"""Tests for the portfolio-specific regime definition (reviewer comment 3).

The whole ask is that VIX prices the index, not this book, so the alternative
definition has to be measurably not self-fulfilling. Every test here defends one
of the two ways it could be: using the day it labels, or re-cutting the bands on
the full sample and then describing the beginning.
"""

import numpy as np
import pandas as pd
import pytest

from config import VIX_CALM_THRESHOLD, VIX_CRISIS_THRESHOLD
from regime_segmentation import (
    PORTFOLIO_REGIME_LABELS, VIX_REGIME_LABELS, agreement_table, build_regime_frame,
    classify_portfolios_regimes, classify_vix_regimes, cross_tab_with_breach_rates,
    freeze_regime_cut_points, lagged_realised_vol,
)

N_DAYS = 800
VOL_WINDOW = 20
CAL_DAYS = 200


@pytest.fixture(scope="module")
def returns_df():
    rng = np.random.default_rng(21)
    index = pd.bdate_range("2005-01-03", periods=N_DAYS)
    shock = rng.standard_normal(N_DAYS)
    regime = np.r_[np.full(N_DAYS // 2, 0.6), np.full(N_DAYS - N_DAYS // 2, 1.8)]
    portfolio = 0.0005 + 0.01 * regime * shock
    vix = 12.0 + 90.0 * np.abs(portfolio) / 0.03 + rng.normal(0, 1.0, N_DAYS)
    return pd.DataFrame({"Portfolio": portfolio, "VIX": np.clip(vix, 9, 90)},
                        index=index)


class TestLaggedRealisedVol:
    def test_the_day_being_labelled_is_not_in_its_own_measure(self, returns_df):
        """Shift is the point: same-day loss would make the high-vol band tautological."""
        vol = lagged_realised_vol(returns_df["Portfolio"], window=VOL_WINDOW)
        mutated = returns_df["Portfolio"].copy()
        mutated.iloc[VOL_WINDOW] = -0.90
        mutated_vol = lagged_realised_vol(mutated, window=VOL_WINDOW)
        assert vol.iloc[VOL_WINDOW] == mutated_vol.iloc[VOL_WINDOW]
        assert vol.iloc[VOL_WINDOW] != vol.iloc[VOL_WINDOW + 1]

    def test_the_window_has_a_finite_start(self, returns_df):
        vol = lagged_realised_vol(returns_df["Portfolio"], window=VOL_WINDOW)
        assert vol.isna().iloc[:VOL_WINDOW].all()
        assert vol.notna().iloc[VOL_WINDOW:].all()

    def test_a_flat_book_has_no_volatility(self, returns_df):
        flat = pd.Series(0.001, index=returns_df.index)
        vol = lagged_realised_vol(flat, window=VOL_WINDOW)
        assert np.nanmax(vol.to_numpy()) < 1e-12


class TestFrozenCutPoints:
    def test_data_after_the_calibration_window_cannot_move_the_bands(self, returns_df):
        vol = lagged_realised_vol(returns_df["Portfolio"], window=VOL_WINDOW).dropna()
        before = freeze_regime_cut_points(vol, cal_days=CAL_DAYS)
        tail = vol.copy()
        tail.iloc[CAL_DAYS:] *= 20.0
        after = freeze_regime_cut_points(tail, cal_days=CAL_DAYS)
        assert before["cut_points"] == after["cut_points"]
        assert before["calibration_days"] == CAL_DAYS

    def test_the_bands_are_quantiles_of_the_calibration_window(self, returns_df):
        vol = lagged_realised_vol(returns_df["Portfolio"], window=VOL_WINDOW).dropna()
        cuts = freeze_regime_cut_points(vol, cal_days=CAL_DAYS)["cut_points"]
        head = vol.iloc[:CAL_DAYS].to_numpy()
        assert cuts[0] == pytest.approx(float(np.quantile(head, 1 / 3)))
        assert cuts[1] == pytest.approx(float(np.quantile(head, 2 / 3)))

    def test_an_undersupplied_calibration_raises(self, returns_df):
        vol = lagged_realised_vol(returns_df["Portfolio"], window=VOL_WINDOW).dropna()
        with pytest.raises(ValueError):
            freeze_regime_cut_points(vol, cal_days=15)


class TestClassification:
    def test_ordering_follows_volatility(self, returns_df):
        vol = lagged_realised_vol(returns_df["Portfolio"], window=VOL_WINDOW)
        cuts = freeze_regime_cut_points(vol.dropna(), cal_days=CAL_DAYS)["cut_points"]
        probe = pd.Series([0.0, cuts[0] - 1e-9, cuts[1] - 1e-9, cuts[1] + 1e-9],
                          index=pd.RangeIndex(4))
        labels = classify_portfolios_regimes(probe, cuts).to_list()
        assert labels == [PORTFOLIO_REGIME_LABELS[0], PORTFOLIO_REGIME_LABELS[0],
                          PORTFOLIO_REGIME_LABELS[1], PORTFOLIO_REGIME_LABELS[2]]

    def test_missing_volatility_is_unlabelled_not_assigned(self, returns_df):
        vol = lagged_realised_vol(returns_df["Portfolio"], window=VOL_WINDOW)
        cuts = freeze_regime_cut_points(vol.dropna(), cal_days=CAL_DAYS)["cut_points"]
        labels = classify_portfolios_regimes(vol, cuts)
        assert labels.iloc[:VOL_WINDOW].isna().all()
        assert labels.iloc[VOL_WINDOW:].notna().all()

    def test_vix_bands_use_the_boundaries_the_report_quotes(self, returns_df):
        vix = pd.Series([VIX_CALM_THRESHOLD - 0.01, VIX_CALM_THRESHOLD,
                         VIX_CRISIS_THRESHOLD - 0.01, VIX_CRISIS_THRESHOLD + 5],
                        index=pd.RangeIndex(4))
        assert classify_vix_regimes(vix).to_list() == [
            VIX_REGIME_LABELS[0], VIX_REGIME_LABELS[1], VIX_REGIME_LABELS[1],
            VIX_REGIME_LABELS[2]]


class TestAgreement:
    def test_both_definitions_are_returned_and_differ(self, returns_df):
        from regime_segmentation import PORTFOLIO_COLUMN_BALANCED, PORTFOLIO_COLUMN_FROZEN
        frame, meta = build_regime_frame(returns_df, vol_window=VOL_WINDOW,
                                        cal_days=CAL_DAYS)
        assert {"frozen", "balanced"} <= set(meta)
        assert {PORTFOLIO_COLUMN_FROZEN, PORTFOLIO_COLUMN_BALANCED} <= set(frame.columns)
        frozen = freeze_regime_cut_points(
            frame["RealisedVol"].dropna(), cal_days=CAL_DAYS)["cut_points"]
        balanced = freeze_regime_cut_points(
            frame["RealisedVol"].dropna(), cal_days=len(frame))["cut_points"]
        assert frozen != balanced, "the two definitions must be visibly different"

    def test_kappa_and_agreement_are_in_range(self, returns_df):
        frame, _meta = build_regime_frame(returns_df, vol_window=VOL_WINDOW,
                                         cal_days=CAL_DAYS)
        table = agreement_table(frame)
        assert -1.0 <= table["kappa_unweighted"] <= 1.0
        assert 0.0 <= table["pct_agreement"] <= 100.0
        assert table["pct_within_one_band"] >= table["pct_agreement"]
        assert table["n_classified"] == sum(table["marginals_portfolio"].values())

    def test_identical_labelings_score_perfect_agreement(self, returns_df):
        """Two vocabularies for the same ordered thing must be mapped, not compared as strings.

        Copying the portfolio labels into the VIX column verbatim gives an
        agreement of zero and an undefined kappa; relabelling low_vol as calm is
        the same statement in the other scheme, and only then does the statistic
        see agreement. That is the trap the production code documents.
        """
        frame, _meta = build_regime_frame(returns_df, vol_window=VOL_WINDOW,
                                         cal_days=CAL_DAYS)
        identical = frame.copy()
        to_vix = dict(zip(PORTFOLIO_REGIME_LABELS, VIX_REGIME_LABELS))
        identical["vix_regime"] = identical["portfolio_regime_balanced"].map(to_vix)
        table = agreement_table(identical)
        assert table["kappa_unweighted"] == pytest.approx(1.0)
        assert table["pct_agreement"] == pytest.approx(100.0)

    def test_the_same_labels_compared_across_vocabularies_agree_on_nothing(self, returns_df):
        frame, _meta = build_regime_frame(returns_df, vol_window=VOL_WINDOW,
                                         cal_days=CAL_DAYS)
        confused = frame.copy()
        confused["vix_regime"] = confused["portfolio_regime_balanced"]
        with pytest.raises(ValueError):
            agreement_table(confused)


class TestCrossTab:
    def test_cells_partition_the_scored_days(self, returns_df):
        frame, _meta = build_regime_frame(returns_df, vol_window=VOL_WINDOW,
                                         cal_days=CAL_DAYS)
        dates = frame.index[VOL_WINDOW + CAL_DAYS:]
        sweep = pd.DataFrame({
            "innovation_dist": "normal",
            "threshold_q": 0.90,
            "confidence_level": 0.99,
            "VaR_GARCH_EVT": 0.03,
            "ES_GARCH_EVT": 0.04,
        }, index=dates)
        table, joined = cross_tab_with_breach_rates(frame, sweep)
        assert len(table) == 9
        assert int(table["Observations"].sum()) == len(joined)
        assert table["Share (%)"].sum() == pytest.approx(100.0, abs=1e-6)

    def test_a_breach_rate_of_a_constant_forecast_matches_a_direct_count(
            self, returns_df):
        frame, _meta = build_regime_frame(returns_df, vol_window=VOL_WINDOW,
                                         cal_days=CAL_DAYS)
        dates = frame.index[VOL_WINDOW + CAL_DAYS:]
        sweep = pd.DataFrame({
            "innovation_dist": "normal", "threshold_q": 0.90,
            "confidence_level": 0.99, "VaR_GARCH_EVT": 0.02, "ES_GARCH_EVT": 0.03,
        }, index=dates)
        table, joined = cross_tab_with_breach_rates(frame, sweep)
        direct = int((joined["Loss"] > 0.02).sum())
        assert int(table["Breaches"].sum()) == direct
