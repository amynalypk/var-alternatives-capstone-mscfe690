"""Tests for reviewer comment 8: turning exception counts into magnitudes and dollars.

Module 4 reported 46 exceptions and stopped. Module 6 has to report what each miss
cost, and that introduces a category of error the frequency work cannot make: a
breach rate is a *frequency*, a reserve is a *stock* held every day, and an
unfunded loss is a *flow* realised only on the days the tail appears. Adding the
last two, or quoting a 46-of-4,531 rate with a normal-approximation interval, are
the two mistakes this file exists to prevent.

The fixture is a six-day book chosen so every expected value can be written down
by hand. A synthetic random sample would let a wrong sign or a mis-scaled dollar
pass unnoticed, which is exactly how the Module 4 checklist recorded its findings.
"""

import numpy as np
import pandas as pd
import pytest

from economic_impact import (
    concentration, economic_headline, economic_summary, model_economic_comparison,
    reserve_adequacy, worst_breaches,
)
from tail_metrics import build_breach_register, clopper_pearson

# A small notional so the dollar arithmetic stays readable inside an assertion.
NOTIONAL = 1_000_000.0
CONFIDENCE = 0.99

# Day 3 carries no forecast at all. It must be scored neither as a breach nor as a
# pass, which leaves five days, three exceptions, each clearing its forecast by
# exactly one percentage point.
DATES = pd.bdate_range("2020-01-01", periods=6)
LOSSES = np.array([0.01, 0.05, 0.02, 0.09, 0.00, 0.03])
VAR = np.array([0.02, 0.04, np.nan, 0.08, 0.02, 0.02])
ES = np.array([0.03, 0.045, 0.03, 0.12, 0.03, 0.025])
RETURNS = -LOSSES


def _summary(es_forecasts=ES, **kwargs):
    return economic_summary(LOSSES, VAR, confidence_level=CONFIDENCE,
                            notional=NOTIONAL, es_forecasts=es_forecasts,
                            returns=RETURNS, **kwargs)


def _adequacy():
    return reserve_adequacy(LOSSES, VAR, ES, confidence_level=CONFIDENCE,
                            notional=NOTIONAL)


class TestEconomicSummary:
    def test_a_missing_forecast_is_neither_a_breach_nor_a_pass(self):
        """The whole sample is six days; the scored sample is five."""
        out = _summary(es_forecasts=None)
        assert out["Total Obs"] == 5
        assert out["Actual Breaches"] == 3
        assert out["Expected Breaches"] == pytest.approx(5 * 0.01)
        assert out["Breach Rate (%)"] == pytest.approx(60.0)

    def test_the_dollar_block_is_arithmetic_on_the_rate_block(self):
        """USD figures are a rescaling of the same excesses, never a re-estimation."""
        out = _summary(es_forecasts=None)
        assert out["Mean Excess Loss (%)"] == pytest.approx(1.0)
        assert out["Mean Excess (USD)"] == pytest.approx(0.01 * NOTIONAL)
        assert out["Max Excess (USD)"] == pytest.approx(0.01 * NOTIONAL)
        assert out["Cumulative Unreserved Loss (USD)"] == pytest.approx(
            out["Mean Excess (USD)"] * out["Actual Breaches"])
        assert out["Cumulative Unreserved Loss (% of notional)"] == pytest.approx(3.0)
        assert out["Mean VaR (%)"] == pytest.approx(18.0 / 5.0)
        assert out["Total Loss on Breach Days (%)"] == pytest.approx(17.0)

    def test_the_exact_interval_brackets_the_rate_and_decides_the_nominal(self):
        out = _summary(es_forecasts=None)
        low, high = out["Breach Rate 95% CI (%)"]
        assert low <= 60.0 <= high
        expected_low, expected_high = clopper_pearson(3, 5, 0.05)
        assert (low, high) == pytest.approx((expected_low * 100.0, expected_high * 100.0))
        assert out["Nominal Inside 95% CI"] is (expected_low <= 0.01 <= expected_high)

    def test_a_model_that_never_breaches_reports_zeroes_rather_than_nans(self):
        """An empty excess set has a mean of zero shortfall, not of undefined."""
        out = economic_summary(np.array([0.01, 0.005]), np.array([0.02, 0.02]),
                               confidence_level=CONFIDENCE, notional=NOTIONAL)
        assert out["Actual Breaches"] == 0
        assert out["Mean Excess Loss (%)"] == 0.0
        assert out["Cumulative Unreserved Loss (USD)"] == 0.0
        assert out["Breach Rate 95% CI (%)"][0] == 0.0

    def test_es_columns_appear_only_when_an_es_path_is_supplied(self):
        without = _summary(es_forecasts=None)
        with_es = _summary()
        assert "ES Breaches" not in without
        assert with_es["ES Breaches"] == 2
        assert with_es["Mean ES (%)"] == pytest.approx(25.0 / 5.0)


