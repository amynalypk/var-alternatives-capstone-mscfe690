"""Tests for the two-stage estimator: the GARCH filter and the peaks-over-threshold tail.

These are the invariants that make the tail number mean what it says. Several of
them exist because of a defect found in the Module 4 code while answering the peer
review, so they are regression tests in the literal sense.
"""

import numpy as np
import pandas as pd
import pytest

from risk_models import (
    InsufficientExceedances, InvalidThresholdConfiguration, compute_evt_quantiles,
    fit_evt_pot, fit_evt_pot_diag, fit_garch11, fit_garch11_state, gpd_mean_excess,
    mean_excess_curve, residual_diagnostics,
)
from tail_metrics import build_breach_register, clopper_pearson
from conftest import simulate_garch_t


class TestGarchFilter:
    def test_unpacking_is_stable_for_legacy_callers(self, returns_array):
        """Module 4 call sites unpack four values; adding a fifth must stay opt-in."""
        out = fit_garch11(returns_array[:500])
        assert len(out) == 4
        res, cond_vol, std_resid, mu = out
        assert np.isfinite(cond_vol).all() and (cond_vol > 0).all()
        assert np.isfinite(std_resid).all()

    def test_residuals_are_standardised(self, returns_array):
        _res, _cv, z, _mu = fit_garch11(returns_array[:500])
        assert abs(float(np.mean(z))) < 0.1
        assert 0.7 < float(np.std(z, ddof=1)) < 1.3

    def test_conditional_volatility_is_on_the_input_scale(self, returns_array):
        """The arch estimation is done on returns x 100 and must come back de-scaled."""
        _res, cond_vol, _z, _mu = fit_garch11(returns_array[:500])
        ratio = np.std(cond_vol) / np.std(returns_array[:500])
        assert 0.3 < ratio < 3.0

    def test_student_t_returns_degrees_of_freedom(self, returns_array):
        _res, _cv, _z, _mu, nu = fit_garch11(returns_array[:500], dist="t",
                                             include_nu=True)
        assert nu > 2.0
        _r2, _c2, _z2, _m2, nu_normal = fit_garch11(returns_array[:500], dist="normal",
                                                    include_nu=True)
        assert not np.isfinite(nu_normal)

    def test_state_flattens_the_parameters_the_recursion_needs(self, returns_array):
        state = fit_garch11_state(returns_array[:500])
        for key in ("mu", "omega", "alpha", "beta", "cond_vol", "std_resid"):
            assert key in state, key
        assert 0.0 < state["alpha"] < 1.0 and 0.0 < state["beta"] < 1.0
        assert state["omega"] > 0.0


class TestThresholdFit:
    def test_clamped_shape_stays_in_the_module_4_band(self, std_resid):
        _u, xi, beta, _n_u, _n_tot, _ = fit_evt_pot(std_resid, 0.90, clamp_xi=True)
        assert 0.001 <= xi <= 0.8
        assert beta > 0.0

    def test_a_sparse_threshold_raises_instead_of_inventing_parameters(self):
        """DEFECT 2: the Module 4 fallback returned xi=0.1, beta=1.0 as if fitted."""
        sparse = np.concatenate([np.zeros(400), np.linspace(1.0, 3.0, 5)])
        with pytest.raises(InsufficientExceedances):
            fit_evt_pot(sparse, 0.99, clamp_xi=False)
        u, xi, beta, n_u, _n_tot, _ = fit_evt_pot(sparse, 0.99, clamp_xi=True)
        assert (xi, beta) == (0.1, 1.0) and n_u < 10

    def test_negative_shape_is_reachable_when_the_clamp_is_off(self):
        """A bounded tail is a real finding; clamping it to +0.001 launders it away."""
        rng = np.random.default_rng(3)
        bounded = (rng.uniform(size=1500) - 0.5) / (1 / np.sqrt(12))
        _u, xi_raw, _b, _n, _t, _ = fit_evt_pot(bounded, 0.95, clamp_xi=False)
        _u2, xi_clamped, _b2, _n2, _t2, _ = fit_evt_pot(bounded, 0.95, clamp_xi=True)
        assert xi_raw < 0.0
        assert xi_clamped == pytest.approx(0.001)

    def test_exceedance_count_falls_as_the_threshold_rises(self, std_resid):
        counts = [fit_evt_pot_diag(std_resid, q)["n_u"] for q in (0.80, 0.85, 0.90, 0.95)]
        assert counts == sorted(counts, reverse=True)
        assert len(set(counts)) > 1

    def test_diagnostic_record_reports_raw_and_used_shape(self, std_resid):
        rec = fit_evt_pot_diag(std_resid, 0.90)
        assert set(("xi_raw", "xi_used", "clamped", "clamp_direction", "degenerate",
                    "xi_se", "ks_pvalue", "aic_gpd")) <= set(rec)
        if rec["clamped"]:
            assert rec["xi_used"] != rec["xi_raw"]
        else:
            assert rec["xi_used"] == rec["xi_raw"]


