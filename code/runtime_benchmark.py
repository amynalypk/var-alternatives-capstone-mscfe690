

import json
import os
import platform
import time
from statistics import quantiles

import numpy as np
import pandas as pd

from config import (
    ROLLING_WINDOW, GARCH_REFIT_INTERVAL, POT_THRESHOLD_QUANTILE,
    PRIMARY_CONFIDENCE, PRIMARY_POT_THRESHOLD_QUANTILE,
    PRIMARY_GARCH_INNOVATION_DISTRIBUTION, VARIANCE_RECURSION,
    BENCH_REPEATS_FAST, BENCH_REPEATS_SLOW, BENCH_WARMUP, BENCH_REFIT_INTERVALS,
    PRIMARY_ES_LP_ALPHA, DATA_DIR,
)
from risk_models import (
    calculate_historical_var, calculate_parametric_var, fit_garch11,
    fit_evt_pot_diag, compute_evt_quantiles, residual_diagnostics,
)
from forecast_eval import score_forecasts
from walkforward_engine import run_multi_config_walk_forward

BENCH_CACHE_MODEL_COSTS = os.path.join(DATA_DIR, "m6_runtime_model_costs.csv")
BENCH_CACHE_CADENCE = os.path.join(DATA_DIR, "m6_runtime_refit_cadence.csv")
BENCH_CACHE_SHARING = os.path.join(DATA_DIR, "m6_runtime_sweep_sharing.csv")
BENCH_CACHE_ENVIRONMENT = os.path.join(DATA_DIR, "m6_runtime_environment.json")
OOS_DAYS = 4531


def environment_fingerprint():
    
    import arch
    import scipy
    import statsmodels
    import sklearn

    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "statsmodels": statsmodels.__version__,
        "arch": arch.__version__,
        "scikit_learn": sklearn.__version__,
    }


