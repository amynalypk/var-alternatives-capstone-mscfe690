"""Tests for the walk-forward engine and its backtest statistics.

The two tests that matter most here are the recursion reference and the
no-look-ahead check. The first pins the defect found while answering the peer
review: Module 4 applied the most recent shock twice on the days between refits.
The second is the property every out-of-sample claim in the report rests on, and
it fails loudly if a slice ever reaches forward.
"""

import numpy as np
import pandas as pd
import pytest

from backtester import (
    christoffersen_test, evaluate_risk_model_performance, kupiec_pof_test,
    run_dirichlet_robustness_test, run_walk_forward_backtest,
    segment_performance_by_regimes,
)
from config import GARCH_REFIT_INTERVAL, POT_THRESHOLD_QUANTILE, ROLLING_WINDOW
from risk_models import compute_evt_quantiles, fit_evt_pot, fit_garch11

M4_COLUMNS = ["Return", "Loss", "VaR_Normal", "VaR_Historical",
              "VaR_GARCH_EVT", "ES_GARCH_EVT"]


def reference_corrected_path(values, window=ROLLING_WINDOW, confidence_level=0.99,
                             refit_interval=GARCH_REFIT_INTERVAL,
                             threshold_quantile=POT_THRESHOLD_QUANTILE):
    """The recursion written from the GARCH(1,1) forecast definition.

    Deliberately re-derived rather than imported from the engine: each realised
    residual enters sigma squared exactly once, and the variance carried into the
    next day is the forecast just made. If the double application creeps back, this
    and the engine part company.
    """
    n_test = len(values) - window
    var_out = np.zeros(n_test)
    es_out = np.zeros(n_test)
    mu = omega = alpha = beta = var_z = None
    sigma_var_prev = None

    for i in range(n_test):
        train = values[i:i + window]
        if i % refit_interval == 0:
            res, cond_vol, std_resid, mu = fit_garch11(train, dist="normal")
            u, xi, b, n_u, n_tot, _ = fit_evt_pot(std_resid, threshold_quantile)
            var_z, es_z = compute_evt_quantiles(u, xi, b, n_u, n_tot, confidence_level)
            omega = float(res.params["omega"] / 10000.0)
            alpha = float(res.params["alpha[1]"])
            beta = float(res.params["beta[1]"])
            sigma_var_prev = float(cond_vol[-1]) ** 2
        eps = float(train[-1]) - mu
        sigma_next = np.sqrt(omega + alpha * eps ** 2 + beta * sigma_var_prev)
        var_out[i] = -mu + sigma_next * var_z
        es_out[i] = -mu + sigma_next * es_z
        sigma_var_prev = sigma_next ** 2

    return var_out, es_out


class TestKupiec:
    def test_zero_exceptions_matches_the_closed_form(self):
        """x = 0 has an exact likelihood-ratio: LR = -2 n ln(1 - p)."""
        lr, p = kupiec_pof_test(0, 100, 0.99)
        assert lr == pytest.approx(-2.0 * 100 * np.log(0.99), abs=1e-12)
        assert 0.0 < p < 1.0

    def test_a_perfectly_matching_count_is_not_rejected(self):
        _lr, p = kupiec_pof_test(1, 100, 0.99)
        assert p > 0.99

    def test_a_grossly_wrong_rate_is_rejected(self):
        _lr, p = kupiec_pof_test(50, 100, 0.99)
        assert p < 1e-10

    def test_statistic_increases_with_the_discrepancy(self):
        few, _p1 = kupiec_pof_test(3, 1000, 0.99)
        many, _p2 = kupiec_pof_test(30, 1000, 0.99)
        assert many > few