class TestEvtQuantiles:
    def test_a_threshold_at_or_above_the_coverage_level_raises(self):
        """P1: tail_prob reaches 1 and the formula silently returns VaR below u."""
        with pytest.raises(InvalidThresholdConfiguration):
            compute_evt_quantiles(u=1.0, xi=0.1, beta=1.0, n_exceedances=10,
                                  total_n=1000, confidence_level=0.99)

    def test_expected_shortfall_exceeds_value_at_risk(self, std_resid):
        rec = fit_evt_pot_diag(std_resid, 0.90)
        var_z, es_z = compute_evt_quantiles(rec["u"], rec["xi_used"], rec["beta"],
                                            rec["n_u"], rec["n_tot"], 0.99)
        assert es_z > var_z > rec["u"]

    def test_higher_coverage_needs_a_larger_reserve(self, std_resid):
        rec = fit_evt_pot_diag(std_resid, 0.90)
        var_975, _ = compute_evt_quantiles(rec["u"], rec["xi_used"], rec["beta"],
                                           rec["n_u"], rec["n_tot"], 0.975)
        var_99, _ = compute_evt_quantiles(rec["u"], rec["xi_used"], rec["beta"],
                                          rec["n_u"], rec["n_tot"], 0.99)
        assert var_99 > var_975

    def test_the_zero_shape_branch_is_continuous(self):
        """The exponential limit must not jump relative to a near-zero shape."""
        args = dict(u=1.5, beta=0.8, n_exceedances=100, total_n=2000)
        var0, es0 = compute_evt_quantiles(xi=0.0, **args)
        var_eps, es_eps = compute_evt_quantiles(xi=2e-5, **args)
        assert abs(var0 - var_eps) < 1e-3
        assert abs(es0 - es_eps) < 1e-3


class TestMeanExcess:
    def test_gpd_mean_excess_matches_the_closed_form(self):
        assert gpd_mean_excess(u=1.0, xi=0.2, beta=0.8) == pytest.approx(
            0.8 / 0.8 + 0.2 * 1.0 / 0.8)
        assert gpd_mean_excess(1.0, 0.0, 0.8) == pytest.approx(0.8)

    def test_curve_carries_the_sample_estimate_and_the_uncertainty(self, std_resid):
        """Linearity is judged against se_excess, so the column has to be there."""
        curve = mean_excess_curve(std_resid, n_points=12)
        assert {"u", "mean_excess", "se_excess", "n_exceedances"} <= set(curve.columns)
        assert len(curve) == 12
        assert (curve["n_exceedances"].to_numpy() <= len(std_resid)).all()
        assert curve["n_exceedances"].is_monotonic_decreasing

    def test_a_higher_threshold_has_fewer_exceedances_and_larger_error_bars(self, std_resid):
        curve = mean_excess_curve(std_resid, n_points=20)
        thin = curve.tail(5).dropna()
        thick = curve.head(5).dropna()
        assert thin["se_excess"].median() > thick["se_excess"].median()


class TestDiagnostics:
    def test_diagnostics_survive_a_datetime_index(self, returns_series):
        """P7: statsmodels returns all-NaN on a DatetimeIndex series on this stack."""
        _res, _cv, z, _mu = fit_garch11(returns_series.to_numpy()[:500])
        indexed = pd.Series(z, index=returns_series.index[:len(z)])
        out = residual_diagnostics(indexed)
        assert np.isfinite(out["arch_lm"]["pvalue"])
        assert out["n_obs"] == len(z)

    def test_second_order_iid_is_tested_not_assumed(self, returns_array):
        """The squares are what POT needs i.i.d.; the levels are a separate question."""
        _res, _cv, z, _mu = fit_garch11(returns_array[:500])
        out = residual_diagnostics(z)
        assert set(out["ljung_box_z2_pvalues"]) == {1, 5, 10, 20}
        assert all(p > 0.0 for p in out["ljung_box_z2_pvalues"].values())
        assert isinstance(out["second_order_rejected_at_5pct"], bool)
        assert isinstance(out["first_order_rejected_at_5pct"], bool)

    def test_a_non_finite_pvalue_raises_instead_of_silently_passing(self):
        """A NaN diagnostic reads as "not rejected", so it must never be returned."""
        with pytest.raises(ValueError):
            residual_diagnostics(np.array([1.0, np.nan, -2.0, 0.5, 3.0, -1.0]))


class TestTailMetrics:
    def test_clopper_pearson_brackets_a_zero_count(self):
        low, high = clopper_pearson(0, 100)
        assert low == 0.0
        assert 0.0 < high < 0.05

    def test_exact_interval_contains_the_wald_interval(self):
        low_cp, high_cp = clopper_pearson(46, 4531)
        assert low_cp < 46 / 4531 < high_cp
        assert high_cp - low_cp > 0.004

    def test_register_lists_breaches_and_drops_missing_forecasts(self):
        """A missing forecast is a different defect from a failed one: neither counted."""
        dates = pd.bdate_range("2020-01-01", periods=6)
        losses = np.array([0.01, 0.05, 0.02, 0.09, 0.00, 0.03])
        var = np.array([0.02, 0.04, np.nan, 0.08, 0.02, 0.02])
        frame = build_breach_register(dates, losses, var)
        assert len(frame) == 3
        assert (frame["Exceedance"] > 0.0).all()
        assert frame["Exceedance"].is_monotonic_decreasing
        assert not frame.index.isna().any()

    def test_an_empty_register_keeps_its_columns(self):
        dates = pd.bdate_range("2020-01-01", periods=4)
        frame = build_breach_register(dates, np.array([0.01] * 4), np.array([0.05] * 4))
        assert len(frame) == 0
        assert {"Loss", "VaR", "Exceedance"} <= set(frame.columns)
