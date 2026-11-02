

import os
import time

import numpy as np
import pandas as pd

from config import (
    M6_WALK_FORWARD_CACHE, M6_WALK_FORWARD_CACHE_LEGACY, ROLLING_WINDOW,
    GARCH_REFIT_INTERVAL, POT_THRESHOLD_QUANTILES, GARCH_INNOVATION_DISTRIBUTIONS,
    VARIANCE_RECURSION,
)
from risk_models import fit_garch11, fit_evt_pot_diag, compute_evt_quantiles


_DEFAULT_CACHE_PATH = object()

SWEEP_CONFIDENCE_LEVELS = (0.99, 0.975)

OUTPUT_COLUMNS = [
    "innovation_dist", "threshold_q", "confidence_level", "VaR_GARCH_EVT",
    "ES_GARCH_EVT", "sigma_next", "mu", "u", "xi_raw", "xi_used", "xi_se",
    "beta_gpd", "n_u", "clamped", "degenerate",
]


def _valid_configurations(threshold_quantiles, confidence_levels):
    
    valid, skipped = [], []
    for q in threshold_quantiles:
        for alpha in confidence_levels:
            if q < alpha:
                valid.append((q, alpha))
            else:
                skipped.append((q, alpha))
    return valid, skipped


def _fit_gpd_states(std_resid, threshold_quantiles, confidence_levels):
    
    states = {}
    for q in threshold_quantiles:
        diag = fit_evt_pot_diag(std_resid, q, min_exceedances=10)
        for alpha in confidence_levels:
            if not q < alpha:
                continue
            key = (q, alpha)
            if diag["degenerate"]:
                
                states[key] = {
                    "u": diag["u"], "xi_raw": None, "xi_used": None, "beta": None,
                    "xi_se": None,
                    "n_u": diag["n_u"], "clamped": False, "degenerate": True,
                    "var_z": None, "es_z": None,
                }
                continue
            var_z, es_z = compute_evt_quantiles(
                diag["u"], diag["xi_used"], diag["beta"],
                diag["n_u"], diag["n_tot"], alpha,
            )
            entry = {k: diag[k] for k in ("u", "xi_raw", "xi_used", "beta",
                                          "xi_se", "n_u", "clamped")}
            entry["degenerate"] = False
            entry["var_z"] = var_z
            entry["es_z"] = es_z
            states[key] = entry
    return states


def run_multi_config_walk_forward(portfolio_returns, vix_series=None,
                                  confidence_levels=SWEEP_CONFIDENCE_LEVELS,
                                  threshold_quantiles=POT_THRESHOLD_QUANTILES,
                                  innovation_dists=GARCH_INNOVATION_DISTRIBUTIONS,
                                  window=ROLLING_WINDOW,
                                  refit_interval=GARCH_REFIT_INTERVAL,
                                  variance_recursion=VARIANCE_RECURSION,
                                  cache_path=_DEFAULT_CACHE_PATH,
                                  force=False):
    
    if variance_recursion not in ("legacy", "corrected"):
        raise ValueError(f"unknown variance_recursion: {variance_recursion}")
    if cache_path is _DEFAULT_CACHE_PATH:
        cache_path = (M6_WALK_FORWARD_CACHE if variance_recursion == "corrected"
                      else M6_WALK_FORWARD_CACHE_LEGACY)

    if cache_path and os.path.exists(cache_path) and not force:
        print(f"[Sweep] Loading cached multi-configuration sweep: {cache_path}")
        frame = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        return {"frame": frame, "states": None, "n_refits": None,
                "excluded": [], "from_cache": True}

    valid, skipped = _valid_configurations(threshold_quantiles, confidence_levels)
    print(f"[Sweep] {len(threshold_quantiles)} thresholds x {len(innovation_dists)} "
          f"innovation distributions x {len(confidence_levels)} coverage levels; "
          f"{len(valid)} valid configurations, {len(skipped)} excluded (q >= alpha)")

    n_total = len(portfolio_returns)
    n_test = n_total - window
    values = np.asarray(portfolio_returns.values, dtype=float)
    dates = portfolio_returns.index[window:]

    per_dist = {
        dist: {
            "refit_day": -999, "res": None, "mu": None, "omega": None,
            "alpha": None, "beta": None, "nu": None, "sigma_var": None,
            "evt": {}, "n_u_values": [],
        }
        for dist in innovation_dists
    }

    rows = []
    n_refits = 0
    t_start = time.perf_counter()

    for i in range(n_test):
        train_slice = values[i: window + i]

        for dist in innovation_dists:
            st = per_dist[dist]
            refitted_today = (i - st["refit_day"] >= refit_interval) or st["res"] is None

            if refitted_today:
                res, cond_vol, std_resid, mu = fit_garch11(train_slice, dist=dist)
                st["res"] = res
                st["mu"] = mu
                st["omega"] = float(res.params['omega'] / 10000.0)
                st["alpha"] = float(res.params['alpha[1]'])
                st["beta"] = float(res.params['beta[1]'])
                st["nu"] = float(res.params['nu']) if dist == "t" else float("inf")
                st["sigma_var"] = cond_vol[-1] ** 2
                st["evt"] = _fit_gpd_states(std_resid, threshold_quantiles, confidence_levels)
                st["refit_day"] = i
                st["n_u_values"].append(min(
                    (s["n_u"] for s in st["evt"].values()), default=0
                ))
                n_refits += 1

            eps = train_slice[-1] - st["mu"]
            if variance_recursion == "legacy" and not refitted_today:
                
                
                
                
                st["sigma_var"] = (st["omega"] + st["alpha"] * eps ** 2
                                   + st["beta"] * st["sigma_var"])
            sigma_next = np.sqrt(
                st["omega"] + st["alpha"] * eps ** 2 + st["beta"] * st["sigma_var"]
            )

            for (q, alpha_level), evt in st["evt"].items():
                if evt["degenerate"]:
                    var_f = es_f = np.nan
                else:
                    var_f = -st["mu"] + sigma_next * evt["var_z"]
                    es_f = -st["mu"] + sigma_next * evt["es_z"]

                rows.append((
                    dates[i], dist, q, alpha_level, var_f, es_f, sigma_next, st["mu"],
                    evt["u"], evt["xi_raw"], evt["xi_used"], evt["xi_se"], evt["beta"],
                    evt["n_u"], evt["clamped"], evt["degenerate"],
                ))

            if variance_recursion == "corrected":
                st["sigma_var"] = sigma_next ** 2

        if (i + 1) % 1000 == 0 or (i + 1) == n_test:
            print(f"[Sweep] {i + 1}/{n_test} out-of-sample days, {n_refits} refits "
                  f"({time.perf_counter() - t_start:.1f}s)")

    frame = pd.DataFrame(rows, columns=["Date"] + OUTPUT_COLUMNS)
    frame = frame.set_index("Date")
    frame.attrs["excluded_configurations"] = skipped
    frame.attrs["n_refits"] = n_refits

    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        frame.to_csv(cache_path)
        print(f"[Sweep] Wrote {len(frame):,} rows to {cache_path}")

    return {"frame": frame, "states": per_dist, "n_refits": n_refits,
            "excluded": skipped, "from_cache": False}


