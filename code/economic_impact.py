

import numpy as np
import pandas as pd

from config import (
    NOTIONAL_USD, PRIMARY_CONFIDENCE, CLOPPER_PEARSON_ALPHA, M4_BASELINE_BACKTEST,
)
from tail_metrics import (
    build_breach_register, clopper_pearson, describe_excess_losses,
)


def economic_summary(losses, var_forecasts, confidence_level=PRIMARY_CONFIDENCE,
                     notional=NOTIONAL_USD, es_forecasts=None, returns=None,
                     label="GARCH-EVT"):
    
    losses = np.asarray(losses, dtype=float)
    var_forecasts = np.asarray(var_forecasts, dtype=float)
    keep = ~np.isnan(var_forecasts) & ~np.isnan(losses)
    scored_losses = losses[keep]
    scored_var = var_forecasts[keep]
    n_obs = int(scored_losses.size)
    breaches = scored_losses > scored_var
    x = int(breaches.sum())

    low, high = clopper_pearson(x, n_obs, CLOPPER_PEARSON_ALPHA)
    nominal = 1.0 - confidence_level
    excess = scored_losses[breaches] - scored_var[breaches]
    severity = describe_excess_losses(excess, notional)
    es = None if es_forecasts is None else np.asarray(es_forecasts, dtype=float)[keep]

    out = {
        "Model": label,
        "Total Obs": n_obs,
        "Actual Breaches": x,
        "Expected Breaches": n_obs * nominal,
        "Breach Rate (%)": x / n_obs * 100.0 if n_obs else 0.0,
        "Nominal Rate (%)": nominal * 100.0,
        "Breach Rate 95% CI (%)": (low * 100.0, high * 100.0),
        "Nominal Inside 95% CI": bool(low <= nominal <= high),
        "Mean Excess Loss (%)": severity["mean_pct"],
        "Median Excess Loss (%)": severity["median_pct"],
        "Max Excess Loss (%)": severity["max_pct"],
        "Mean Excess (USD)": severity["mean_notional"],
        "Max Excess (USD)": severity["max_notional"],
        "Cumulative Unreserved Loss (USD)": severity["total_notional"],
        "Cumulative Unreserved Loss (% of notional)": severity["total_pct"],
        "Mean VaR (%)": float(scored_var.mean() * 100.0) if n_obs else 0.0,
        "Total Loss on Breach Days (%)": float(scored_losses[breaches].sum() * 100.0),
    }
    if es is not None:
        out["ES Breaches"] = int((scored_losses > es).sum())
        out["Mean ES (%)"] = float(es.mean() * 100.0) if n_obs else 0.0
    return out


def worst_breaches(register, n=10):
    
    return register.head(n).copy()


def concentration(register, top_k=(1, 5, 10)):
    
    total = float(register["USD_Excess"].sum())
    out = {"total_usd_excess": total, "n_breaches": int(len(register))}
    if total <= 0 or register.empty:
        out.update({f"top_{k}_share_pct": np.nan for k in top_k})
        return out
    ordered = register["USD_Excess"].sort_values(ascending=False)
    for k in top_k:
        out[f"top_{k}_share_pct"] = float(ordered.head(k).sum() / total * 100.0)
    out["largest_single_usd"] = float(ordered.iloc[0])
    out["hhi_of_excess"] = float(((ordered / total) ** 2).sum())
    return out