def _time_callables(fast=BENCH_REPEATS_FAST, slow=BENCH_REPEATS_SLOW,
                    warmup=BENCH_WARMUP):
    
    def run(fn, repeats):
        for _ in range(warmup):
            fn()
        samples = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            fn()
            samples.append((time.perf_counter() - t0) * 1000.0)
        samples.sort()
        mid = samples[len(samples) // 2]
        if len(samples) >= 20:
            p95 = quantiles(samples, n=20)[-1]
        else:
            p95 = samples[-1]
        return {"median_ms": mid, "p95_ms": p95, "min_ms": samples[0],
                "n_repeats": repeats}

    return run


def benchmark_model_costs(train_slice, n_assets=20, window=ROLLING_WINDOW,
                          refit_interval=GARCH_REFIT_INTERVAL,
                          fast=BENCH_REPEATS_FAST, slow=BENCH_REPEATS_SLOW,
                          warmup=BENCH_WARMUP, n_test=OOS_DAYS):
    
    run = _time_callables(fast, slow, warmup)
    arr = np.asarray(train_slice, dtype=float)

    z = None
    gpd = None
    try:
        _res, _cv, z, _mu = fit_garch11(arr, dist=PRIMARY_GARCH_INNOVATION_DISTRIBUTION)
        gpd = fit_evt_pot_diag(z, PRIMARY_POT_THRESHOLD_QUANTILE)
    except Exception:
        pass

    rng = np.random.default_rng(0)
    scenarios = rng.normal(0.0, 0.012, size=(window, n_assets))
    mu_vec = np.zeros(n_assets)

    from portfolio_optimizer import min_es_lp, min_variance_weights, scenario_covariance

    refits_per_pass = (n_test + refit_interval - 1) // refit_interval
    measured = [
        ("Historical simulation VaR", lambda: calculate_historical_var(arr, PRIMARY_CONFIDENCE),
         n_test, fast, "every day"),
        ("Gaussian parametric VaR", lambda: calculate_parametric_var(arr, PRIMARY_CONFIDENCE),
         n_test, fast, "every day"),
        ("GARCH(1,1) MLE, normal innovations", lambda: fit_garch11(arr, dist="normal"),
         None, slow, f"every {refit_interval} days"),
        ("GARCH(1,1) MLE, Student-t innovations", lambda: fit_garch11(arr, dist="t"),
         None, slow, f"every {refit_interval} days"),
    ]
    if z is not None:
        measured.append(
            ("GPD peaks-over-threshold fit",
             lambda: fit_evt_pot_diag(z, PRIMARY_POT_THRESHOLD_QUANTILE), None, fast,
             f"every {refit_interval} days"))
        measured.append(
            ("GPD quantile arithmetic",
             lambda: compute_evt_quantiles(gpd["u"], gpd["xi_used"], gpd["beta"],
                                           gpd["n_u"], gpd["n_tot"], PRIMARY_CONFIDENCE),
             n_test, fast, "every day"))
        measured.append(
            ("Full GARCH-EVT calibration",
             lambda: _joint_calibration(arr, PRIMARY_POT_THRESHOLD_QUANTILE), None, slow,
             f"every {refit_interval} days"))
        measured.append(
            ("Residual i.i.d. diagnostic battery",
             lambda: residual_diagnostics(z), 1, fast, "reported once"))

    measured.append(
        ("Minimum-ES linear programme",
         lambda: min_es_lp(scenarios, alpha=PRIMARY_ES_LP_ALPHA,
                           expected_returns=mu_vec), refits_per_pass, slow,
         f"every {refit_interval} days"))
    measured.append(
        ("Minimum-variance QP (benchmark)",
         lambda: min_variance_weights(scenario_covariance(scenarios)),
         refits_per_pass, slow, f"every {refit_interval} days"))

    rows = []
    for name, fn, per_pass, repeats, cadence in measured:
        t = run(fn, repeats)
        refits = (n_test + refit_interval - 1) // refit_interval if per_pass is None else per_pass
        wall_s = t["median_ms"] * refits / 1000.0
        rows.append({
            "Model": name,
            "Calibration median (ms)": t["median_ms"],
            "Calibration p95 (ms)": t["p95_ms"],
            "Calibration min (ms)": t["min_ms"],
            "Repeats": t["n_repeats"],
            "Runs per pass": refits,
            "Cadence": cadence,
            "Full-pass cost (s)": wall_s,
            "Amortised per forecast (us)": wall_s * 1e6 / n_test,
        })
    return pd.DataFrame(rows).set_index("Model")


def _joint_calibration(arr, threshold_quantile):
    
    res, cond_vol, std_resid, mu = fit_garch11(arr, dist=PRIMARY_GARCH_INNOVATION_DISTRIBUTION)
    diag = fit_evt_pot_diag(std_resid, threshold_quantile)
    compute_evt_quantiles(diag["u"], diag["xi_used"], diag["beta"], diag["n_u"],
                          diag["n_tot"], PRIMARY_CONFIDENCE)
    return res


def benchmark_refit_cadence(portfolio_returns, intervals=BENCH_REFIT_INTERVALS,
                            window=ROLLING_WINDOW):
    
    losses = -np.asarray(portfolio_returns.values[window:], dtype=float)
    rows = []
    for k in intervals:
        t0 = time.perf_counter()
        out = run_multi_config_walk_forward(
            portfolio_returns, None,
            confidence_levels=(PRIMARY_CONFIDENCE,),
            threshold_quantiles=(PRIMARY_POT_THRESHOLD_QUANTILE,),
            innovation_dists=(PRIMARY_GARCH_INNOVATION_DISTRIBUTION,),
            window=window, refit_interval=k,
            variance_recursion=VARIANCE_RECURSION, cache_path=None, force=True)
        wall = time.perf_counter() - t0
        frame = out["frame"]
        scores = score_forecasts(losses, frame["VaR_GARCH_EVT"].to_numpy(),
                                 PRIMARY_CONFIDENCE,
                                 es_forecasts=frame["ES_GARCH_EVT"].to_numpy())
        rows.append({
            "Refit interval (days)": k,
            "Refits": out["n_refits"],
            "Scored days": len(frame),
            "Wall time (s)": wall,
            "Wall time per forecast (ms)": wall * 1000.0 / max(len(frame), 1),
            "Breaches": scores["Actual Breaches"],
            "Breach rate (%)": scores["Breach Rate (%)"],
            "Kupiec p": scores["Kupiec p-val"],
            "Christoffersen p": scores["Conditional Cov p-val"],
            "Mean excess loss (%)": scores["Mean Excess Loss (%)"],
        })
        print(f"[Bench] refit every {k:3d} days: {out['n_refits']:5d} refits, "
              f"{wall:7.1f}s, {scores['Actual Breaches']:3d} breaches "
              f"({scores['Breach Rate (%)']:.3f}%)")
    return pd.DataFrame(rows).set_index("Refit interval (days)")


def benchmark_sweep_sharing(portfolio_returns, window=ROLLING_WINDOW):
    
    single = dict(confidence_levels=(PRIMARY_CONFIDENCE,),
                  threshold_quantiles=(PRIMARY_POT_THRESHOLD_QUANTILE,),
                  innovation_dists=(PRIMARY_GARCH_INNOVATION_DISTRIBUTION,))
    t0 = time.perf_counter()
    one = run_multi_config_walk_forward(portfolio_returns, None, window=window,
                                        cache_path=None, force=True, **single)
    wall_single = time.perf_counter() - t0

    t0 = time.perf_counter()
    full = run_multi_config_walk_forward(portfolio_returns, None, window=window,
                                         cache_path=None, force=True)
    wall_full = time.perf_counter() - t0

    n_configs = len(full["frame"]) // max(len(one["frame"]), 1)
    return {
        "configurations_in_sweep": int(n_configs),
        "single_config_pass_wall_time_s": wall_single,
        "single_config_refits": one["n_refits"],
        "shared_pass_wall_time_s": wall_full,
        "shared_pass_refits": full["n_refits"],
        "naive_independent_passes_s": wall_single * n_configs,
        "saving_vs_independent (%)": (1.0 - wall_full / (wall_single * n_configs)) * 100.0,
        "cost_per_configuration_minute": wall_full / 60.0 / n_configs,
    }


def run_runtime_benchmarks(portfolio_returns, write_cache=True):
    
    costs = benchmark_model_costs(portfolio_returns.iloc[:ROLLING_WINDOW].to_numpy())
    cadence = benchmark_refit_cadence(portfolio_returns)
    sharing = benchmark_sweep_sharing(portfolio_returns)
    payload = {"model_costs": costs, "refit_cadence": cadence,
               "sweep_sharing": sharing,
               "environment": environment_fingerprint(),
               "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if write_cache:
        costs.to_csv(BENCH_CACHE_MODEL_COSTS)
        cadence.to_csv(BENCH_CACHE_CADENCE)
        pd.Series(sharing).to_frame("value").to_csv(BENCH_CACHE_SHARING)
        
        
        with open(BENCH_CACHE_ENVIRONMENT, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        print(f"[Bench] wrote four benchmark caches to {DATA_DIR}")
    return payload


if __name__ == "__main__":
    from data_acquisition import fetch_and_cache_data, process_returns

    print("Environment:", environment_fingerprint())
    returns_df = process_returns(fetch_and_cache_data())
    t0 = time.perf_counter()
    out = run_runtime_benchmarks(returns_df["Portfolio"])
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print("\n=== Table 21: calibration cost per model ===")
        print(out["model_costs"].to_string(float_format=lambda v: f"{v:,.4f}"))
        print("\n=== Table 22: cost and accuracy by re-estimation cadence ===")
        print(out["refit_cadence"].to_string(float_format=lambda v: f"{v:,.4f}"))
        print("\n=== Table 23: one shared pass versus independent passes ===")
        for key, value in out["sweep_sharing"].items():
            print(f"  {key:34s} {value:,.4f}" if isinstance(value, (int, float))
                  else f"  {key:34s} {value}")
    print(f"\n{time.perf_counter() - t0:.0f}s total")
