

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from config import (
    TICKERS, PORTFOLIO_VOL_WINDOW, PORTFOLIO_REGIME_BANDS,
    PORTFOLIO_REGIME_CAL_DAYS, VIX_CALM_THRESHOLD, VIX_CRISIS_THRESHOLD,
    PRIMARY_CONFIDENCE, PRIMARY_POT_THRESHOLD_QUANTILE,
    PRIMARY_GARCH_INNOVATION_DISTRIBUTION, M4_BASELINE_BACKTEST, STRESS_WINDOWS,
)
from forecast_eval import score_forecasts





GICS_SECTOR_BY_TICKER = {
    "AAPL": "Information Technology",
    "MSFT": "Information Technology",
    "JNJ": "Health Care",
    "PFE": "Health Care",
    "JPM": "Financials",
    "GS": "Financials",
    "HD": "Consumer Discretionary",
    "DIS": "Communication Services",
    "VZ": "Communication Services",
    "CMCSA": "Communication Services",
    "BA": "Industrials",
    "CAT": "Industrials",
    "PG": "Consumer Staples",
    "KO": "Consumer Staples",
    "XOM": "Energy",
    "CVX": "Energy",
    "DD": "Materials",
    "LIN": "Materials",
    "DUK": "Utilities",
    "SO": "Utilities",
}

PORTFOLIO_REGIME_LABELS = ["low_vol", "mid_vol", "high_vol"]
VIX_REGIME_LABELS = ["calm", "normal", "crisis"]



PORTFOLIO_COLUMN_FROZEN = "portfolio_regime_frozen"
PORTFOLIO_COLUMN_BALANCED = "portfolio_regime_balanced"


def lagged_realised_vol(portfolio_returns, window=PORTFOLIO_VOL_WINDOW):
    
    return (portfolio_returns.rolling(window).std(ddof=1) * np.sqrt(252.0)).shift(1)


def freeze_regime_cut_points(realised_vol, cal_days=PORTFOLIO_REGIME_CAL_DAYS,
                             n_bands=PORTFOLIO_REGIME_BANDS):
    
    cal = realised_vol.iloc[:cal_days].dropna()
    if len(cal) < n_bands * 10:
        raise ValueError(
            f"only {len(cal)} usable calibration observations for {n_bands} bands")
    probs = np.linspace(0.0, 1.0, n_bands + 1)[1:-1]
    cuts = [float(np.quantile(cal, p)) for p in probs]
    return {"calibration_days": int(len(cal)), "cut_points": cuts,
            "calibration_mean": float(cal.mean()), "calibration_max": float(cal.max())}


def classify_portfolios_regimes(realised_vol, cut_points):
    labels = []
    for v in realised_vol:
        if pd.isna(v):
            labels.append(None)
        elif v < cut_points[0]:
            labels.append(PORTFOLIO_REGIME_LABELS[0])
        elif v < cut_points[1]:
            labels.append(PORTFOLIO_REGIME_LABELS[1])
        else:
            labels.append(PORTFOLIO_REGIME_LABELS[2])
    return pd.Series(labels, index=realised_vol.index, name="portfolio_regime")


def classify_vix_regimes(vix, calm=VIX_CALM_THRESHOLD, crisis=VIX_CRISIS_THRESHOLD):
    out = pd.Series(None, index=vix.index, name="vix_regime", dtype=object)
    out[vix < calm] = VIX_REGIME_LABELS[0]
    out[(vix >= calm) & (vix < crisis)] = VIX_REGIME_LABELS[1]
    out[vix >= crisis] = VIX_REGIME_LABELS[2]
    return out


