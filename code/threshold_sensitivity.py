

"""Profile POT thresholds and compare EVT sensitivity in and out of sample."""
import numpy as np
import pandas as pd

from config import (
    PRIMARY_CONFIDENCE, PRIMARY_POT_THRESHOLD_QUANTILE, POT_THRESHOLD_QUANTILES,
    GARCH_INNOVATION_DISTRIBUTIONS, CONFIDENCE_LEVELS, NOTIONAL_USD,
    ROLLING_WINDOW, validate_pot_configuration,
)
from risk_models import (
    fit_garch11_state, fit_evt_pot_diag, compute_evt_quantiles,
    mean_excess_curve, gpd_mean_excess,
)
from forecast_eval import score_forecasts











MEL_LINEAR_Z_TOL = 2.0
MIN_EXCEEDANCES_FULL_SAMPLE = 100
MEL_GRID_POINTS = 40


MEL_GRID_MIN_EXCEEDANCES = MIN_EXCEEDANCES_FULL_SAMPLE


def garch_innovations(returns, dist="normal", window=None):
    
    """Compute or assemble the garch_innovations result used by the threshold_sensitivity analysis."""
    slice_ = returns if window is None else returns.iloc[:window]
    state = fit_garch11_state(slice_, dist=dist)
    return np.asarray(state["std_resid"], dtype=float), state


def profile_over_thresholds(std_resid, quantiles=POT_THRESHOLD_QUANTILES,
                            confidence_levels=CONFIDENCE_LEVELS,
                            min_exceedances=10):
    
    """Compute or assemble the profile_over_thresholds result used by the threshold_sensitivity analysis."""
    rows = []
    for q in quantiles:
        for alpha in confidence_levels:
            try:
                validate_pot_configuration(q, alpha)
            except ValueError:
                continue
            diag = fit_evt_pot_diag(std_resid, q, min_exceedances=min_exceedances)
            row = dict(diag)
            row["confidence_level"] = float(alpha)

            xi_raw = diag["xi_raw"]
            finite_raw = xi_raw is not None and np.isfinite(xi_raw)
            if diag["degenerate"] or not finite_raw:
                row.update({"var_z": np.nan, "es_z": np.nan,
                            "var_z_raw": np.nan, "es_z_raw": np.nan,
                            "gpd_mean_excess_at_u": np.nan})
            else:
                row["var_z"], row["es_z"] = compute_evt_quantiles(
                    diag["u"], diag["xi_used"], diag["beta"],
                    diag["n_u"], diag["n_tot"], alpha,
                )
                if xi_raw < 1.0:
                    
                    
                    
                    
                    row["var_z_raw"], row["es_z_raw"] = compute_evt_quantiles(
                        diag["u"], xi_raw, diag["beta"],
                        diag["n_u"], diag["n_tot"], alpha,
                    )
                else:
                    row["var_z_raw"] = np.nan
                    row["es_z_raw"] = np.nan
                row["gpd_mean_excess_at_u"] = gpd_mean_excess(
                    diag["u"], diag["xi_used"], diag["beta"]
                )
            rows.append(row)

    columns = ["threshold_quantile", "confidence_level", "u", "n_u", "n_tot",
               "xi_raw", "xi_used", "xi_se", "xi_ci95", "beta", "beta_se",
               "clamped", "clamp_direction", "degenerate", "ks_stat", "ks_pvalue",
               "aic_gpd", "var_z", "es_z", "var_z_raw", "es_z_raw",
               "gpd_mean_excess_at_u"]
    return pd.DataFrame(rows, columns=columns).set_index(
        ["threshold_quantile", "confidence_level"]
    )


def mel_table(std_resid, n_points=MEL_GRID_POINTS,
              min_exceedances=MEL_GRID_MIN_EXCEEDANCES):
    
    """Compute or assemble the mel_table result used by the threshold_sensitivity analysis."""
    losses = -np.asarray(std_resid, dtype=float)
    top_percentile = 100.0 * (1.0 - min_exceedances / len(losses))
    grid = np.percentile(losses, np.linspace(50.0, top_percentile, n_points))

    curve = mean_excess_curve(std_resid, u_grid=grid).rename(
        columns={"mean_excess": "sample_e_hat"}
    )
    curve["implied_quantile"] = [
        float(np.mean(losses <= u)) for u in curve["u"]
    ]

    gpd_e, xi_at, fittable = [], [], []
    for u in curve["u"]:
        diag = fit_evt_pot_diag(std_resid, float(np.mean(losses <= u)))
        xi_at.append(diag["xi_raw"])
        fittable.append(not diag["degenerate"])
        gpd_e.append(np.nan if diag["degenerate"]
                     else gpd_mean_excess(u, diag["xi_used"], diag["beta"]))
    curve["gpd_e_hat"] = gpd_e
    curve["xi_raw_at_u"] = xi_at
    curve["fittable"] = fittable

    return curve.sort_values("u").reset_index(drop=True)