def load_multi_config_cache(force=False):
    
    out = {}
    for variant, path in (("corrected", M6_WALK_FORWARD_CACHE),
                          ("legacy", M6_WALK_FORWARD_CACHE_LEGACY)):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"no cached {variant} sweep at {path}; run run_multi_config_walk_forward "
                f"(variance_recursion={variant!r}) first")
        print(f"[Sweep] Loading cached {variant} sweep: {path}")
        out[variant] = pd.read_csv(path, index_col=0, parse_dates=True)
    return out


def slice_config(frame, innovation_dist, threshold_q, confidence_level):
    
    mask = (
        (frame["innovation_dist"] == innovation_dist)
        & (frame["threshold_q"] == threshold_q)
        & (frame["confidence_level"] == confidence_level)
    )
    sub = frame.loc[mask]
    out = pd.DataFrame(index=sub.index)
    out["VaR_GARCH_EVT"] = sub["VaR_GARCH_EVT"].values
    out["ES_GARCH_EVT"] = sub["ES_GARCH_EVT"].values
    out["sigma_next"] = sub["sigma_next"].values
    return out


def summarise_sweep(frame):
    
    work = frame.copy()
    work["xi_negative"] = work["xi_raw"] < 0
    work["xi_se_missing"] = ~np.isfinite(work["xi_se"])
    work["xi_zero_covered"] = (
        ~work["xi_se_missing"]
        & (work["xi_raw"].abs() <= 1.959963985 * work["xi_se"].abs())
    ) | work["xi_se_missing"]

    grouped = work.groupby(["innovation_dist", "threshold_q", "confidence_level"])
    return pd.DataFrame({
        "days": grouped.size(),
        "n_u_min": grouped["n_u"].min(),
        "n_u_median": grouped["n_u"].median(),
        "n_u_max": grouped["n_u"].max(),
        "degenerate_days": grouped["degenerate"].sum(),
        "clamped_days": grouped["clamped"].sum(),
        "xi_negative_days": grouped["xi_negative"].sum(),
        "xi_se_median": grouped["xi_se"].median(),
        "xi_se_missing_days": grouped["xi_se_missing"].sum(),
        "xi_not_identified_days": grouped["xi_zero_covered"].sum(),
        "var_z_nan": grouped["VaR_GARCH_EVT"].apply(lambda s: int(s.isna().sum())),
    })


if __name__ == "__main__":
    from data_acquisition import fetch_and_cache_data, process_returns
    from config import PRIMARY_CONFIDENCE

    returns_df = process_returns(fetch_and_cache_data())
    elapsed = time.perf_counter()
    result = run_multi_config_walk_forward(
        returns_df["Portfolio"], returns_df.get("VIX"), force=True
    )
    print(f"[Sweep] total wall time {time.perf_counter() - elapsed:.1f}s, "
          f"{result['n_refits']} refits")
    print(summarise_sweep(result["frame"]).to_string())