def build_regime_frame(returns_df, vol_window=PORTFOLIO_VOL_WINDOW,
                       cal_days=PORTFOLIO_REGIME_CAL_DAYS,
                       n_bands=PORTFOLIO_REGIME_BANDS):
    
    port = returns_df["Portfolio"]
    rv = lagged_realised_vol(port, window=vol_window)
    frozen = freeze_regime_cut_points(rv, cal_days=cal_days, n_bands=n_bands)
    balanced = freeze_regime_cut_points(rv, cal_days=len(rv), n_bands=n_bands)
    vix_lag = returns_df["VIX"].shift(1)

    frame = pd.DataFrame({
        "Portfolio_Return": port,
        "Loss": -port,
        "RealisedVol": rv,
        "VIX_lag": vix_lag,
        "VIX": returns_df["VIX"],
    })
    frame[PORTFOLIO_COLUMN_FROZEN] = classify_portfolios_regimes(rv, frozen["cut_points"])
    frame[PORTFOLIO_COLUMN_BALANCED] = classify_portfolios_regimes(rv, balanced["cut_points"])
    frame["vix_regime"] = classify_vix_regimes(vix_lag)
    return frame, {"frozen": frozen, "balanced": balanced}


def _to_ordinal(series, labels):
    return series.map({label: i for i, label in enumerate(labels)})


def agreement_table(regime_frame, portfolio_column=PORTFOLIO_COLUMN_BALANCED):
    
    sub = regime_frame.dropna(subset=[portfolio_column, "vix_regime"])
    a = _to_ordinal(sub[portfolio_column], PORTFOLIO_REGIME_LABELS).to_numpy()
    b = _to_ordinal(sub["vix_regime"], VIX_REGIME_LABELS).to_numpy()
    return {
        "portfolio_column": portfolio_column,
        "n_classified": int(len(sub)),
        "kappa_unweighted": float(cohen_kappa_score(a, b, labels=[0, 1, 2])),
        "kappa_quadratic": float(cohen_kappa_score(a, b, labels=[0, 1, 2],
                                                   weights="quadratic")),
        "pct_agreement": float(np.mean(a == b) * 100.0),
        "pct_within_one_band": float(np.mean(np.abs(a - b) <= 1) * 100.0),
        "marginals_portfolio": {k: int(v) for k, v in
                                sub[portfolio_column].value_counts().items()},
        "marginals_vix": {k: int(v) for k, v in
                          sub["vix_regime"].value_counts().items()},
    }


def cross_tab_with_breach_rates(regime_frame, sweep_frame, innovation_dist=PRIMARY_GARCH_INNOVATION_DISTRIBUTION,
                                threshold_q=PRIMARY_POT_THRESHOLD_QUANTILE,
                                confidence_level=PRIMARY_CONFIDENCE,
                                portfolio_column=PORTFOLIO_COLUMN_BALANCED):
    
    sel = sweep_frame[(sweep_frame["innovation_dist"] == innovation_dist)
                      & (sweep_frame["threshold_q"] == threshold_q)
                      & (sweep_frame["confidence_level"] == confidence_level)]
    joined = regime_frame.join(sel[["VaR_GARCH_EVT", "ES_GARCH_EVT"]], how="inner")
    joined = joined.dropna(subset=[portfolio_column, "vix_regime", "VaR_GARCH_EVT"])

    rows = []
    for pr in PORTFOLIO_REGIME_LABELS:
        for vr in VIX_REGIME_LABELS:
            cell = joined[(joined[portfolio_column] == pr)
                          & (joined["vix_regime"] == vr)]
            n = len(cell)
            breaches = int((cell["Loss"] > cell["VaR_GARCH_EVT"]).sum()) if n else 0
            excess = (cell.loc[cell["Loss"] > cell["VaR_GARCH_EVT"], "Loss"]
                      - cell.loc[cell["Loss"] > cell["VaR_GARCH_EVT"], "VaR_GARCH_EVT"])
            rows.append({
                "portfolio_regime": pr,
                "vix_regime": vr,
                "Observations": n,
                "Share (%)": float(n / len(joined) * 100.0) if len(joined) else 0.0,
                "Breaches": breaches,
                "Breach Rate (%)": float(breaches / n * 100.0) if n else np.nan,
                "Mean VaR (%)": float(cell["VaR_GARCH_EVT"].mean() * 100.0) if n else np.nan,
                "Mean Excess Loss (%)": float(excess.mean() * 100.0) if breaches else np.nan,
                "Mean Realised Vol (%)": float(cell["RealisedVol"].mean() * 100.0) if n else np.nan,
                "Mean VIX (lag)": float(cell["VIX_lag"].mean()) if n else np.nan,
            })
    return pd.DataFrame(rows), joined