MIN_BAND_POINTS = 4


def linear_mel_band(curve, z_tol=MEL_LINEAR_Z_TOL,
                    min_exceedances=MIN_EXCEEDANCES_FULL_SAMPLE):
    
    """Compute or assemble the linear_mel_band result used by the threshold_sensitivity analysis."""
    usable = curve[(curve["n_exceedances"] >= min_exceedances)
                   & curve["sample_e_hat"].notna()
                   & curve["se_excess"].notna()].sort_values("u").reset_index(drop=True)
    if len(usable) < MIN_BAND_POINTS:
        return None

    u = usable["u"].to_numpy()
    e = usable["sample_e_hat"].to_numpy()
    se = usable["se_excess"].to_numpy()
    n_u = usable["n_exceedances"].to_numpy()
    q_imp = usable["implied_quantile"].to_numpy()
    n = len(u)

    best = None
    for i in range(n):
        for j in range(i + MIN_BAND_POINTS - 1, n):
            band_u, band_e, band_se = u[i:j + 1], e[i:j + 1], se[i:j + 1]
            if np.any(band_se <= 0):
                continue
            slope, intercept = np.polyfit(band_u, band_e, 1)
            deviations = np.abs(band_e - (slope * band_u + intercept)) / band_se
            if float(np.max(deviations)) > z_tol:
                continue
            candidate = {
                "u_lo": float(band_u[0]), "u_hi": float(band_u[-1]),
                "n_points": int(j - i + 1),
                "ols_slope": float(slope), "ols_intercept": float(intercept),
                "mean_level": float(np.mean(band_e)),
                "max_deviation_in_se": float(np.max(deviations)),
                "n_exceedances_at_u_lo": int(n_u[i]),
                "n_exceedances_at_u_hi": int(n_u[j]),
                "implied_quantile_lo": float(q_imp[i]),
                "implied_quantile_hi": float(q_imp[j]),
            }
            if best is None or (candidate["n_points"], candidate["u_lo"]) > (
                    best["n_points"], best["u_lo"]):
                best = candidate

    if best is None:
        return None
    best.update({"z_tolerance": float(z_tol),
                 "min_exceedances": int(min_exceedances),
                 "mel_support_u_lo": float(u[0]), "mel_support_u_hi": float(u[-1]),
                 
                 
                 "band_at_support_edge": bool(abs(best["u_hi"] - float(u[-1])) < 1e-12)})
    return best


