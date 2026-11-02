"""Tests for the single-pass sweep engine that produces Tables 8, 11 and 12.

The engine's claim is that twenty configurations from one pass are the same
numbers twenty passes would have produced. That is the one property worth
testing, because if it is false every row of the sensitivity table is an
artefact of the shared residuals rather than a model comparison.
"""

import os

import numpy as np
import pandas as pd
import pytest

from config import M6_WALK_FORWARD_CACHE, ROLLING_WINDOW
from walkforward_engine import (
    _valid_configurations, run_multi_config_walk_forward, slice_config, summarise_sweep,
)

SHORT_GRID = {"threshold_quantiles": (0.80, 0.90),
              "confidence_levels": (0.99, 0.975),
              "innovation_dists": ("normal", "t")}


@pytest.fixture(scope="module")
def sweep(returns_series):
    return run_multi_config_walk_forward(returns_series, cache_path=None, force=True,
                                         **SHORT_GRID)


class TestConfigurationGuard:
    def test_a_threshold_at_or_above_the_coverage_level_is_excluded(self):
        valid, skipped = _valid_configurations((0.90, 0.975, 0.98), (0.975, 0.99))
        assert (0.975, 0.975) in skipped and (0.98, 0.975) in skipped
        assert (0.90, 0.975) in valid and (0.90, 0.99) in valid
        assert len(valid) + len(skipped) == 6

    def test_no_valid_pair_can_produce_a_tail_ratio_of_one(self):
        valid, _skipped = _valid_configurations((0.80, 0.85, 0.90, 0.95, 0.975, 0.98),
                                                (0.975, 0.99))
        assert all(q < alpha for q, alpha in valid)


class TestSharedPassAgreement:
    def test_row_count_is_days_times_configurations(self, sweep, returns_series):
        n_days = len(returns_series) - ROLLING_WINDOW
        assert len(sweep["frame"]) == n_days * 4 * 2
        assert sweep["frame"].index.nunique() == n_days

    def test_refit_count_is_one_garch_estimation_per_distribution_per_refit_date(
            self, sweep, returns_series):
        """n_refits counts GARCH fits, not refit dates: production shows 454 = 227 x 2."""
        n_days = len(returns_series) - ROLLING_WINDOW
        refit_dates = len(range(0, n_days, 20))
        assert sweep["n_refits"] == refit_dates * len(SHORT_GRID["innovation_dists"])

    @pytest.mark.parametrize("dist", ["normal", "t"])
    def test_one_config_from_the_shared_pass_equals_a_pass_of_its_own(
            self, returns_series, sweep, dist):
        """The whole point of the shared engine, checked against an independent run."""
        single = run_multi_config_walk_forward(
            returns_series, cache_path=None, force=True,
            threshold_quantiles=(0.90,), confidence_levels=(0.99,),
            innovation_dists=(dist,))
        shared = slice_config(sweep["frame"], dist, 0.90, 0.99)
        own = slice_config(single["frame"], dist, 0.90, 0.99)
        pd.testing.assert_frame_equal(shared, own)

    def test_expected_shortfall_stays_above_value_at_risk_in_every_config(self, sweep):
        frame = sweep["frame"]
        assert (frame["ES_GARCH_EVT"] > frame["VaR_GARCH_EVT"]).all()

    def test_a_higher_coverage_level_never_prices_a_smaller_reserve(self, sweep):
        frame = sweep["frame"]
        for dist in ("normal", "t"):
            lo = frame[(frame.innovation_dist == dist) & (frame.threshold_q == 0.90)
                       & (frame.confidence_level == 0.975)]["VaR_GARCH_EVT"].to_numpy()
            hi = frame[(frame.innovation_dist == dist) & (frame.threshold_q == 0.90)
                       & (frame.confidence_level == 0.99)]["VaR_GARCH_EVT"].to_numpy()
            assert (hi >= lo - 1e-15).all()

    @pytest.mark.skipif(not os.path.exists(M6_WALK_FORWARD_CACHE),
                        reason="the production sweep cache is not present")
    def test_the_shared_pass_writes_nothing_to_the_production_cache(self, returns_series):
        """A benchmark that measures the sweep must not overwrite the sweep.

        This happened: cache_path=None used to mean "use the default file", so a
        single-configuration timing pass replaced the 90,620-row grid with its own
        4,531 rows. The sentinel now keeps the two apart, and this test is the
        guard against re-merging them.
        """
        before = os.stat(M6_WALK_FORWARD_CACHE)
        run_multi_config_walk_forward(returns_series, cache_path=None, force=True,
                                      threshold_quantiles=(0.90,),
                                      confidence_levels=(0.99,),
                                      innovation_dists=("normal",))
        after = os.stat(M6_WALK_FORWARD_CACHE)
        assert (before.st_size, before.st_mtime) == (after.st_size, after.st_mtime)


class TestSweepSummary:
    def test_summary_reports_the_identification_columns(self, sweep):
        table = summarise_sweep(sweep["frame"])
        for column in ("days", "n_u_min", "degenerate_days", "clamped_days",
                       "xi_se_missing_days", "xi_not_identified_days", "var_z_nan"):
            assert column in table.columns, column
        assert table["days"].sum() == len(sweep["frame"])

    def test_a_window_without_a_shape_interval_counts_as_not_identified(self, sweep):
        table = summarise_sweep(sweep["frame"])
        assert (table["xi_not_identified_days"] >= table["xi_se_missing_days"]).all()

    def test_the_exceedance_count_rises_as_the_threshold_falls(self, sweep):
        table = summarise_sweep(sweep["frame"]).reset_index()
        for dist in ("normal", "t"):
            rows = table[table["innovation_dist"] == dist].sort_values("threshold_q")
            assert rows["n_u_median"].is_monotonic_decreasing