def regime_conditional_performance(regime_frame, sweep_frame,
                                   innovation_dist=PRIMARY_GARCH_INNOVATION_DISTRIBUTION,
                                   threshold_q=PRIMARY_POT_THRESHOLD_QUANTILE,
                                   confidence_level=PRIMARY_CONFIDENCE,
                                   notional=None):
    
    sel = sweep_frame[(sweep_frame["innovation_dist"] == innovation_dist)
                      & (sweep_frame["threshold_q"] == threshold_q)
                      & (sweep_frame["confidence_level"] == confidence_level)]
    joined = regime_frame.join(sel[["VaR_GARCH_EVT", "ES_GARCH_EVT"]], how="inner")
    joined = joined.dropna(subset=["VaR_GARCH_EVT"])

    blocks = []
    for kind, column, labels in (
        ("vix_band", "vix_regime", VIX_REGIME_LABELS),
        ("portfolio_vol_tercile_frozen", PORTFOLIO_COLUMN_FROZEN, PORTFOLIO_REGIME_LABELS),
        ("portfolio_vol_tercile_balanced", PORTFOLIO_COLUMN_BALANCED, PORTFOLIO_REGIME_LABELS),
    ):
        for label in labels:
            cell = joined[joined[column] == label]
            if cell.empty:
                continue
            scored = score_forecasts(
                cell["Loss"].to_numpy(), cell["VaR_GARCH_EVT"].to_numpy(),
                confidence_level, es_forecasts=cell["ES_GARCH_EVT"].to_numpy(),
                **({"notional": notional} if notional is not None else {}),
            )
            scored.update({
                "definition": kind,
                "regime": label,
                "Mean Realised Vol (%)": float(cell["RealisedVol"].mean() * 100.0),
                "Mean VIX (lag)": float(cell["VIX_lag"].mean()),
                "Mean Daily Loss (%)": float(cell["Loss"].mean() * 100.0),
            })
            blocks.append(scored)

    for name, start, end in STRESS_WINDOWS:
        mask = (joined.index >= pd.Timestamp(start)) & (joined.index <= pd.Timestamp(end))
        cell = joined[mask]
        if cell.empty:
            continue
        scored = score_forecasts(
            cell["Loss"].to_numpy(), cell["VaR_GARCH_EVT"].to_numpy(),
            confidence_level, es_forecasts=cell["ES_GARCH_EVT"].to_numpy(),
            **({"notional": notional} if notional is not None else {}),
        )
        scored.update({
            "definition": "date_overlay (not a partition)",
            "regime": name,
            "Mean Realised Vol (%)": float(cell["RealisedVol"].mean() * 100.0),
            "Mean VIX (lag)": float(cell["VIX_lag"].mean()),
            "Mean Daily Loss (%)": float(cell["Loss"].mean() * 100.0),
        })
        blocks.append(scored)

    table = pd.DataFrame(blocks)
    leading = ["definition", "regime", "Total Obs", "Actual Breaches"]
    ordered = leading + [c for c in table.columns if c not in leading]
    return table[ordered].set_index(["definition", "regime"])


def regime_gap(joined_frame, portfolio_column=PORTFOLIO_COLUMN_BALANCED):
    
    sub = joined_frame.dropna(subset=[portfolio_column, "vix_regime"])
    return (_to_ordinal(sub[portfolio_column], PORTFOLIO_REGIME_LABELS)
            - _to_ordinal(sub["vix_regime"], VIX_REGIME_LABELS))


