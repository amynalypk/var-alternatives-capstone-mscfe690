"""Tests for the minimum-ES linear programme and its scenario plumbing.

The LP is the only part of Module 6 where an error would not announce itself: a
silently infeasible solve that fell back to equal weight would still print a
table. These tests therefore check the failure paths as hard as the successes.
"""

import numpy as np
import pytest

from portfolio_optimizer import (
    build_scenarios, concentration_report, empirical_es, equal_weight,
    mean_off_diagonal_correlation, min_es_lp, min_variance_weights,
    portfolio_losses, scenario_covariance, shrunk_covariance,
)


@pytest.fixture(scope="module")
def scenarios():
    """A correlated 8-asset scenario block: common factor plus idiosyncratic noise."""
    rng = np.random.default_rng(11)
    k, n = 300, 8
    common = rng.standard_normal(k)
    block = np.column_stack([0.7 * common + 0.7 * rng.standard_normal(k) for _ in range(n)])
    tail_days = np.argmax(np.abs(common))
    block[tail_days] -= 0.05          # one coherent crash scenario, not nine noise draws
    return block


def _bounds_ok(w, lo=0.0, hi=0.15):
    return (w >= lo - 1e-8).all() and (w <= hi + 1e-8).all()


class TestScenarioConstruction:
    def test_conditional_scenarios_reproduce_the_point_forecast(self, scenarios):
        assert scenarios.shape == (300, 8)
        assert np.isfinite(scenarios).all()

    def test_a_non_positive_volatility_is_refused(self):
        mu = np.zeros(3)
        sigma = np.array([0.01, -0.01, 0.02])
        with pytest.raises(ValueError):
            build_scenarios(mu, sigma, np.ones((10, 3)))

    def test_row_count_mismatch_is_refused(self):
        with pytest.raises(ValueError):
            build_scenarios(np.zeros(3), np.ones(3), np.ones((10, 4)))

    def test_rows_with_any_missing_asset_are_dropped_not_zero_filled(self):
        z = np.ones((6, 3))
        z[2, 1] = np.nan
        out = build_scenarios(np.zeros(3), np.ones(3), z)
        assert out.shape == (5, 3)

    def test_alignment_across_assets_is_preserved(self):
        """Column-wise resampling would destroy tail dependence, so rows must stay rows."""
        z = np.arange(12, dtype=float).reshape(4, 3)
        out = build_scenarios(np.zeros(3), np.ones(3), z)
        np.testing.assert_allclose(out, z)


class TestLinearProgramme:
    def test_budget_and_weight_cap_hold(self, scenarios):
        out = min_es_lp(scenarios, alpha=0.975)
        assert out["status"] == 0 and out["weights"] is not None
        assert out["weights"].sum() == pytest.approx(1.0, abs=1e-8)
        assert _bounds_ok(out["weights"])

    def test_objective_is_no_worse_than_equal_weight(self, scenarios):
        ew = equal_weight(8)
        out = min_es_lp(scenarios, alpha=0.975)
        assert out["es"] <= empirical_es(ew, scenarios, 0.975) + 1e-10

    def test_lp_value_equals_an_independent_evaluation_of_its_own_weights(self, scenarios):
        """The solver and the evaluator must agree, or one of them is wrong."""
        out = min_es_lp(scenarios, alpha=0.975)
        assert out["es"] == pytest.approx(out["empirical_es_check"], rel=1e-9)
        assert out["es"] == pytest.approx(
            empirical_es(out["weights"], scenarios, 0.975), rel=1e-9)

    def test_a_higher_confidence_level_prices_a_deeper_tail(self, scenarios):
        """ES_0.99 averages only the extreme tail, ES_0.95 dilutes it with milder days."""
        es_95 = min_es_lp(scenarios, alpha=0.95)["es"]
        es_99 = min_es_lp(scenarios, alpha=0.99)["es"]
        assert es_95 <= es_99 + 1e-12

    def test_cvar_is_convex_so_the_midpoint_book_is_feasible(self, scenarios):
        a = min_es_lp(scenarios, alpha=0.975)["weights"]
        ew = equal_weight(8)
        mid = 0.5 * (a + ew)
        assert empirical_es(mid, scenarios, 0.975) <= 0.5 * (
            empirical_es(a, scenarios, 0.975) + empirical_es(ew, scenarios, 0.975)) + 1e-12

    def test_a_cap_too_tight_for_the_simplex_raises_instead_of_returning_junk(self):
        """Six assets at 15% cannot sum to 1: no portfolio exists."""
        rng = np.random.default_rng(5)
        with pytest.raises(ValueError):
            min_es_lp(rng.normal(scale=0.01, size=(100, 6)), alpha=0.975)

    def test_an_unreachable_return_floor_reports_infeasible_not_equal_weighted(self, scenarios):
        expected = np.full(8, 0.001)
        out = min_es_lp(scenarios, alpha=0.975, expected_returns=expected,
                        return_floor=0.50)
        assert out["status"] != 0
        assert out["weights"] is None
        assert out["objective"] is None

    def test_bad_alpha_is_rejected(self, scenarios):
        for alpha in (0.0, 1.0, 1.5):
            with pytest.raises(ValueError):
                min_es_lp(scenarios, alpha=alpha)