class TestChristoffersen:
    def test_alternating_breaches_reject_independence(self):
        """Clustering is what the test looks for; a perfect alternation is its mirror."""
        e = np.tile([1, 0], 150)
        out = christoffersen_test(e, 0.99)
        assert out["p_val_ind"] < 0.05
        assert out["Transitions"] == (0, 149, 150, 0)

    def test_conditional_coverage_decomposes_into_two_pieces(self):
        e = np.zeros(500, dtype=int)
        e[[17, 91, 250, 401]] = 1
        out = christoffersen_test(e, 0.99)
        assert out["LR_cc"] == pytest.approx(out["LR_uc"] + out["LR_ind"])
        assert out["p_val_cc"] > 0.05

    def test_a_silent_book_does_not_crash(self):
        out = christoffersen_test(np.zeros(300, dtype=int), 0.99)
        assert np.isfinite(out["p_val_ind"])
        assert out["Transitions"] == (299, 0, 0, 0)


class TestWalkForwardFrame:
    @pytest.fixture(scope="class")
    def frame(self, returns_series):
        return run_walk_forward_backtest(returns_series)

    def test_schema_is_the_module_4_contract(self, frame, returns_series):
        assert list(frame.columns) == M4_COLUMNS
        assert isinstance(frame.index, pd.DatetimeIndex)
        assert len(frame) == len(returns_series) - ROLLING_WINDOW

    def test_loss_is_the_sign_flip_of_return(self, frame):
        assert np.allclose(frame["Loss"], -frame["Return"])

    def test_every_forecast_is_finite(self, frame):
        for col in ("VaR_Normal", "VaR_Historical", "VaR_GARCH_EVT", "ES_GARCH_EVT"):
            assert np.isfinite(frame[col].to_numpy()).all(), col

    def test_expected_shortfall_sits_above_value_at_risk(self, frame):
        assert (frame["ES_GARCH_EVT"] > frame["VaR_GARCH_EVT"]).all()

    def test_vix_is_attached_only_when_supplied(self, returns_series, returns_frame):
        plain = run_walk_forward_backtest(returns_series)
        with_vix = run_walk_forward_backtest(
            returns_series, vix_series=returns_frame["^VIX"])
        assert "VIX" not in plain.columns
        assert list(with_vix["VIX"].index) == list(plain.index)

    def test_recursion_flag_changes_the_forecasts(self, returns_series):
        """The flag is live, not decorative: the two recursions are different models."""
        legacy = run_walk_forward_backtest(returns_series, variance_recursion="legacy")
        corrected = run_walk_forward_backtest(returns_series, variance_recursion="corrected")
        assert not np.allclose(legacy["VaR_GARCH_EVT"], corrected["VaR_GARCH_EVT"])
        assert np.allclose(legacy["VaR_Historical"], corrected["VaR_Historical"])

    def test_corrected_recursion_matches_the_reference(self, returns_series):
        var, es = reference_corrected_path(returns_series.to_numpy())
        frame = run_walk_forward_backtest(returns_series, variance_recursion="corrected")
        np.testing.assert_allclose(frame["VaR_GARCH_EVT"].to_numpy(), var, rtol=1e-12)
        np.testing.assert_allclose(frame["ES_GARCH_EVT"].to_numpy(), es, rtol=1e-12)


class TestNoLookAhead:
    def test_truncating_the_input_leaves_earlier_forecasts_unchanged(self, returns_series):
        """The single most valuable test in the suite.

        A forecast made on day t may only use data up to t. Cutting the sample at
        day m must therefore reproduce the first m - window forecasts bit for bit.
        Any look-ahead - a full-sample threshold, a regime tercile, a normalising
        constant - shows up here as a difference.
        """
        full = run_walk_forward_backtest(returns_series, variance_recursion="corrected")
        cut = 900
        short = run_walk_forward_backtest(returns_series.iloc[:cut],
                                          variance_recursion="corrected")
        assert len(short) == cut - ROLLING_WINDOW
        pd.testing.assert_frame_equal(
            short, full.iloc[:len(short)], check_exact=False, atol=0.0, rtol=0.0
        )

    def test_an_earlier_confidence_level_does_not_shift_the_window(self, returns_series):
        short = run_walk_forward_backtest(returns_series.iloc[:900], confidence_level=0.975)
        full = run_walk_forward_backtest(returns_series, confidence_level=0.975)
        pd.testing.assert_index_equal(short.index, full.index[:len(short)])