def disagreement_register(joined_frame, portfolio_column=PORTFOLIO_COLUMN_BALANCED):
    
    sub = joined_frame.dropna(subset=[portfolio_column, "vix_regime", "VaR_GARCH_EVT"]).copy()
    sub["gap"] = regime_gap(sub, portfolio_column)

    out = {}
    for key, mask in (
        ("portfolio_stressed_market_calm", sub["gap"] >= 2),
        ("market_stressed_portfolio_calm", sub["gap"] <= -2),
        ("any_disagreement", sub["gap"] != 0),
    ):
        days = sub[mask]
        out[key] = {
            "n_days": int(len(days)),
            "pct_of_sample": float(len(days) / len(sub) * 100.0) if len(sub) else 0.0,
            "mean_loss_pct": float(days["Loss"].mean() * 100.0) if len(days) else 0.0,
            "breach_rate_pct": float((days["Loss"] > days["VaR_GARCH_EVT"]).mean() * 100.0)
            if len(days) else np.nan,
            "mean_var_pct": float(days["VaR_GARCH_EVT"].mean() * 100.0) if len(days) else np.nan,
            "worst_days": [
                {"date": str(idx.date()), "loss_pct": float(row["Loss"] * 100.0),
                 "portfolio_regime": row[portfolio_column],
                 "vix_regime": row["vix_regime"], "vix_lag": float(row["VIX_lag"])}
                for idx, row in days.nlargest(10, "Loss").iterrows()
            ] if len(days) else [],
        }
    return out


def sector_contribution(returns_df, dates, tickers=None):
    
    tickers = TICKERS if tickers is None else tickers
    weights = {}
    for t in tickers:
        sector = GICS_SECTOR_BY_TICKER[t]
        weights.setdefault(sector, []).append(t)
    dates = pd.DatetimeIndex(dates)
    columns = ["sector", "n_names", "names", "weight", "mean_daily_return_pct",
               "contribution_pct", "mean_dispersion_vs_portfolio_pct", "n_days"]
    if len(dates) == 0:
        return pd.DataFrame(columns=columns)

    days = dates.intersection(returns_df.index)
    port = returns_df.loc[days, "Portfolio"]
    rows = []
    for sector, names in sorted(weights.items()):
        sub = returns_df.loc[days, names]
        mean_ret = float(sub.mean().mean())
        w = len(names) / len(tickers)
        gap = (sub.sub(port, axis=0)).abs().mean().mean()
        rows.append({
            "sector": sector, "n_names": len(names), "names": ",".join(names),
            "weight": w, "mean_daily_return_pct": mean_ret * 100.0,
            "contribution_pct": mean_ret * w * 100.0,
            "mean_dispersion_vs_portfolio_pct": float(gap) * 100.0,
            "n_days": int(len(days)),
        })
    frame = pd.DataFrame(rows, columns=columns)
    return frame.sort_values("mean_dispersion_vs_portfolio_pct",
                             ascending=False).reset_index(drop=True)


def model_ranking_by_regime(baseline_frame, sweep_frame, regime_frame,
                            innovation_dist=PRIMARY_GARCH_INNOVATION_DISTRIBUTION,
                            threshold_q=PRIMARY_POT_THRESHOLD_QUANTILE,
                            confidence_level=PRIMARY_CONFIDENCE,
                            portfolio_column=PORTFOLIO_COLUMN_BALANCED):
    
    sel = sweep_frame[(sweep_frame["innovation_dist"] == innovation_dist)
                      & (sweep_frame["threshold_q"] == threshold_q)
                      & (sweep_frame["confidence_level"] == confidence_level)]
    columns = {
        "Gaussian": "VaR_Normal",
        "Historical": "VaR_Historical",
    }
    joined = (regime_frame
              .join(baseline_frame[list(columns.values())], how="inner")
              .join(sel[["VaR_GARCH_EVT"]], how="inner"))
    joined = joined.dropna(subset=[portfolio_column, "vix_regime"])
    all_columns = dict(columns, **{"GARCH-EVT": "VaR_GARCH_EVT"})

    rows = []
    blocks = [("vix_band", "vix_regime", VIX_REGIME_LABELS),
              ("portfolio_vol_tercile", portfolio_column, PORTFOLIO_REGIME_LABELS)]
    for kind, column, labels in blocks:
        for label in labels:
            cell = joined[joined[column] == label]
            if cell.empty:
                continue
            entry = {"definition": kind, "regime": label, "Total Obs": len(cell)}
            scored = {}
            for model, col in all_columns.items():
                scored[model] = score_forecasts(
                    cell["Loss"].to_numpy(), cell[col].to_numpy(), confidence_level)
                entry[f"{model} Breaches"] = scored[model]["Actual Breaches"]
                entry[f"{model} Rate (%)"] = scored[model]["Breach Rate (%)"]
                entry[f"{model} Kupiec p"] = scored[model]["Kupiec p-val"]
                entry[f"{model} Mean Excess (%)"] = scored[model]["Mean Excess Loss (%)"]
            nominal = (1.0 - confidence_level) * 100.0
            
            
            entry["closest_to_nominal"] = min(
                all_columns, key=lambda m: abs(scored[m]["Breach Rate (%)"] - nominal))
            entry["all_within_nominal_5pct"] = bool(all(
                scored[m]["Nominal Rate Inside 95% CI"] for m in all_columns))
            entry["garch_evt_kupiec_rejected"] = bool(
                scored["GARCH-EVT"]["Kupiec p-val"] < 0.05)
            entry["severity_ranking_lowest_first"] = " < ".join(
                m for m in sorted(all_columns, key=lambda m: scored[m]["Mean Excess Loss (%)"]))
            rows.append(entry)
    return pd.DataFrame(rows).set_index(["definition", "regime"])