def reserve_adequacy(losses, var_forecasts, es_forecasts,
                     confidence_level=PRIMARY_CONFIDENCE, notional=NOTIONAL_USD):
    
    losses = np.asarray(losses, dtype=float)
    var = np.asarray(var_forecasts, dtype=float)
    es = np.asarray(es_forecasts, dtype=float)
    keep = ~np.isnan(var) & ~np.isnan(es) & ~np.isnan(losses)
    losses, var, es = losses[keep], var[keep], es[keep]
    n = int(losses.size)
    years = n / 252.0 if n else np.nan

    var_short = np.maximum(losses - var, 0.0)
    es_short = np.maximum(losses - es, 0.0)
    premium = es - var
    breach = losses > var

    unreserved_var = float(var_short.sum() * notional)
    unreserved_es = float(es_short.sum() * notional)
    incremental_capital = float(premium.mean() * notional) if n else 0.0

    return {
        "Total Obs": n,
        "Years": years,
        "Mean VaR (%)": float(var.mean() * 100.0),
        "Mean ES (%)": float(es.mean() * 100.0),
        "Mean VaR Reserve (USD)": float(var.mean() * notional) if n else 0.0,
        "Mean ES Reserve (USD)": float(es.mean() * notional) if n else 0.0,
        "Incremental Capital Held (USD)": incremental_capital,
        "Incremental Capital (% of notional)": float(premium.mean() * 100.0) if n else 0.0,
        "ES Reserve Uplift over VaR (%)": (
            float(premium.mean() / var.mean() * 100.0) if n and var.mean() > 0 else np.nan),
        "Cumulative Unreserved under VaR (USD)": unreserved_var,
        "Cumulative Unreserved under ES (USD)": unreserved_es,
        "Unreserved Loss Avoided by ES (USD)": unreserved_var - unreserved_es,
        "Unreserved Loss Avoided per Year (USD)": (
            (unreserved_var - unreserved_es) / years if years else np.nan),
        "Avoided Shortfall per Dollar of Extra Capital": (
            (unreserved_var - unreserved_es) / incremental_capital
            if incremental_capital > 0 else np.nan),
        "ES Absorbs All VaR Shortfall": bool(es_short.sum() == 0.0),
        "Days ES Also Breached": int((losses > es).sum()),
        "Share of VaR Breaches Also ES Breaches (%)": (
            float((losses[breach] > es[breach]).sum() / breach.sum() * 100.0)
            if breach.any() else np.nan),
        "Largest Unreserved Day under VaR (USD)": float(var_short.max() * notional)
        if n else 0.0,
        "Largest Unreserved Day under ES (USD)": float(es_short.max() * notional)
        if n else 0.0,
    }


def model_economic_comparison(baseline_frame=None,
                              confidence_level=PRIMARY_CONFIDENCE,
                              notional=NOTIONAL_USD):
    
    if baseline_frame is None:
        baseline_frame = pd.read_csv(M4_BASELINE_BACKTEST, index_col=0, parse_dates=True)
    rows = []
    for label, column in (("Gaussian VaR", "VaR_Normal"),
                          ("Historical VaR", "VaR_Historical"),
                          ("GARCH-EVT VaR", "VaR_GARCH_EVT")):
        rows.append(economic_summary(
            baseline_frame["Loss"], baseline_frame[column],
            confidence_level=confidence_level, notional=notional,
            es_forecasts=baseline_frame["ES_GARCH_EVT"] if label == "GARCH-EVT VaR" else None,
            returns=baseline_frame["Return"], label=label,
        ))
    table = pd.DataFrame(rows).set_index("Model")
    table["Cumulative Unreserved (USD m)"] = (
        table["Cumulative Unreserved Loss (USD)"] / 1e6)
    return table


def registers_by_model(baseline_frame, notional=NOTIONAL_USD):
    
    return {
        label: build_breach_register(
            baseline_frame.index, baseline_frame["Loss"],
            baseline_frame[column], returns=baseline_frame["Return"],
            es_forecasts=baseline_frame["ES_GARCH_EVT"], notional=notional)
        for label, column in (("Gaussian", "VaR_Normal"),
                              ("Historical", "VaR_Historical"),
                              ("GARCH-EVT", "VaR_GARCH_EVT"))
    }