class TestPerformanceSummary:
    def test_module_4_keys_survive_and_module_6_keys_are_added(self, returns_series):
        frame = run_walk_forward_backtest(returns_series)
        perf = evaluate_risk_model_performance(frame)
        for key in ("Total Obs", "Actual Breaches", "Breach Rate (%)", "Kupiec p-val",
                    "Independence p-val", "Mean Excess Loss (%)"):
            assert key in perf["VaR_GARCH_EVT"], key
        for key in ("Breach Rate 95% CI (%)", "Nominal Rate Inside 95% CI",
                    "Total Excess (USD)", "Median Excess Loss (%)"):
            assert key in perf["VaR_GARCH_EVT"], key

    def test_breach_counts_agree_with_a_direct_count(self, returns_series):
        frame = run_walk_forward_backtest(returns_series)
        perf = evaluate_risk_model_performance(frame)
        direct = int((frame["Loss"] > frame["VaR_GARCH_EVT"]).sum())
        assert perf["VaR_GARCH_EVT"]["Actual Breaches"] == direct

    def test_the_exact_interval_brackets_the_observed_rate(self, returns_series):
        frame = run_walk_forward_backtest(returns_series)
        perf = evaluate_risk_model_performance(frame)["VaR_GARCH_EVT"]
        low, high = perf["Breach Rate 95% CI (%)"]
        assert low <= perf["Breach Rate (%)"] <= high


def segmented_frame():
    """Eight days whose VIX band and exception counts can be done by hand.

    VIX 18, 12, 15 are calm; 29, 22 normal; 31, 38, 35 crisis. Against a flat
    VaR_GARCH_EVT of 2%, the exceptions fall on the first, second, sixth and
    seventh days, so the three bands carry 1, 0 and 3 of them and still sum to the
    whole sample. The two date windows pick up three and two days out of the same
    eight, which is the point of the whole class below.
    """
    dates = pd.to_datetime(["2008-09-10", "2008-10-01", "2009-06-15", "2015-05-05",
                            "2019-08-05", "2020-03-01", "2020-04-15", "2023-01-03"])
    frame = pd.DataFrame({"Loss": [0.03, 0.05, 0.02, 0.005, 0.01, 0.06, 0.04, 0.008],
                          "VaR_Normal": 0.01, "VaR_Historical": 0.025,
                          "VaR_GARCH_EVT": 0.02, "ES_GARCH_EVT": 0.03}, index=dates)
    frame["VIX"] = [18.0, 31.0, 29.0, 12.0, 22.0, 38.0, 35.0, 15.0]
    return frame