def select_threshold(curve, profile, alpha=PRIMARY_CONFIDENCE,
                     production_q=PRIMARY_POT_THRESHOLD_QUANTILE):
    
    """Compute or assemble the select_threshold result used by the threshold_sensitivity analysis."""
    band = linear_mel_band(curve)

    eligible, rejected, all_var = [], [], []
    for q in sorted(profile.index.get_level_values("threshold_quantile").unique()):
        row = profile.loc[(q, alpha)]
        xi_raw = row["xi_raw"]
        xi_se = row["xi_se"]
        finite = xi_raw is not None and np.isfinite(xi_raw)

        reasons = []
        if band is None:
            reasons.append("no near-linear MEL band found on this sample")
        elif row["u"] > band["mel_support_u_hi"]:
            reasons.append(
                f"u above the range over which the mean excess curve keeps "
                f"{MIN_EXCEEDANCES_FULL_SAMPLE} exceedances (top {band['mel_support_u_hi']:.3f})"
            )
        elif not band["u_lo"] <= row["u"] <= band["u_hi"]:
            reasons.append(
                "u inside the curve's measured range but outside its near-linear band "
                f"[{band['u_lo']:.3f}, {band['u_hi']:.3f}]"
            )
        if row["n_u"] < MIN_EXCEEDANCES_FULL_SAMPLE:
            reasons.append(f"n_u={int(row['n_u'])} below {MIN_EXCEEDANCES_FULL_SAMPLE}")
        if not (finite and xi_raw > 0):
            reasons.append("raw shape estimate not positive")

        se_finite = xi_se is not None and np.isfinite(xi_se)
        record = {
            "threshold_quantile": float(q), "u": float(row["u"]),
            "n_u": int(row["n_u"]),
            "xi_raw": float(xi_raw) if finite else None,
            "xi_se": float(xi_se) if se_finite else None,
            
            
            
            "xi_distinguishable_from_zero": bool(
                finite and se_finite and abs(xi_raw) > 1.959963985 * xi_se
            ),
            "clamped": bool(row["clamped"]),
            "var_z": float(row["var_z"]) if np.isfinite(row["var_z"]) else None,
        }
        if np.isfinite(row["var_z"]):
            all_var.append(float(row["var_z"]))
        (rejected if reasons else eligible).append(
            record if not reasons else {**record, "reasons": "; ".join(reasons)}
        )

    grid_spread = (float(max(all_var) - min(all_var)) if len(all_var) > 1 else 0.0)
    grid_spread_pct = float(grid_spread / np.mean(all_var) * 100.0) if all_var else 0.0
    all_records = eligible + rejected
    n_shape_signed = sum(1 for r in all_records if r["xi_distinguishable_from_zero"])

    result = {
        "alpha": float(alpha),
        "band": band,
        "eligible": eligible,
        "rejected": rejected,
        "n_eligible": len(eligible),
        "n_grid": len(eligible) + len(rejected),
        "n_thresholds_whose_shape_is_significant": n_shape_signed,
        "production_q": float(production_q),
        "recommended_q": None,
        "recommended_u": None,
        "production_is_recommended": False,
        "production_eligible": bool(
            production_q in {r["threshold_quantile"] for r in eligible}
        ),
        "var_z_min": min(all_var) if all_var else None,
        "var_z_max": max(all_var) if all_var else None,
        "var_z_spread_across_grid": grid_spread,
        "var_z_spread_across_grid_pct": grid_spread_pct,
    }

    if band is None:
        result["rationale"] = (
            "no contiguous stretch of the sample mean excess curve was linear to "
            f"within {MEL_LINEAR_Z_TOL} standard errors of its own points while "
            f"keeping at least {MIN_EXCEEDANCES_FULL_SAMPLE} exceedances"
        )
        return result

    if not eligible:
        categories = [r.split("(")[0].strip()
                      for item in rejected for r in item["reasons"].split(";")]
        counts = pd.Series(categories).value_counts()
        result["rationale"] = (
            f"no threshold of the {result['n_grid']}-point grid satisfies all four "
            f"criteria. The constraint that bites most often is: "
            f"{counts.index[0]} ({int(counts.iloc[0])} of {result['n_grid']} "
            f"candidates). This is a statement about the sample, not about the grid."
        )
        return result

    recommended = min(eligible, key=lambda r: r["threshold_quantile"])
    eligible_var = [r["var_z"] for r in eligible if r["var_z"] is not None]
    eligible_spread = (float(max(eligible_var) - min(eligible_var))
                       if len(eligible_var) > 1 else 0.0)

    result.update({
        "recommended_q": recommended["threshold_quantile"],
        "recommended_u": recommended["u"],
        "production_is_recommended": bool(
            recommended["threshold_quantile"] == production_q
        ),
        "var_z_spread_across_eligible": eligible_spread,
        "xi_se_min": min((r["xi_se"] for r in eligible if r["xi_se"] is not None),
                         default=None),
        "xi_se_max": max((r["xi_se"] for r in eligible if r["xi_se"] is not None),
                         default=None),
        "rationale": (
            f"{len(eligible)} of {result['n_grid']} grid thresholds satisfy "
            f"linearity, exceedance-count and positive-shape criteria. The lowest is "
            f"q={recommended['threshold_quantile']}, the eligible point with the most "
            f"data behind it. 99% VaR spans {grid_spread:.4f} standardised units "
            f"({grid_spread_pct:.2f}% of its mean) across the whole grid and "
            f"{eligible_spread:.4f} across the eligible subset."
        ),
    })
    return result