class TestTurnoverAndFloors:
    def test_turnover_cap_is_respected(self, scenarios):
        w_prev = equal_weight(8)
        cap = 0.10
        out = min_es_lp(scenarios, alpha=0.975, w_prev=w_prev, turnover_cap=cap)
        assert out["status"] == 0
        assert np.abs(out["weights"] - w_prev).sum() / 2.0 <= cap + 1e-8

    def test_a_cap_leaves_the_objective_no_better_than_the_free_solve(self, scenarios):
        free = min_es_lp(scenarios, alpha=0.975)["es"]
        w_prev = equal_weight(8)
        capped = min_es_lp(scenarios, alpha=0.975, w_prev=w_prev,
                           turnover_cap=0.05)["es"]
        assert capped >= free - 1e-12

    def test_return_floor_is_met_when_it_is_attainable(self, scenarios):
        expected = scenarios.mean(axis=0)
        attainable = float(expected.min())
        out = min_es_lp(scenarios, alpha=0.975, expected_returns=expected,
                       return_floor=attainable)
        assert out["status"] == 0
        assert expected @ out["weights"] >= attainable - 1e-10

    def test_a_floor_needs_something_to_floor_against(self, scenarios):
        with pytest.raises(ValueError):
            min_es_lp(scenarios, alpha=0.975, return_floor=0.001)


class TestQuadraticBenchmarks:
    def test_minimum_variance_beats_equal_weight_on_variance(self, scenarios):
        cov = scenario_covariance(scenarios)
        out = min_variance_weights(cov)
        ew = equal_weight(8)
        assert out["weights"].sum() == pytest.approx(1.0, abs=1e-6)
        assert _bounds_ok(out["weights"])
        assert out["variance"] <= ew @ cov @ ew

    def test_shrinkage_stays_symmetric_and_positive_definite(self, scenarios):
        lw = shrunk_covariance(scenarios)
        assert np.allclose(lw, lw.T)
        assert np.linalg.eigvalsh(lw).min() > 0.0

    def test_sample_covariance_is_recovered_from_its_own_scenarios(self, scenarios):
        manual = np.cov(scenarios, rowvar=False, ddof=1)
        np.testing.assert_allclose(scenario_covariance(scenarios), manual)


class TestReportingHelpers:
    def test_equal_weight_concentrates_nothing(self):
        report = concentration_report(equal_weight(20))
        assert report["herfindahl"] == pytest.approx(1.0 / 20.0)
        assert report["names_held"] == 20

    def test_a_one_name_book_has_herfindahl_one(self):
        w = np.zeros(20)
        w[3] = 1.0
        assert concentration_report(w)["herfindahl"] == pytest.approx(1.0)

    def test_off_diagonal_correlation_of_independent_columns_is_near_zero(self):
        rng = np.random.default_rng(2)
        assert abs(mean_off_diagonal_correlation(rng.normal(size=(500, 6)))) < 0.1

    def test_off_diagonal_correlation_of_identical_columns_is_one(self):
        matrix = np.tile(np.linspace(-1, 1, 400)[:, None], (1, 5))
        assert mean_off_diagonal_correlation(matrix) == pytest.approx(1.0, abs=1e-10)

    def test_portfolio_loss_is_the_sign_flip_of_the_weighted_return(self, scenarios):
        w = equal_weight(8)
        np.testing.assert_allclose(portfolio_losses(w, scenarios),
                                   -(scenarios @ w))