def economic_headline(summary_row, adequacy_row, notional=NOTIONAL_USD):
    
    low, high = summary_row["Breach Rate 95% CI (%)"]
    years = summary_row["Total Obs"] / 252.0
    return {
        "frequency": (
            f"{summary_row['Actual Breaches']} exceptions in "
            f"{summary_row['Total Obs']} out-of-sample days, a rate of "
            f"{summary_row['Breach Rate (%)']:.3f}% with an exact 95% interval of "
            f"[{low:.3f}%, {high:.3f}%], which "
            f"{'contains' if summary_row['Nominal Inside 95% CI'] else 'excludes'} "
            f"the {summary_row['Nominal Rate (%)']:.1f}% target."
        ),
        "magnitude": (
            f"Each miss cleared the forecast by "
            f"{summary_row['Mean Excess Loss (%)']:.4f}% on average "
            f"(${summary_row['Mean Excess (USD)']:,.0f} on a "
            f"${notional:,.0f} book) and by up to "
            f"{summary_row['Max Excess Loss (%)']:.4f}% "
            f"(${summary_row['Max Excess (USD)']:,.0f}), leaving "
            f"${summary_row['Cumulative Unreserved Loss (USD)']:,.0f} unreserved "
            f"over {years:.1f} years of out-of-sample history."
        ),
        "reserve": (
            f"Holding expected shortfall rather than value at risk means carrying "
            f"${adequacy_row['Incremental Capital Held (USD)']:,.0f} more at every "
            f"mark, an uplift of "
            f"{adequacy_row['ES Reserve Uplift over VaR (%)']:.1f}% on the reserve. "
            f"That extra capital is held on all "
            f"{adequacy_row['Total Obs']} days, whereas the "
            f"${adequacy_row['Unreserved Loss Avoided by ES (USD)']:,.0f} of loss it "
            f"prevents going unfunded -- about "
            f"${adequacy_row['Unreserved Loss Avoided per Year (USD)']:,.0f} a year "
            f"-- is realised only on the days the tail appears. "
            f"It is not a complete fix: "
            f"{'it absorbs' if adequacy_row['ES Absorbs All VaR Shortfall'] else 'it does not absorb'} "
            f"the whole VaR shortfall, because "
            f"{adequacy_row['Days ES Also Breached']} of "
            f"{summary_row['Actual Breaches']} exceptions "
            f"({adequacy_row['Share of VaR Breaches Also ES Breaches (%)']:.1f}%) "
            f"still clear expected shortfall, leaving "
            f"${adequacy_row['Cumulative Unreserved under ES (USD)']:,.0f} uncovered."
        ),
    }


if __name__ == "__main__":
    from config import PRIMARY_POT_THRESHOLD_QUANTILE, PRIMARY_GARCH_INNOVATION_DISTRIBUTION
    from walkforward_engine import load_multi_config_cache

    baseline = pd.read_csv(M4_BASELINE_BACKTEST, index_col=0, parse_dates=True)

    print("=== Table 16: magnitude of the exceptions, all three models ===")
    comparison = model_economic_comparison(baseline)
    print(comparison[[
        "Total Obs", "Actual Breaches", "Breach Rate (%)", "Breach Rate 95% CI (%)",
        "Nominal Inside 95% CI", "Mean Excess Loss (%)", "Max Excess Loss (%)",
        "Mean Excess (USD)", "Cumulative Unreserved (USD m)",
    ]].to_string())

    print("\n=== Table 24: worst ten exceptions (GARCH-EVT) ===")
    registers = registers_by_model(baseline)
    register = registers["GARCH-EVT"]
    print(worst_breaches(register, 10).to_string())

    print(f"\n=== full register: {len(register)} exceptions, Appendix C ===")
    print(register.tail(5).to_string())

    print("\n=== concentration of the shortfall ===")
    for label, reg in registers.items():
        print(label, concentration(reg))

    print("\n=== VaR reserve versus ES reserve ===")
    adequacy = reserve_adequacy(baseline["Loss"], baseline["VaR_GARCH_EVT"],
                               baseline["ES_GARCH_EVT"], notional=NOTIONAL_USD)
    for k, v in adequacy.items():
        print(f"  {k}: {v}")

    print("\n=== headline sentences ===")
    summary = economic_summary(baseline["Loss"], baseline["VaR_GARCH_EVT"],
                               es_forecasts=baseline["ES_GARCH_EVT"],
                               returns=baseline["Return"])
    for key, sentence in economic_headline(summary, adequacy).items():
        print(f"\n[{key}]\n{sentence}")

    print("\n=== same analysis on the Module 6 primary configuration (corrected recursion) ===")
    sweep = load_multi_config_cache()["corrected"]
    sel = sweep[(sweep["innovation_dist"] == PRIMARY_GARCH_INNOVATION_DISTRIBUTION)
                & (sweep["threshold_q"] == PRIMARY_POT_THRESHOLD_QUANTILE)
                & (sweep["confidence_level"] == PRIMARY_CONFIDENCE)]
    losses = -baseline["Return"].reindex(sel.index).to_numpy(dtype=float)
    m6 = economic_summary(losses, sel["VaR_GARCH_EVT"].to_numpy(),
                          es_forecasts=sel["ES_GARCH_EVT"].to_numpy(),
                          returns=baseline["Return"].reindex(sel.index).to_numpy(dtype=float),
                          label="GARCH-EVT (corrected)")
    print(f"breaches {m6['Actual Breaches']} of {m6['Total Obs']}, "
          f"rate {m6['Breach Rate (%)']:.3f}%, CI {m6['Breach Rate 95% CI (%)']}, "
          f"cumulative unreserved ${m6['Cumulative Unreserved Loss (USD)']:,.0f}")
