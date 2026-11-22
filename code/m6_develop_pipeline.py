

"""Build the Module 6 metrics manifest and supporting analytical sections."""
import argparse
import datetime as _dt
import json
import os
import time

import numpy as np
import pandas as pd

from config import (
    CONFIDENCE_LEVELS, DATA_DIR, DIRICHLET_SIMULATIONS, GARCH_INNOVATION_DISTRIBUTIONS,
    GARCH_REFIT_INTERVAL, M4_BASELINE_BACKTEST, M6_METRICS_MANIFEST,
    M6_WALK_FORWARD_CACHE, M6_WALK_FORWARD_CACHE_LEGACY, NOTIONAL_USD,
    POT_THRESHOLD_QUANTILES, PRIMARY_CONFIDENCE,
    PRIMARY_GARCH_INNOVATION_DISTRIBUTION, PRIMARY_POT_THRESHOLD_QUANTILE,
    ROLLING_WINDOW, TICKERS, VARIANCE_RECURSION,
)
from data_acquisition import compute_summary_statistics, fetch_and_cache_data, process_returns
from backtester import (
    evaluate_risk_model_performance, run_dirichlet_robustness_test,
    run_walk_forward_backtest, segment_performance_by_regimes,
)
from forecast_eval import score_forecasts
from walkforward_engine import load_multi_config_cache, run_multi_config_walk_forward, slice_config
from threshold_sensitivity import (
    garch_innovations, mel_table, profile_over_thresholds, select_threshold,
    walk_forward_sensitivity_table,
)
import residual_analysis as ra
import regime_segmentation as rs
from regime_segmentation import (
    PORTFOLIO_COLUMN_BALANCED, PORTFOLIO_COLUMN_FROZEN, agreement_table,
    build_regime_frame, cross_tab_with_breach_rates, disagreement_register,
    model_ranking_by_regime, regime_conditional_performance, regime_gap,
    sector_contribution,
)
from economic_impact import (
    concentration, economic_headline, economic_summary, model_economic_comparison,
    registers_by_model, reserve_adequacy, worst_breaches,
)
from tail_metrics import build_breach_register, clopper_pearson
from dynamic_portfolio import (
    book_diagnosis_table, engine_convention_control, run_optimisation,
)
import runtime_benchmark as rb






NULL_MEANINGS = {
    "var_z_raw": ("the unclamped shape estimate is at least 1, where the generalised "
                  "Pareto quantile does not exist; a shape below 1, negative included, "
                  "is reported beside the clamped value"),
    "es_z_raw": ("the unclamped shape estimate is at least 1, where the generalised "
                 "Pareto quantile does not exist"),
    "nu": ("Gaussian innovations have no degrees of freedom to report; this is not a "
           "failed Student-t fit"),
    "filter_nu": ("the fitted filter is Gaussian, so it has no degrees of freedom to "
                  "report"),
    "clamp_direction": ("the shape clamp did not act at this threshold"),
    "Mean Excess Loss (%)": ("no exception in that cell, so there is no excess to "
                             "average; the cell is not missing data"),
    "Median Excess Loss (%)": "no exception in that cell, so there is no excess to average",
    "ES Breaches": ("the model produces a VaR forecast only, so it has no exception "
                    "series of its own to count"),
    "Mean ES (%)": "the model produces a VaR forecast only and no ES forecast",
    "breach_rate_pct": ("the category is empty under this regime definition, so a rate "
                        "has no denominator"),
    "mean_var_pct": "the category is empty under this regime definition",
    "mu": ("the row is a difference between two fits, not a fit; it has no parameters "
           "of its own"),
    "omega": "the row is a difference between two fits, not a fit",
    "alpha": "the row is a difference between two fits, not a fit",
    "beta": "the row is a difference between two fits, not a fit",
    "persistence": "the row is a difference between two fits, not a fit",
    "nobs": "the row is a difference between two fits, not a fit",
    "convergence_flag": "the row is a difference between two fits, not a fit",
    "Reduction (%)": ("the equal-weight forecast ES at this decision date is not "
                      "positive, so a proportional reduction is undefined"),
    "recommended_q": ("no threshold on the grid satisfies linearity, exceedance count "
                      "and a positive shape estimate simultaneously; the absence is the "
                      "result, not a failed lookup"),
    "recommended_u": ("no threshold on the grid satisfies linearity, exceedance count "
                      "and a positive shape estimate simultaneously"),
}


def _field_of(path):
    
    """Compute or assemble the _field_of result used by the m6_develop_pipeline analysis."""
    leaf = path.rsplit(".", 1)[-1]
    return leaf.split("[")[0]