class TestRegimeSegments:
    """The VIX bands partition the sample and the crisis windows overlap it.

    Module 4's Table 2 put all five rows in one block, and a reader who added the
    Observations column got roughly twice the sample. The helper is kept because the
    Module 4 report generator still calls it, so these tests pin both the counts and
    the trap.
    """

    @pytest.fixture(scope="class")
    def summary(self):
        return segment_performance_by_regimes(segmented_frame())

    def test_the_three_bands_account_for_every_day_exactly_once(self, summary):
        bands = [k for k in summary if "VIX" in k]
        assert len(bands) == 3
        assert sum(summary[k]["Observations"] for k in bands) == 8

    def test_the_date_windows_are_subsets_that_must_not_be_added(self, summary):
        overlays = [k for k in summary if "VIX" not in k]
        assert len(overlays) == 2
        assert sum(summary[k]["Observations"] for k in overlays) == 5
        total = sum(v["Observations"] for v in summary.values())
        assert total > 8, "a block that sums to more than the sample cannot be a partition"

    def test_band_membership_and_exception_counts_match_a_hand_count(self, summary):
        assert summary["Calm (VIX < 20)"]["VaR_GARCH_EVT_Breaches"] == 1
        assert summary["Normal (20 <= VIX < 30)"]["VaR_GARCH_EVT_Breaches"] == 0
        assert summary["Crisis (VIX >= 30)"]["VaR_GARCH_EVT_Breaches"] == 3
        assert sum(summary[k]["VaR_GARCH_EVT_Breaches"] for k in
                   [k for k in summary if "VIX" in k]) == 4

    def test_rates_are_breaches_over_that_cells_own_days(self, summary):
        assert summary["Crisis (VIX >= 30)"]["VaR_GARCH_EVT_Rate (%)"] == 100.0
        assert summary["2008 GFC Shock"]["VaR_GARCH_EVT_Rate (%)"] == pytest.approx(
            2 / 3 * 100.0)

    def test_mean_excess_averages_only_the_exceptions(self, summary):
        assert summary["Crisis (VIX >= 30)"]["VaR_GARCH_EVT_MeanExcess (%)"] == \
            pytest.approx(3.0)
        assert summary["Calm (VIX < 20)"]["VaR_GARCH_EVT_MeanExcess (%)"] == \
            pytest.approx(1.0)

    def test_an_empty_segment_reports_zero_excess_instead_of_raising(self, summary):
        cell = summary["Normal (20 <= VIX < 30)"]
        assert cell["VaR_GARCH_EVT_MeanExcess (%)"] == 0.0
        assert cell["VaR_GARCH_EVT_Rate (%)"] == 0.0

    def test_es_is_scored_against_the_es_forecast_not_the_var_one(self, summary):
        assert summary["Crisis (VIX >= 30)"]["ES_GARCH_EVT_Breaches"] == 3
        assert summary["Calm (VIX < 20)"]["ES_GARCH_EVT_Breaches"] == 0

    def test_a_frame_without_vix_returns_an_empty_dict(self):
        frame = segmented_frame().drop(columns=["VIX"])
        assert segment_performance_by_regimes(frame) == {}

    def test_a_band_with_no_days_is_absent_rather_than_zero_filled(self):
        frame = segmented_frame()
        frame["VIX"] = 15.0
        summary = segment_performance_by_regimes(frame)
        assert set(summary) == {"Calm (VIX < 20)", "2008 GFC Shock", "2020 COVID Crash"}
        assert summary["Calm (VIX < 20)"]["Observations"] == 8


class TestDirichletWeightRobustness:
    """Module 4's random-weight panel, and the row of it that carries no information.

    Historical VaR is the empirical quantile of the same window it is scored on, so
    its breach rate is the nominal one whatever the weights are. The test below is
    the evidence for the disclosure the manifest attaches to that panel (Module 4's
    table 4, table 9 of the Module 6 report).
    """

    SIMULATIONS = 6

    @pytest.fixture(scope="class")
    def rates(self, returns_frame):
        tickers = [c for c in returns_frame.columns if c.startswith("A")]
        return run_dirichlet_robustness_test(
            returns_frame, tickers, n_simulations=self.SIMULATIONS)

    def test_every_model_returns_one_rate_per_simulation(self, rates):
        assert set(rates) == {"VaR_Normal_Rates", "VaR_Historical_Rates",
                              "VaR_GARCH_EVT_Rates", "ES_GARCH_EVT_Rates"}
        for series in rates.values():
            assert len(series) == self.SIMULATIONS
            assert all(0.0 <= r <= 100.0 for r in series)

    def test_historical_var_spread_over_weights_is_exactly_zero(self, rates):
        hist = np.asarray(rates["VaR_Historical_Rates"])
        assert hist.max() - hist.min() < 1e-9
        assert hist.mean() == pytest.approx(1.0, abs=1e-9)

    def test_the_other_three_rows_do_move_with_the_weights(self, rates):
        for key in ("VaR_Normal_Rates", "VaR_GARCH_EVT_Rates", "ES_GARCH_EVT_Rates"):
            series = np.asarray(rates[key])
            assert series.max() - series.min() > 1e-6, key

    def test_the_seed_makes_the_panel_reproducible(self, returns_frame):
        tickers = [c for c in returns_frame.columns if c.startswith("A")]
        first = run_dirichlet_robustness_test(returns_frame, tickers, n_simulations=2)
        second = run_dirichlet_robustness_test(returns_frame, tickers, n_simulations=2)
        for key in first:
            assert first[key] == second[key], key
