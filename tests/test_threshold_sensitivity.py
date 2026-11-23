"""Tests for the threshold-selection evidence (reviewer comment 5, the priority ask).

The Module 4 proposal claimed the 90th percentile was "verified against sample
mean excess functions" without ever producing that evidence. These tests hold the
code to the claim: the curve must be measured, the band must be derived from it,
and a threshold whose own data contradicts the heavy-tail premise must be rejected
rather than clamped into acceptability.
"""

import numpy as np
import pandas as pd
import pytest

from config import POT_THRESHOLD_QUANTILES
from threshold_sensitivity import (
    MEL_GRID_POINTS, MIN_EXCEEDANCES_FULL_SAMPLE, linear_mel_band, mel_table,
    profile_over_thresholds, select_threshold,
)

N = 5000


@pytest.fixture(scope="module")
def heavy_tailed_resid():
    """Standardised t(4) innovations: a genuine positive shape and enough tail data."""
    rng = np.random.default_rng(31)
    z = rng.standard_t(4, size=N) * np.sqrt(2.0 / 4.0)
    return pd.Series(z, index=pd.RangeIndex(N))


@pytest.fixture(scope="module")
def bounded_resid():
    """Uniform innovations: an upper-bounded tail, so the shape must come out negative."""
    rng = np.random.default_rng(32)
    u = (rng.uniform(size=N) - 0.5) * np.sqrt(12.0)
    return pd.Series(u, index=pd.RangeIndex(N))


class TestProfile:
    def test_raw_and_used_shape_are_both_reported(self, heavy_tailed_resid):
        profile = profile_over_thresholds(heavy_tailed_resid,
                                          quantiles=(0.80, 0.90, 0.95),
                                          confidence_levels=(0.99,))
        for column in ("xi_raw", "xi_used", "clamped", "beta", "u", "n_u", "var_z"):
            assert column in profile.columns, column

    def test_a_clamped_row_shows_the_value_the_clamp_replaced(self, bounded_resid):
        profile = profile_over_thresholds(bounded_resid, quantiles=(0.90,),
                                          confidence_levels=(0.99,))
        row = profile.iloc[0]
        assert row["clamped"] and row["xi_raw"] < 0.0 <= row["xi_used"]

    def test_cells_with_no_tail_to_extrapolate_are_absent(self, heavy_tailed_resid):
        profile = profile_over_thresholds(heavy_tailed_resid,
                                          quantiles=(0.90, 0.975, 0.98),
                                          confidence_levels=(0.975, 0.99))
        pairs = set(profile.index.tolist())
        assert (0.975, 0.975) not in pairs and (0.98, 0.975) not in pairs
        assert (0.90, 0.975) in pairs and (0.90, 0.99) in pairs

    def test_exceedance_count_falls_monotonically_in_the_threshold(
            self, heavy_tailed_resid):
        profile = profile_over_thresholds(heavy_tailed_resid,
                                          quantiles=POT_THRESHOLD_QUANTILES,
                                          confidence_levels=(0.99,))
        counts = profile.droplevel("confidence_level")["n_u"]
        assert counts.is_monotonic_decreasing
        assert counts.iloc[-1] >= 10