def _explain_nulls(manifest):
    
    """Compute or assemble the _explain_nulls result used by the m6_develop_pipeline analysis."""
    fields = sorted({_field_of(path) for path in manifest["non_finite_paths"]})
    unexplained = [field for field in fields if field not in NULL_MEANINGS]
    if unexplained:
        raise KeyError(
            "the manifest carries a null nobody explained: "
            + ", ".join(unexplained)
            + ". Add it to NULL_MEANINGS with what it means, or fix the section "
              "that produced it.")
    manifest["null_meanings"] = {field: NULL_MEANINGS[field] for field in fields}
    return fields




def _scalar(v, nan_to_none=False):
    
    """Compute or assemble the _scalar result used by the m6_develop_pipeline analysis."""
    if isinstance(v, (np.generic,)):
        v = v.item()
    if isinstance(v, (pd.Timestamp, _dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, np.ndarray):
        return [_scalar(x, nan_to_none) for x in v]
    if isinstance(v, (list, tuple)):
        return [_scalar(x, nan_to_none) for x in v]
    if isinstance(v, dict):
        return {str(k): _scalar(x, nan_to_none) for k, x in v.items()}
    if isinstance(v, (pd.DataFrame, pd.Series)):
        return _scalar(v.to_dict() if isinstance(v, pd.Series)
                       else v.reset_index().to_dict("records"), nan_to_none)
    if isinstance(v, float) and not np.isfinite(v):
        
        
        return None if nan_to_none else v
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    return str(v)


def to_jsonable(obj, nan_to_none=False):
    """Compute or assemble the to_jsonable result used by the m6_develop_pipeline analysis."""
    return _scalar(obj, nan_to_none)


def _find_non_finite(node, path="$", hits=None):
    
    """Compute or assemble the _find_non_finite result used by the m6_develop_pipeline analysis."""
    if hits is None:
        hits = []
    if node is None or (isinstance(node, float) and not np.isfinite(node)):
        hits.append(path)
    elif isinstance(node, dict):
        for key, value in node.items():
            _find_non_finite(value, f"{path}.{key}", hits)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _find_non_finite(value, f"{path}[{i}]", hits)
    return hits


def _cached(ctx, key, factory):
    """Compute or assemble the _cached result used by the m6_develop_pipeline analysis."""
    if key not in ctx:
        ctx[key] = factory()
    return ctx[key]


def _load_sweeps(ctx):
    """Compute or assemble the _load_sweeps result used by the m6_develop_pipeline analysis."""
    def build():
        """Compute or assemble the build result used by the m6_develop_pipeline analysis."""
        try:
            return load_multi_config_cache()
        except FileNotFoundError:
            out = {}
            for variant, path in (("corrected", M6_WALK_FORWARD_CACHE),
                                  ("legacy", M6_WALK_FORWARD_CACHE_LEGACY)):
                out[variant] = run_multi_config_walk_forward(
                    ctx["portfolio"], ctx["vix"], variance_recursion=variant,
                    cache_path=path)["frame"]
            return out
    return _cached(ctx, "sweeps", build)


def _primary_slice(ctx, recursion):
    
    """Compute or assemble the _primary_slice result used by the m6_develop_pipeline analysis."""
    def build():
        """Compute or assemble the build result used by the m6_develop_pipeline analysis."""
        frame = _load_sweeps(ctx)[recursion]
        sub = slice_config(frame, PRIMARY_GARCH_INNOVATION_DISTRIBUTION,
                           PRIMARY_POT_THRESHOLD_QUANTILE, PRIMARY_CONFIDENCE)
        sub["Loss"] = ctx["baseline"]["Loss"].reindex(sub.index).to_numpy()
        sub["Return"] = ctx["baseline"]["Return"].reindex(sub.index).to_numpy()
        return sub
    return _cached(ctx, f"primary_{recursion}", build)




def section_data(ctx):
    """Compute or assemble the section_data result used by the m6_develop_pipeline analysis."""
    returns = ctx["returns_df"]
    n_test = len(ctx["portfolio"]) - ROLLING_WINDOW
    observed_refits = int(_load_sweeps(ctx)["corrected"]
                          .groupby(["innovation_dist", "threshold_q",
                                    "confidence_level"])["u"].nunique().iloc[0])
    stats = compute_summary_statistics(ctx["portfolio"])
    return {
        "universe": list(TICKERS),
        "n_assets": len(TICKERS),
        "benchmark": "SPY",
        "price_rows": int(len(returns)),
        "first_date": returns.index[0].date().isoformat(),
        "last_date": returns.index[-1].date().isoformat(),
        "columns": list(returns.columns),
        "walk_forward_days": int(len(ctx["baseline"])),
        "window": ROLLING_WINDOW,
        "refit_interval": GARCH_REFIT_INTERVAL,
        "refits_expected": int(-(-n_test // GARCH_REFIT_INTERVAL)),
        "refits_observed_in_cache": observed_refits,
        "confidence_levels": list(CONFIDENCE_LEVELS),
        "threshold_quantiles": list(POT_THRESHOLD_QUANTILES),
        "innovation_distributions": list(GARCH_INNOVATION_DISTRIBUTIONS),
        "notional_usd": NOTIONAL_USD,
        "portfolio_statistics": stats,
        "data_limitations": {
            "close_only": True,
            "volume_available": False,
            "consequence": ("Liquidity-adjusted stress and any volume-based "
                            "threshold were descoped: the cached panel carries "
                            "closing prices, a benchmark and the VIX only."),
            "survivorship": ("All twenty names are 2024 constituents, so the "
                             "sample excludes delisted and merged firms."),
        },
    }


def _read_table(path):
    
    """Compute or assemble the _read_table result used by the m6_develop_pipeline analysis."""
    return pd.read_csv(path).rename(columns={"Unnamed: 0": "metric"})


def section_runtime(ctx):
    
    """Compute or assemble the section_runtime result used by the m6_develop_pipeline analysis."""
    if not os.path.exists(rb.BENCH_CACHE_MODEL_COSTS):
        payload = rb.run_runtime_benchmarks(ctx["portfolio"])
    else:
        payload = {}
    env = {}
    if os.path.exists(rb.BENCH_CACHE_ENVIRONMENT):
        with open(rb.BENCH_CACHE_ENVIRONMENT) as handle:
            env = json.load(handle)
    return {
        "measured_by": "python runtime_benchmark.py",
        "environment": env,
        "model_costs": _read_table(rb.BENCH_CACHE_MODEL_COSTS) if os.path.exists(
            rb.BENCH_CACHE_MODEL_COSTS) else payload.get("model_costs"),
        "refit_cadence": _read_table(rb.BENCH_CACHE_CADENCE) if os.path.exists(
            rb.BENCH_CACHE_CADENCE) else payload.get("cadence"),
        "sweep_sharing": _read_table(rb.BENCH_CACHE_SHARING) if os.path.exists(
            rb.BENCH_CACHE_SHARING) else payload.get("sharing"),
        "caution": ("Per-calibration cost is not the quantity a practitioner pays. "
                    "Amortised cost is, and it is set by the refit cadence, not by "
                    "the price of one fit."),
    }


def section_recursion(ctx):
    
    """Compute or assemble the section_recursion result used by the m6_develop_pipeline analysis."""
    baseline = ctx["baseline"]
    frames = {recursion: _cached(ctx, f"wf_{recursion}",
                                 lambda r=recursion: run_walk_forward_backtest(
                                     ctx["portfolio"], ctx["vix"],
                                     confidence_level=PRIMARY_CONFIDENCE,
                                     window=ROLLING_WINDOW, variance_recursion=r))
              for recursion in ("legacy", "corrected")}

    m4_columns = ["Return", "Loss", "VaR_Normal", "VaR_Historical",
                  "VaR_GARCH_EVT", "ES_GARCH_EVT"]
    diffs = {}
    for column in m4_columns:
        diffs[column] = float(np.max(np.abs(
            frames["legacy"][column].to_numpy() - baseline[column].to_numpy())))

    per_recursion = {}
    for recursion, frame in frames.items():
        perf = evaluate_risk_model_performance(frame, PRIMARY_CONFIDENCE)
        per_recursion[recursion] = {
            "exceptions": int((frame["Loss"] > frame["VaR_GARCH_EVT"]).sum()),
            "score": perf["VaR_GARCH_EVT"],
            "es_score": perf["ES_GARCH_EVT"],
            "other_models": {model: perf[model] for model in
                             ("VaR_Normal", "VaR_Historical")},
        }
    return {
        "primary_recursion": VARIANCE_RECURSION,
        "m4_reproduction": {
            "baseline_artefact": os.path.relpath(M4_BASELINE_BACKTEST, os.getcwd()),
            "max_abs_difference": max(diffs.values()),
            "per_column_difference": diffs,
            "published_exceptions": int((baseline["Loss"]
                                         > baseline["VaR_GARCH_EVT"]).sum()),
            "reproduced": bool(max(diffs.values()) < 1e-12),
        },
        "sensitivity": per_recursion,
        "difference": {
            "exceptions_legacy_minus_corrected": (
                per_recursion["legacy"]["exceptions"]
                - per_recursion["corrected"]["exceptions"]),
            "identical_across_recursions": [
                column for column in ("VaR_Normal", "VaR_Historical")
                if np.allclose(frames["legacy"][column], frames["corrected"][column])],
        },
    }


def section_headline(ctx):
    
    """Compute or assemble the section_headline result used by the m6_develop_pipeline analysis."""
    baseline = ctx["baseline"]
    perf = evaluate_risk_model_performance(baseline, PRIMARY_CONFIDENCE)
    x = int((baseline["Loss"] > baseline["VaR_GARCH_EVT"]).sum())
    n = int(len(baseline))
    low, high = clopper_pearson(x, n, 0.05)
    corrected = _primary_slice(ctx, "corrected")
    score_corrected = score_forecasts(corrected["Loss"].to_numpy(),
                                      corrected["VaR_GARCH_EVT"].to_numpy(),
                                      PRIMARY_CONFIDENCE,
                                      es_forecasts=corrected["ES_GARCH_EVT"].to_numpy())
    return {
        "confidence_level": PRIMARY_CONFIDENCE,
        "module4_performance_summary": perf,
        "module4_regime_summary": segment_performance_by_regimes(baseline, PRIMARY_CONFIDENCE),
        "module4_exact_interval": {
            "exceptions": x, "observations": n, "rate_pct": x / n * 100.0,
            "ci_pct": [low * 100.0, high * 100.0],
            "nominal_inside": bool(low <= 1.0 - PRIMARY_CONFIDENCE <= high),
            "wald_interval_would_be": [
                (x / n - 1.96 * np.sqrt(x / n * (1 - x / n) / n)) * 100.0,
                (x / n + 1.96 * np.sqrt(x / n * (1 - x / n) / n)) * 100.0],
        },
        "module6_primary": score_corrected,
    }


def section_threshold(ctx):
    
    """Compute or assemble the section_threshold result used by the m6_develop_pipeline analysis."""
    out = {"per_innovation": {}, "grid": list(POT_THRESHOLD_QUANTILES),
           "production_q": PRIMARY_POT_THRESHOLD_QUANTILE}
    for dist in GARCH_INNOVATION_DISTRIBUTIONS:
        per_window = {}
        for label, window in (("calibration_window", ROLLING_WINDOW),
                              ("full_sample", None)):
            z, meta = garch_innovations(ctx["portfolio"], dist=dist, window=window)
            profile = profile_over_thresholds(z)
            curve = mel_table(z)
            choice = select_threshold(curve, profile, alpha=PRIMARY_CONFIDENCE)
            per_window[label] = {
                "n_innovations": int(len(z)),
                "fit": {k: v for k, v in meta.items()
                        if k not in ("cond_vol", "std_resid")},
                "profile": profile,
                "mel_curve": curve,
                "selection": choice,
            }
        out["per_innovation"][dist] = per_window

    sweep = _load_sweeps(ctx)["corrected"]
    out["walk_forward_sensitivity"] = walk_forward_sensitivity_table(
        sweep, ctx["portfolio"], notional=NOTIONAL_USD)
    out["walk_forward_sensitivity_legacy"] = walk_forward_sensitivity_table(
        _load_sweeps(ctx)["legacy"], ctx["portfolio"], notional=NOTIONAL_USD)
    primary = out["per_innovation"][PRIMARY_GARCH_INNOVATION_DISTRIBUTION]
    out["recommendation"] = {
        "from_calibration_window": primary["calibration_window"]["selection"],
        "from_full_sample": primary["full_sample"]["selection"],
    }
    return out


def section_iid(ctx):
    
    """Compute or assemble the section_iid result used by the m6_develop_pipeline analysis."""
    portfolio = ctx["portfolio"]
    diagnostics = ra.innovation_diagnostics_table(portfolio)
    walk_forward = ra.walk_forward_filter_table(_load_sweeps(ctx)["corrected"], portfolio,
                                                confidence_level=PRIMARY_CONFIDENCE,
                                                notional=NOTIONAL_USD)
    return {
        "residual_diagnostics": diagnostics,
        "iid_verdict": ra.iid_verdict(diagnostics),
        "filter_parameters": ra.filter_parameter_table(portfolio),
        "evt_across_filters": ra.evt_across_filters_table(portfolio),
        "walk_forward_filter_table": walk_forward,
        "normal_minus_t": ra.filter_difference_summary(walk_forward),
    }


def section_regime(ctx):
    
    """Compute or assemble the section_regime result used by the m6_develop_pipeline analysis."""
    frame, cut_points = build_regime_frame(ctx["returns_df"])
    sweep = _load_sweeps(ctx)["corrected"]
    tab11, joined = cross_tab_with_breach_rates(frame, sweep)
    gap = regime_gap(joined)
    stressed_calm = gap.index[gap >= 2]
    ranking = {column: model_ranking_by_regime(ctx["baseline"], sweep, frame,
                                               portfolio_column=column)
               for column in (PORTFOLIO_COLUMN_BALANCED, PORTFOLIO_COLUMN_FROZEN)}
    return {
        "cut_points": cut_points,
        "agreement": {column: agreement_table(frame, portfolio_column=column)
                      for column in (PORTFOLIO_COLUMN_FROZEN, PORTFOLIO_COLUMN_BALANCED)},
        "cross_tab_with_breach_rates": tab11,
        "regime_conditional_performance": regime_conditional_performance(frame, sweep,
                                                                         notional=NOTIONAL_USD),
        "disagreement": {column: disagreement_register(joined, portfolio_column=column)
                         for column in (PORTFOLIO_COLUMN_BALANCED, PORTFOLIO_COLUMN_FROZEN)},
        "stressed_but_calm": {
            "n_days": int(len(stressed_calm)),
            "sector_contribution": sector_contribution(ctx["returns_df"], stressed_calm),
            "years": {int(k): int(v) for k, v in
                      pd.Series([d.year for d in stressed_calm]).value_counts().sort_index().items()},
        },
        "model_ranking": ranking,
    }


def section_economic(ctx):
    
    """Compute or assemble the section_economic result used by the m6_develop_pipeline analysis."""
    baseline = ctx["baseline"]
    comparison = model_economic_comparison(baseline, notional=NOTIONAL_USD)
    registers = registers_by_model(baseline, notional=NOTIONAL_USD)

    
    
    
    published_path = os.path.join(DATA_DIR, "m4_breach_register_garch_evt.csv")
    registers["GARCH-EVT"].to_csv(published_path)
    primary = _primary_slice(ctx, "corrected")
    primary_register = build_breach_register(
        primary.index, primary["Loss"].to_numpy(), primary["VaR_GARCH_EVT"].to_numpy(),
        returns=primary["Return"].to_numpy(),
        es_forecasts=primary["ES_GARCH_EVT"].to_numpy(), notional=NOTIONAL_USD)
    register_path = os.path.join(DATA_DIR, "m6_breach_register_garch_evt.csv")
    primary_register.to_csv(register_path)

    blocks = {}
    for recursion in ("legacy", "corrected"):
        frame = _primary_slice(ctx, recursion)
        losses = frame["Loss"].to_numpy()
        var = frame["VaR_GARCH_EVT"].to_numpy()
        es = frame["ES_GARCH_EVT"].to_numpy()
        summary = economic_summary(losses, var, PRIMARY_CONFIDENCE, NOTIONAL_USD,
                                   es_forecasts=es, returns=frame["Return"].to_numpy(),
                                   label=f"GARCH-EVT ({recursion})")
        adequacy = reserve_adequacy(losses, var, es, PRIMARY_CONFIDENCE, NOTIONAL_USD)
        blocks[recursion] = {
            "summary": summary,
            "reserve_adequacy": adequacy,
            "headlines": economic_headline(summary, adequacy, notional=NOTIONAL_USD),
        }
    return {
        "model_comparison": comparison,
        "registers": {name: {"n_exceptions": int(len(reg)),
                             "concentration": concentration(reg)}
                      for name, reg in registers.items()},
        "worst_ten": worst_breaches(primary_register, 10),
        "primary_register_concentration": concentration(primary_register),
        "full_register_path": os.path.relpath(register_path, os.getcwd()),
        "published_register_path": os.path.relpath(published_path, os.getcwd()),
        "full_register_rows": int(len(primary_register)),
        "published_register_rows": int(len(registers["GARCH-EVT"])),
        "by_recursion": blocks,
        "stock_versus_flow": ("Incremental capital is a level held at every mark; "
                              "unreserved loss is a total realised only on breach days. "
                              "They are reported side by side and never added."),
    }


def section_optimisation(ctx):
    
    """Compute or assemble the section_optimisation result used by the m6_develop_pipeline analysis."""
    out = _cached(ctx, "optimisation", lambda: run_optimisation(
        returns_df=ctx["returns_df"], write_cache=True))
    reduction = out["es_reduction"]
    summary = (reduction.groupby("alpha")["Reduction (%)"].agg(["mean", "median", "min", "max"])
               if reduction is not None and len(reduction) else None)

    
    
    
    paths = []
    for name, book in out["books"].items():
        risk = out["risk_frames"][name]
        frame = book.join(risk[["VaR_GARCH_EVT", "ES_GARCH_EVT"]], how="left")
        frame.insert(0, "Strategy", name)
        frame.index.name = "Date"
        paths.append(frame.reset_index())
    paths_frame = pd.concat(paths, ignore_index=True)
    paths_path = os.path.join(DATA_DIR, "m6_optimisation_paths.csv")
    paths_frame.to_csv(paths_path, index=False)

    return {
        "universe": out["tickers"],
        "strategies": list(out["table"].index),
        "table": out["table"],
        "concentration": out["concentration"],
        "failed_solves": int(len(out["failures"])),
        "failure_records": out["failures"] if len(out["failures"]) else [],
        "mean_off_diagonal_correlation": out["mean_off_diagonal_correlation"],
        "forecast_es_reduction_by_alpha": summary,
        "forecast_es_reduction_path": os.path.relpath(paths_path, os.getcwd()),
        "forecast_es_reduction_records": reduction,
        "engine_convention_control": engine_convention_control(out),
        "book_diagnosis": book_diagnosis_table(out),
        "breach_date_agreement": out["breach_date_agreement"],
        "weight_history_rows": int(sum(len(f) for f in out["schedules"].values())),
        "comparability_warning": ("Breach counts across two books are not a model "
                                  "comparison: they price different loss series. "
                                  "Calibration is read within a row, risk reduction "
                                  "across rows."),
    }


def section_optimisation_control(ctx):
    
    """Compute or assemble the section_optimisation_control result used by the m6_develop_pipeline analysis."""
    out = run_optimisation(returns_df=ctx["returns_df"], quick=True, write_cache=False)
    return {
        "universe": out["tickers"],
        "n_assets": len(out["tickers"]),
        "table": out["table"],
        "concentration": out["concentration"],
        "reason": ("The names are chosen by letter, not by anything the optimiser "
                   "could exploit, so a result that survives this cut is not an "
                   "artefact of which survivors are in the sample."),
    }


def section_weight_robustness(ctx):
    
    """Compute or assemble the section_weight_robustness result used by the m6_develop_pipeline analysis."""
    res = run_dirichlet_robustness_test(ctx["returns_df"], TICKERS,
                                        n_simulations=DIRICHLET_SIMULATIONS,
                                        confidence_level=PRIMARY_CONFIDENCE)
    out = {"simulations": DIRICHLET_SIMULATIONS, "in_sample": True,
           "models": {}}
    for key, rates in res.items():
        arr = np.asarray(rates, dtype=float)
        out["models"][key] = {"mean_pct": float(arr.mean()), "std_pct": float(arr.std()),
                              "min_pct": float(arr.min()), "max_pct": float(arr.max()),
                              "p5_pct": float(np.percentile(arr, 5)),
                              "p95_pct": float(np.percentile(arr, 95))}
    out["tautology"] = ("Historical VaR is the empirical quantile of the same window "
                        "it is scored on, so its breach rate is pinned near the "
                        "nominal one for every weight vector. The spread that matters "
                        "is zero, and the figure labels this test full-sample.")
    return out


def section_pointers(ctx):
    
    """Compute or assemble the section_pointers result used by the m6_develop_pipeline analysis."""
    return {
        "Table 1": "static in the report generator (reviewer response matrix)",
        "Table 2": "static in the report generator (revised objectives)",
        "Table 3": "static in the report generator (milestone schedule)",
        "Table 4": "static in the report generator (remaining tasks)",
        "Table 5": "static in the report generator (risk registry)",
        "Table 6": "module4_metrics_manifest.json > summary_stats and spy_stats",
        "Table 7": "module4_metrics_manifest.json > perf_summary",
        "Table 8": "headline.module4_regime_summary",
        "Table 9": "weight_robustness.models",
        "Table 10": "threshold.per_innovation.<innovation>.full_sample.profile",
        "Table 11": "threshold.walk_forward_sensitivity",
        "Table 12": "iid.residual_diagnostics",
        "Table 13": "iid.normal_minus_t",
        "Table 14": "regime.cross_tab_with_breach_rates",
        "Table 15": "regime.regime_conditional_performance",
        "Table 16": "economic.model_comparison",
        "Table 17": "economic.by_recursion.<recursion>.reserve_adequacy",
        "Table 18": "optimisation.table",
        "Table 19": "optimisation.engine_convention_control",
        "Table 20": "optimisation.book_diagnosis",
        "Table 21": "runtime.model_costs",
        "Table 22": "runtime.refit_cadence",
        "Table 23": "runtime.sweep_sharing",
        "Table 24": "economic.full_register_path",
        "Table 25": "optimisation.concentration",
        "Table 26": "static in the report generator (appendix E traceability matrix)",
        "Table 27": "runtime.environment",
        "Figures 1-5": "module4_metrics_manifest.json, carried from the proposal",
        "Figure 6": "threshold.per_innovation.<innovation>.full_sample.profile",
        "Figure 7": "threshold.walk_forward_sensitivity",
        "Figure 8": "iid.residual_diagnostics",
        "Figure 9": "iid.normal_minus_t",
        "Figure 10": "regime.cross_tab_with_breach_rates",
        "Figure 11": "economic.worst_ten and economic.by_recursion",
        "Figure 12": "optimisation.table",
        "Figure 13": "optimisation.forecast_es_reduction_by_alpha",
        "Figure 14": "runtime.model_costs and runtime.refit_cadence",
    }


SECTIONS = [
    ("data", section_data),
    ("runtime", section_runtime),
    ("recursion", section_recursion),
    ("headline", section_headline),
    ("threshold", section_threshold),
    ("iid", section_iid),
    ("regime", section_regime),
    ("economic", section_economic),
    ("optimisation", section_optimisation),
    ("optimisation_control", section_optimisation_control),
    ("weight_robustness", section_weight_robustness),
    ("report_table_pointers", section_pointers),
]


def build_context():
    """Compute or assemble the build_context result used by the m6_develop_pipeline analysis."""
    returns_df = process_returns(fetch_and_cache_data())
    return {
        "returns_df": returns_df,
        "portfolio": returns_df["Portfolio"],
        "vix": returns_df["VIX"],
        "baseline": pd.read_csv(M4_BASELINE_BACKTEST, index_col=0, parse_dates=True),
    }


def run_module6_pipeline(force=False, only=None, write_manifest=True,
                         verbose=True):
    
    """Compute or assemble the run_module6_pipeline result used by the m6_develop_pipeline analysis."""
    t_start = time.perf_counter()
    ctx = build_context()
    names = [name for name, _ in SECTIONS]
    selected = names if not only else [n for n in names if n in only.split(",")]

    manifest = {}
    
    
    
    if os.path.exists(M6_METRICS_MANIFEST) and not force:
        with open(M6_METRICS_MANIFEST) as handle:
            manifest = json.load(handle)

    manifest["generated_at"] = datetime_now()
    manifest["config"] = {
        "confidence_level": PRIMARY_CONFIDENCE,
        "threshold_quantile": PRIMARY_POT_THRESHOLD_QUANTILE,
        "innovation_distribution": PRIMARY_GARCH_INNOVATION_DISTRIBUTION,
        "variance_recursion": VARIANCE_RECURSION,
        "window": ROLLING_WINDOW,
        "refit_interval": GARCH_REFIT_INTERVAL,
    }
    timings = dict(manifest.get("section_timings_s", {}))
    
    
    non_finite = dict(manifest.get("section_non_finite", {}))
    for name, function in SECTIONS:
        if name not in selected:
            continue
        if verbose:
            print(f"\n[{name}] ", end="", flush=True)
        t0 = time.perf_counter()
        try:
            computed = to_jsonable(function(ctx))
        except Exception as error:  
            print(f"FAILED: {type(error).__name__}: {error}")
            raise
        non_finite[name] = _find_non_finite(computed, path=f"$.{name}")
        manifest[name] = _scalar(computed, nan_to_none=True)
        timings[name] = time.perf_counter() - t0
        if verbose:
            print(f"done in {timings[name]:.1f}s"
                  f"  ({len(non_finite[name])} non-finite)")

    manifest["section_timings_s"] = timings
    manifest["total_time_s"] = time.perf_counter() - t_start
    
    
    
    
    body = {key: value for key, value in manifest.items()
            if key not in ("non_finite_paths", "section_non_finite", "null_meanings")}
    manifest["non_finite_paths"] = sorted(_find_non_finite(body))
    manifest["section_non_finite"] = {}
    for path in manifest["non_finite_paths"]:
        section = path.split(".")[1].split("[")[0]
        manifest["section_non_finite"].setdefault(section, []).append(path)
    _explain_nulls(manifest)
    manifest["nan_policy"] = (
        "A NaN or a missing value is written as null and listed in non_finite_paths, "
        "with its meaning in null_meanings, so the file is valid JSON for any tool and "
        "nothing silent is hidden. The report build refuses to render a null that is "
        "not accounted for here.")

    all_non_finite = manifest["non_finite_paths"]
    if verbose:
        print(f"\n{'=' * 78}\n  sections: {len(selected)}/{len(names)}   "
              f"total {manifest['total_time_s']:.0f}s   "
              f"non-finite values: {len(all_non_finite)}")
        for path in all_non_finite[:20]:
            print(f"    {path}")
        print("=" * 78)

    
    
    manifest = _scalar(manifest, nan_to_none=True)
    if write_manifest:
        with open(M6_METRICS_MANIFEST, "w") as handle:
            json.dump(manifest, handle, indent=2, default=str, allow_nan=False)
        if verbose:
            print(f"  manifest written to {M6_METRICS_MANIFEST}")
    return manifest


def datetime_now():
    """Compute or assemble the datetime_now result used by the m6_develop_pipeline analysis."""
    return _dt.datetime.now().isoformat(timespec="seconds")


def _show(value, spec="{:.4f}"):
    
    """Compute or assemble the _show result used by the m6_develop_pipeline analysis."""
    if value is None:
        return "not run"
    if isinstance(value, float) and not np.isfinite(value):
        return "n/a"
    try:
        return spec.format(value)
    except (TypeError, ValueError):
        return str(value)


def print_summary(manifest):
    """Compute or assemble the print_summary result used by the m6_develop_pipeline analysis."""
    headline = manifest.get("headline", {}).get("module6_primary", {})
    recursion = manifest.get("recursion", {})
    reproduction = recursion.get("m4_reproduction", {})
    sensitivity = recursion.get("sensitivity", {})
    threshold = manifest.get("threshold", {})
    recommendation = threshold.get("recommendation", {}).get("from_calibration_window", {})
    print("\n--- Module 6 pipeline summary ---")
    print(f"  primary recursion      : {recursion.get('primary_recursion', 'not run')}")
    print(f"  M4 reproduction diff   : "
          f"{_show(reproduction.get('max_abs_difference'), '{:.3e}')} "
          f" reproduced={reproduction.get('reproduced', 'not run')}")
    print(f"  exceptions (leg/corr)  : "
          f"{sensitivity.get('legacy', {}).get('exceptions', '-')}"
          f" / {sensitivity.get('corrected', {}).get('exceptions', '-')}")
    print(f"  primary breach rate    : "
          f"{_show(headline.get('Breach Rate (%)'), '{:.3f}')}% "
          f"Kupiec p={_show(headline.get('Kupiec p-val'))} "
          f"CC p={_show(headline.get('Conditional Cov p-val'))}")
    window_choice = recommendation.get("recommended_q")
    full_choice = (threshold.get("recommendation", {})
                   .get("from_full_sample", {}).get("recommended_q"))
    print(f"  recommended threshold  : "
          f"{'none defensible in a 500-day window' if window_choice is None else window_choice}"
          f" in-window, {full_choice} full-sample "
          f"(production {recommendation.get('production_q', '-')}, "
          f"agrees={recommendation.get('production_is_recommended', '-')})")
    optimisation = manifest.get("optimisation", {})
    table = optimisation.get("table") or []
    if isinstance(table, list) and table:
        by_name = {row["Strategy"]: row for row in table}
        for name in ("Equal weight (rebalanced)", "Minimum ES"):
            row = by_name.get(name)
            if row:
                print(f"  {name:26s}  vol="
                      f"{_show(row.get('Ann volatility (%)'), '{:.2f}')}% "
                      f"ES={_show(row.get('Mean ES (%)'), '{:.3f}')}% "
                      f"breaches={row.get('Actual Breaches', '-')} "
                      f"Kupiec p={_show(row.get('Kupiec p'))}")
        agreement = optimisation.get("breach_date_agreement") or []
        if agreement:
            worst = max(agreement, key=lambda r: r["Jaccard"] if r["Jaccard"] is not None else -1)
            print(f"  identical exception days: "
                  f"{worst['Book A']} == {worst['Book B']} "
                  f"({worst['Shared exception days']}/{worst['Breaches A']})")
    print(f"  non-finite values      : {len(manifest.get('non_finite_paths', []))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true",
                        help="recompute every section, ignoring the manifest on disk")
    parser.add_argument("--only", default=None,
                        help="comma-separated section names, e.g. threshold,iid")
    parser.add_argument("--no-write", action="store_true",
                        help="compute and report without touching the manifest file")
    args = parser.parse_args()
    result = run_module6_pipeline(force=args.force, only=args.only,
                                  write_manifest=not args.no_write)
    print_summary(result)