class TestReserveAdequacy:
    def test_stock_and_flow_are_computed_from_their_own_definitions(self):
        """Every value here is hand-derived from the six-day fixture.

        Unreserved under VaR: three breaches at 0.01 each = 0.03. Under ES the
        0.09 day is covered, leaving two breaches at 0.005 = 0.01. The premium
        (ES - VaR) averaged over the five scored days is 0.014 and the mean VaR
        over the same days is 0.036, so the uplift is 0.014 / 0.036.
        """
        out = _adequacy()
        assert out["Total Obs"] == 5
        assert out["Mean VaR (%)"] == pytest.approx(3.6)
        assert out["Cumulative Unreserved under VaR (USD)"] == pytest.approx(30_000.0)
        assert out["Cumulative Unreserved under ES (USD)"] == pytest.approx(10_000.0)
        assert out["Unreserved Loss Avoided by ES (USD)"] == pytest.approx(20_000.0)
        assert out["Incremental Capital Held (USD)"] == pytest.approx(14_000.0)
        assert out["Incremental Capital (% of notional)"] == pytest.approx(1.4)
        assert out["ES Reserve Uplift over VaR (%)"] == pytest.approx(
            0.014 / 0.036 * 100.0)
        assert out["Days ES Also Breached"] == 2
        assert out["Share of VaR Breaches Also ES Breaches (%)"] == pytest.approx(
            2 / 3 * 100.0)
        assert out["Largest Unreserved Day under VaR (USD)"] == pytest.approx(10_000.0)
        assert out["Largest Unreserved Day under ES (USD)"] == pytest.approx(5_000.0)
        assert out["ES Absorbs All VaR Shortfall"] is False

    def test_doubling_the_sample_scales_the_flow_but_leaves_the_stock_alone(self):
        """The docstring's own claim, tested rather than trusted.

        Replicating a backtest doubles the realised shortfall and the number of
        years, but the capital held at each mark is unchanged -- it is a level, not
        a total. A pipeline that summed the daily reserve across the sample would
        double here, and that number would be reported as the cost of ES.
        """
        single = _adequacy()
        doubled = reserve_adequacy(np.concatenate([LOSSES, LOSSES]),
                                  np.concatenate([VAR, VAR]),
                                  np.concatenate([ES, ES]),
                                  confidence_level=CONFIDENCE, notional=NOTIONAL)
        assert doubled["Incremental Capital Held (USD)"] == pytest.approx(
            single["Incremental Capital Held (USD)"])
        assert doubled["Mean VaR Reserve (USD)"] == pytest.approx(
            single["Mean VaR Reserve (USD)"])
        assert doubled["Cumulative Unreserved under VaR (USD)"] == pytest.approx(
            2 * single["Cumulative Unreserved under VaR (USD)"])
        assert doubled["Years"] == pytest.approx(2 * single["Years"])
        assert doubled["Unreserved Loss Avoided per Year (USD)"] == pytest.approx(
            single["Unreserved Loss Avoided per Year (USD)"])

    def test_a_deeper_reserve_cannot_leave_a_larger_shortfall(self):
        """ES is VaR plus a positive uplift, so its residual shortfall must be smaller."""
        var = np.linspace(0.02, 0.03, 40)
        rng = np.random.default_rng(5)
        losses = var + np.abs(rng.standard_normal(40)) * 0.004
        for uplift in (0.002, 0.006, 0.015):
            out = reserve_adequacy(losses, var, var + uplift, notional=NOTIONAL)
            assert out["Cumulative Unreserved under ES (USD)"] <= \
                out["Cumulative Unreserved under VaR (USD)"]
            assert out["Days ES Also Breached"] <= out["Total Obs"]

    def test_a_reserve_above_every_loss_absorbs_the_whole_shortfall(self):
        out = reserve_adequacy(LOSSES, VAR, np.nanmax(VAR) * 10 + LOSSES,
                               notional=NOTIONAL)
        assert out["ES Absorbs All VaR Shortfall"] is True
        assert out["Cumulative Unreserved under ES (USD)"] == 0.0
        assert out["Days ES Also Breached"] == 0

    def test_days_without_either_forecast_drop_out_of_both_sides(self):
        """A missing ES must not be compared to a present VaR on the same row."""
        es_missing = ES.copy()
        es_missing[1] = np.nan
        out = reserve_adequacy(LOSSES, VAR, es_missing, notional=NOTIONAL)
        assert out["Total Obs"] == 4
        assert out["Cumulative Unreserved under VaR (USD)"] == pytest.approx(20_000.0)