class TestMeanExcessGrid:
    def test_every_grid_point_keeps_the_stated_exceedance_count(self, heavy_tailed_resid):
        curve = mel_table(heavy_tailed_resid)
        assert len(curve) == MEL_GRID_POINTS
        assert (curve["n_exceedances"] >= MIN_EXCEEDANCES_FULL_SAMPLE).all()
        assert curve["u"].is_monotonic_increasing
        assert {"sample_e_hat", "se_excess", "implied_quantile"} <= set(curve.columns)

    def test_the_error_bars_grow_along_the_curve(self, heavy_tailed_resid):
        curve = mel_table(heavy_tailed_resid)
        assert curve["se_excess"].iloc[-1] > curve["se_excess"].iloc[0]

    def test_the_grid_is_on_the_loss_scale_not_the_innovation_scale(
            self, heavy_tailed_resid):
        """A near-symmetric residual distribution hides a sign error everywhere except here.

        The exceedance count at each u is only reproducible if u was measured on
        the same scale the curve was built from, so the count is the test.
        """
        losses = -heavy_tailed_resid.to_numpy()
        curve = mel_table(heavy_tailed_resid)
        for i in (0, len(curve) // 2, len(curve) - 1):
            u = curve["u"].iloc[i]
            assert int((losses > u).sum()) == int(curve["n_exceedances"].iloc[i])
        assert curve["n_exceedances"].iloc[-1] == pytest.approx(
            MIN_EXCEEDANCES_FULL_SAMPLE, abs=2)


class TestLinearBand:
    def test_a_heavy_tail_yields_a_band_that_reaches_the_top_of_the_curve(
            self, heavy_tailed_resid):
        band = linear_mel_band(mel_table(heavy_tailed_resid))
        assert band is not None
        assert band["u_lo"] <= band["u_hi"]
        assert band["n_points"] >= 4
        assert band["max_deviation_in_se"] <= band["z_tolerance"]
        assert band["mel_support_u_lo"] <= band["u_lo"]
        assert band["u_hi"] <= band["mel_support_u_hi"] + 1e-12

    def test_too_few_points_is_reported_as_no_band_not_a_degenerate_band(
            self, heavy_tailed_resid):
        curve = mel_table(heavy_tailed_resid, n_points=3, min_exceedances=10)
        assert len(curve) == 3
        assert linear_mel_band(curve, min_exceedances=10) is None

    def test_a_bounded_tail_bends_down_at_the_top_of_the_curve(self, bounded_resid):
        """A distribution with an upper endpoint loses mean excess as u approaches it.

        That bend is what disqualifies a high threshold on a light-tailed sample,
        and it is visible in the data rather than in the clamped shape.
        """
        curve = mel_table(bounded_resid)
        assert curve["sample_e_hat"].iloc[-1] < curve["sample_e_hat"].max()


class TestSelection:
    def test_the_recommendation_is_the_lowest_eligible_threshold(self, heavy_tailed_resid):
        curve = mel_table(heavy_tailed_resid)
        profile = profile_over_thresholds(heavy_tailed_resid,
                                         confidence_levels=(0.99,))
        result = select_threshold(curve, profile, alpha=0.99)
        if result["recommended_q"] is not None:
            eligible_qs = sorted(r["threshold_quantile"] for r in result["eligible"])
            assert result["recommended_q"] == eligible_qs[0]
            assert result["recommended_q"] < 0.99

    def test_a_negative_shape_is_rejected_on_evidence_not_clamped_away(
            self, bounded_resid):
        curve = mel_table(bounded_resid)
        profile = profile_over_thresholds(bounded_resid, confidence_levels=(0.99,))
        result = select_threshold(curve, profile, alpha=0.99)
        rejected = {r["threshold_quantile"]: r["reasons"] for r in result["rejected"]}
        assert any("shape" in reason for reason in rejected.values()) or not result["eligible"]
        for row in result["rejected"]:
            assert "reasons" in row

    def test_value_at_risk_spread_is_reported_for_the_grid_and_the_eligible_set(
            self, heavy_tailed_resid):
        curve = mel_table(heavy_tailed_resid)
        profile = profile_over_thresholds(heavy_tailed_resid, confidence_levels=(0.99,))
        result = select_threshold(curve, profile, alpha=0.99)
        assert result["var_z_spread_across_grid"] >= 0.0
        assert result["var_z_min"] <= result["var_z_max"]
        assert result["n_grid"] == len(POT_THRESHOLD_QUANTILES)

    def test_the_production_threshold_is_scored_against_the_same_rule(
            self, heavy_tailed_resid):
        curve = mel_table(heavy_tailed_resid)
        profile = profile_over_thresholds(heavy_tailed_resid, confidence_levels=(0.99,))
        result = select_threshold(curve, profile, alpha=0.99, production_q=0.90)
        assert isinstance(result["production_eligible"], bool)
        assert isinstance(result["production_is_recommended"], bool)
        assert result["rationale"]

    def test_xi_significance_is_counted_not_assumed(self, heavy_tailed_resid):
        curve = mel_table(heavy_tailed_resid)
        profile = profile_over_thresholds(heavy_tailed_resid, confidence_levels=(0.99,))
        result = select_threshold(curve, profile, alpha=0.99)
        assert 0 <= result["n_thresholds_whose_shape_is_significant"] <= result["n_grid"]

    def test_eligibility_demands_a_positive_raw_shape_not_a_clamped_one(
            self, heavy_tailed_resid):
        """The rule reads xi_raw, so a recommendation is never an artefact of the clamp."""
        curve = mel_table(heavy_tailed_resid)
        profile = profile_over_thresholds(heavy_tailed_resid, confidence_levels=(0.99,))
        result = select_threshold(curve, profile, alpha=0.99)
        for row in result["eligible"]:
            assert row["xi_raw"] is not None and row["xi_raw"] > 0
            assert row["n_u"] >= MIN_EXCEEDANCES_FULL_SAMPLE
            assert row["var_z"] > row["u"]