def walk_forward_sensitivity_table(sweep_frame, portfolio_returns,
                                   notional=NOTIONAL_USD):
    
    """Compute or assemble the walk_forward_sensitivity_table result used by the threshold_sensitivity analysis."""
    rows = []
    keys = ["innovation_dist", "threshold_q", "confidence_level"]
    for (dist, q, alpha), group in sweep_frame.groupby(keys, sort=True):
        aligned_losses = -portfolio_returns.reindex(group.index).to_numpy(dtype=float)
        scored = score_forecasts(
            aligned_losses, group["VaR_GARCH_EVT"].to_numpy(), alpha,
            es_forecasts=group["ES_GARCH_EVT"].to_numpy(), notional=notional,
        )
        n_days = len(group)
        xi_raw = group["xi_raw"].to_numpy(dtype=float)
        xi_se = group["xi_se"].to_numpy(dtype=float)
        scored.update({
            "innovation_dist": dist,
            "threshold_q": q,
            "confidence_level": alpha,
            "n_u_min": int(group["n_u"].min()),
            "n_u_median": float(group["n_u"].median()),
            "degenerate_days": int(group["degenerate"].sum()),
            "clamped_days": int(group["clamped"].sum()),
            "clamped_share_%": float(group["clamped"].mean() * 100.0),
            "xi_raw_median": float(np.nanmedian(xi_raw)),
            "xi_se_median": float(np.nanmedian(xi_se)),
            "xi_negative_share_%": float(np.nanmean(xi_raw < 0.0) * 100.0),
            
            
            
            "xi_zero_covered_share_%": float(
                np.mean(
                    np.nan_to_num(np.abs(xi_raw) <= 1.959963985 * xi_se, nan=False)
                    | ~np.isfinite(xi_se)
                ) * 100.0
            ),
            "xi_se_missing_share_%": float(
                np.mean(~np.isfinite(xi_se)) * 100.0
            ),
            "n_days_in_sample": n_days,
        })
        rows.append(scored)

    table = pd.DataFrame(rows)
    leading = ["innovation_dist", "threshold_q", "confidence_level"]
    tail = ["n_u_min", "n_u_median", "degenerate_days", "clamped_days",
            "clamped_share_%", "xi_raw_median", "xi_se_median", "xi_negative_share_%",
            "xi_zero_covered_share_%", "xi_se_missing_share_%"]
    middle = [c for c in table.columns
              if c not in leading + tail + ["n_days_in_sample"]]
    return table[leading + middle + tail].set_index(leading)


if __name__ == "__main__":
    from data_acquisition import fetch_and_cache_data, process_returns
    from walkforward_engine import run_multi_config_walk_forward

    returns_df = process_returns(fetch_and_cache_data())
    port = returns_df["Portfolio"]

    for label, window in (("calibration window (first 500 days)", ROLLING_WINDOW),
                          ("full sample (in-sample, descriptive)", None)):
        z, _ = garch_innovations(port, dist="normal", window=window)
        prof = profile_over_thresholds(z)
        curve = mel_table(z)
        choice = select_threshold(curve, prof)
        print(f"\n=== {label}: n={len(z)} ===")
        print(prof[["u", "n_u", "xi_raw", "xi_se", "xi_used", "beta", "clamped",
                    "ks_pvalue", "var_z", "es_z"]].to_string())
        print("band:", choice["band"])
        print(f"recommended q = {choice['recommended_q']} "
              f"(production {choice['production_q']}, production_is_recommended="
              f"{choice['production_is_recommended']}, eligible="
              f"{choice['production_eligible']})")
        print(f"var_z across grid: min={choice['var_z_min']} max={choice['var_z_max']} "
              f"spread={choice['var_z_spread_across_grid']:.4f} "
              f"({choice['var_z_spread_across_grid_pct']:.2f}%)")
        print("rationale:", choice["rationale"])
        for r in choice["rejected"]:
            print(f"  rejected q={r['threshold_quantile']}: {r['reasons']}")

    frame = run_multi_config_walk_forward(port, returns_df.get("VIX"))["frame"]
    table = walk_forward_sensitivity_table(frame, port)
    print("\n=== walk-forward sensitivity (corrected recursion) ===")
    print(table[["Total Obs", "Actual Breaches", "Breach Rate (%)", "Kupiec p-val",
                 "Conditional Cov p-val", "n_u_min", "Mean Excess Loss (%)",
                 "clamped_share_%", "xi_raw_median", "xi_se_median",
                 "xi_negative_share_%", "Breach Rate 95% CI (%)"]].to_string())