class TestWorstBreachesAndConcentration:
    def test_worst_breaches_is_a_prefix_of_the_sorted_register(self):
        register = build_breach_register(DATES, LOSSES, VAR, returns=RETURNS,
                                        es_forecasts=ES, notional=NOTIONAL)
        assert register["Exceedance"].is_monotonic_decreasing
        pd.testing.assert_frame_equal(worst_breaches(register, 2), register.head(2))
        assert len(worst_breaches(register, 10)) == len(register)

    def test_top_k_shares_rise_with_k_and_stay_inside_a_share(self):
        var = np.linspace(0.02, 0.03, 20)
        rng = np.random.default_rng(9)
        losses = var + np.abs(rng.standard_normal(20)) * 0.004
        register = build_breach_register(pd.bdate_range("2021-01-01", periods=20),
                                        losses, var, notional=NOTIONAL)
        out = concentration(register, top_k=(1, 5, 10))
        shares = [out["top_1_share_pct"], out["top_5_share_pct"], out["top_10_share_pct"]]
        assert shares == sorted(shares)
        assert shares[-1] <= 100.0 + 1e-9
        assert out["n_breaches"] == 20
        assert out["largest_single_usd"] == pytest.approx(
            out["total_usd_excess"] * shares[0] / 100.0)
        n = out["n_breaches"]
        assert 1.0 / n - 1e-12 <= out["hhi_of_excess"] <= 1.0 + 1e-12

    def test_a_register_without_shortfall_reports_no_share_instead_of_dividing(self):
        register = build_breach_register(DATES, np.zeros(6), np.ones(6),
                                        notional=NOTIONAL)
        assert register.empty
        out = concentration(register)
        assert out["total_usd_excess"] == 0.0
        assert out["n_breaches"] == 0
        assert np.isnan(out["top_1_share_pct"])


class TestComparisonAndHeadline:
    def test_the_three_candidates_are_reranked_on_dollars_not_counts(self):
        frame = pd.DataFrame({
            "Return": RETURNS,
            "Loss": LOSSES,
            "VaR_Normal": np.full(6, 0.015),
            "VaR_Historical": VAR,
            "VaR_GARCH_EVT": VAR,
            "ES_GARCH_EVT": ES,
        }, index=DATES)
        table = model_economic_comparison(frame, confidence_level=CONFIDENCE,
                                          notional=NOTIONAL)
        assert list(table.index) == ["Gaussian VaR", "Historical VaR", "GARCH-EVT VaR"]
        assert len(table) == 3
        assert table.loc["Gaussian VaR", "Actual Breaches"] == 4
        assert table.loc["GARCH-EVT VaR", "ES Breaches"] == 2
        assert table.loc["GARCH-EVT VaR", "Cumulative Unreserved (USD m)"] == pytest.approx(
            table.loc["GARCH-EVT VaR", "Cumulative Unreserved Loss (USD)"] / 1e6)

    def test_the_headline_restates_the_computed_rows_without_inventing_a_number(self):
        sentences = economic_headline(_summary(), _adequacy(), notional=NOTIONAL)
        blob = " ".join(sentences.values())
        for token in ("nan", "None", "{", "}"):
            assert token not in blob
        assert set(sentences) == {"frequency", "magnitude", "reserve"}
        assert "3 exceptions in 5 out-of-sample days" in sentences["frequency"]
        assert "60.000%" in sentences["frequency"]
        assert "excludes the 1.0% target" in sentences["frequency"]
        assert "$30,000 unreserved" in sentences["magnitude"]
        assert "$14,000 more at every mark" in sentences["reserve"]

    def test_a_well_covered_reserve_is_described_as_absorbing_the_shortfall(self):
        """The reserve sentence flips its clause on a computed flag, so test both ways."""
        adequacy = reserve_adequacy(LOSSES, VAR, np.full(6, 0.8), notional=NOTIONAL)
        summary = _summary(es_forecasts=np.nanmax(VAR) * 10 + LOSSES)
        sentence = economic_headline(summary, adequacy, notional=NOTIONAL)["reserve"]
        assert "it absorbs the whole VaR shortfall" in sentence
        assert "0 of 3 exceptions" in sentence