if __name__ == "__main__":
    from data_acquisition import fetch_and_cache_data, process_returns
    from walkforward_engine import load_multi_config_cache

    returns_df = process_returns(fetch_and_cache_data())
    frame, cut_points = build_regime_frame(returns_df)
    print("=== portfolio-vol tercile cut points ===")
    for kind, points in cut_points.items():
        print(f"{kind}: {points}")

    print("\n=== agreement between the two definitions ===")
    for column in (PORTFOLIO_COLUMN_FROZEN, PORTFOLIO_COLUMN_BALANCED):
        print(f"--- {column} ---")
        for k, v in agreement_table(frame, portfolio_column=column).items():
            print(f"  {k}: {v}")

    sweep = load_multi_config_cache()["corrected"]
    tab11, joined = cross_tab_with_breach_rates(frame, sweep)
    print("\n=== Table 14: VIX band x portfolio-vol tercile, with breach rates ===")
    print(tab11.to_string(index=False))

    print("\n=== Table 15: regime-conditional performance, both definitions ===")
    print(regime_conditional_performance(frame, sweep)[
        ["Total Obs", "Actual Breaches", "Breach Rate (%)", "Kupiec p-val",
         "Conditional Cov p-val", "Mean Excess Loss (%)", "Mean VaR (%)",
         "Mean Realised Vol (%)", "Mean VIX (lag)", "Mean Daily Loss (%)"]
    ].to_string())

    for column in (PORTFOLIO_COLUMN_BALANCED, PORTFOLIO_COLUMN_FROZEN):
        print(f"\n=== disagreement register, {column} ===")
        for key, val in disagreement_register(joined, column).items():
            print(f"{key}: n={val['n_days']} ({val['pct_of_sample']:.2f}% of sample) "
                  f"mean loss {val['mean_loss_pct']:.4f}% "
                  f"breach rate {val['breach_rate_pct']:.3f}%")

    gap = regime_gap(joined)
    stressed_calm = gap.index[gap >= 2]
    print("\n=== sector attribution on portfolio-stressed / market-calm days ===")
    print(sector_contribution(returns_df, stressed_calm).to_string(index=False))
    print("\n=== which years those days fall in ===")
    print(pd.Series(stressed_calm.year).value_counts().sort_index().to_string())

    baseline = pd.read_csv(M4_BASELINE_BACKTEST, index_col=0, parse_dates=True)
    for column in (PORTFOLIO_COLUMN_BALANCED, PORTFOLIO_COLUMN_FROZEN):
        print(f"\n=== model ranking by regime, {column} ===")
        print(model_ranking_by_regime(baseline, sweep, frame, portfolio_column=column)[
            ["Total Obs", "Gaussian Breaches", "Gaussian Rate (%)",
             "Historical Breaches", "Historical Rate (%)",
             "GARCH-EVT Breaches", "GARCH-EVT Rate (%)", "GARCH-EVT Kupiec p",
             "closest_to_nominal", "severity_ranking_lowest_first"]
        ].to_string())
