"""Walk-forward portfolio allocation, trading simulation, and evaluation.

Target weights are solved on a fixed trading-day schedule from aligned raw or
conditional return scenarios.  ``simulate_book`` then lets holdings drift with
realized asset returns, compares the next target with those held weights, and
nets stylised turnover costs.  The dynamic risk engine evaluates the exposed
book with the corrected GARCH-EVT recursion.  This module implements equal
weight, minimum-variance, and minimum-Expected-Shortfall variants; risk parity,
volume-based liquidity, and copula stress models are outside this deliverable.
"""

import os
import time

import numpy as np
import pandas as pd
from scipy.stats import kurtosis

from config import (
    REBALANCE_INTERVAL, ROLLING_WINDOW, MAX_ASSET_WEIGHT, MIN_ASSET_WEIGHT,
    TXN_COST_BPS, TURNOVER_CAP_ONE_WAY, PRIMARY_ES_LP_ALPHA, ES_LP_ALPHAS,
    PRIMARY_CONFIDENCE, PRIMARY_POT_THRESHOLD_QUANTILE,
    PRIMARY_GARCH_INNOVATION_DISTRIBUTION, VARIANCE_RECURSION,
    M6_ASSET_STORE_DIR, NOTIONAL_USD, DATA_DIR, STRESS_WINDOWS,
)
from portfolio_optimizer import (
    build_scenarios, min_es_lp, min_variance_weights, scenario_covariance,
    shrunk_covariance, equal_weight, empirical_es, mean_off_diagonal_correlation,
)
from risk_models import fit_garch11_state, fit_evt_pot_diag, compute_evt_quantiles
from forecast_eval import score_forecasts
from backtester import run_walk_forward_backtest
from asset_walk_forward import run_asset_walk_forward, assemble

M6_OPTIMISATION_CACHE = os.path.join(DATA_DIR, "m6_optimisation_weight_history.csv")

STRATEGIES = {
    "Equal weight (rebalanced)": {"kind": "equal", "rebalance": True},
    "Equal weight (buy-and-hold)": {"kind": "equal", "rebalance": False},
    "Minimum variance (sample)": {"kind": "minvar", "cov": "sample"},
    "Minimum variance (Ledoit-Wolf)": {"kind": "minvar", "cov": "shrunk"},
    "Minimum ES": {"kind": "mines", "alpha": PRIMARY_ES_LP_ALPHA},
    "Minimum ES with return floor": {
        "kind": "mines", "alpha": PRIMARY_ES_LP_ALPHA, "floor": "ew"},
    "Minimum ES with turnover cap": {
        "kind": "mines", "alpha": PRIMARY_ES_LP_ALPHA,
        "turnover_cap": TURNOVER_CAP_ONE_WAY},
}


def scenario_block(matrices, i, full_returns, window=ROLLING_WINDOW):
    """Assemble the trailing scenario block used by an allocation decision.

    Early decisions use raw returns for the part of the rolling window before
    standardized residuals exist.  Later decisions use conditional scenarios
    from the asset-level forecast mean, volatility, and aligned residual rows.
    """
    hist_r = full_returns.iloc[i: i + window].to_numpy(dtype=float)
    if hist_r.shape[0] != window:
        raise ValueError(f"day {i} has fewer than {window} rows of price history behind it")
    z_hist = matrices["z"].iloc[max(i - window, 0): i].to_numpy(dtype=float)
    mu = matrices["mu"].iloc[i].to_numpy(dtype=float)
    sigma = matrices["sigma"].iloc[i].to_numpy(dtype=float)

    if z_hist.shape[0] == window:
        return build_scenarios(mu, sigma, z_hist)
    unconditional = hist_r[: window - z_hist.shape[0]]
    if z_hist.shape[0] == 0:
        return unconditional
    return np.vstack([unconditional, build_scenarios(mu, sigma, z_hist)])


def unconditional_rows_used(matrices, i, window=ROLLING_WINDOW):
    
    return max(window - min(i, window), 0)


def _solve_at(matrices, i, spec, w_prev, expected_returns, full_returns):
    n = matrices["z"].shape[1]
    scenarios = scenario_block(matrices, i, full_returns)
    if spec["kind"] == "equal":
        return {"weights": equal_weight(n), "status": 0, "objective": None,
                "es": empirical_es(equal_weight(n), scenarios, PRIMARY_ES_LP_ALPHA),
                "n_scenarios": scenarios.shape[0], "turnover": None}
    if spec["kind"] == "minvar":
        cov = scenario_covariance(scenarios) if spec["cov"] == "sample" \
            else shrunk_covariance(scenarios)
        out = min_variance_weights(cov, w_prev=w_prev,
                                   turnover_cap=spec.get("turnover_cap"))
        out["es"] = empirical_es(out["weights"], scenarios, PRIMARY_ES_LP_ALPHA)
        out["n_scenarios"] = scenarios.shape[0]
        return out
    floor = None
    if spec.get("floor") == "ew" and expected_returns is not None:
        floor = float(expected_returns @ equal_weight(n))
    return min_es_lp(scenarios, alpha=spec["alpha"], w_prev=w_prev,
                     turnover_cap=spec.get("turnover_cap"),
                     expected_returns=expected_returns, return_floor=floor)


def build_weight_schedule(matrices, full_returns, strategies=STRATEGIES,
                          interval=REBALANCE_INTERVAL):
    """Create target-weight schedules without using future observations.

    A new target is solved when ``i % interval == 0``; otherwise the prior
    target is carried forward.  The default interval is 20 trading days and is
    shared with the GARCH/EVT refit cadence.  A failed solve retains the prior
    target and records a diagnostic.  Buy-and-hold is solved once, while other
    strategies are periodically re-optimised.
    """
    dates = matrices["z"].index
    n = matrices["z"].shape[1]
    tickers = list(matrices["z"].columns)
    expected_returns = matrices["mu"].to_numpy(dtype=float)

    schedules = {}
    diagnostics = []
    for name, spec in strategies.items():
        rows = np.full((len(dates), n), np.nan)
        w_prev = equal_weight(n)
        for i in range(len(dates)):
            if i % interval == 0:
                out = _solve_at(matrices, i, spec, w_prev, expected_returns[i],
                                full_returns)
                if out["weights"] is None or out["status"] != 0:
                    diagnostics.append({
                        "strategy": name, "date": str(dates[i]),
                        "status": out["status"], "message": out["message"],
                    })
                    
                    
                    
                    rows[i] = w_prev
                else:
                    rows[i] = out["weights"]
                    w_prev = out["weights"]
            else:
                rows[i] = w_prev
        frame = pd.DataFrame(rows, index=dates, columns=tickers)
        if not spec.get("rebalance", True):
            frame = frame.iloc[[0]].reindex(frame.index)
        frame = frame.ffill()
        if frame.isna().any().any():
            raise AssertionError(f"{name}: schedule has unfilled weight days")
        schedules[name] = frame

    return schedules, pd.DataFrame(diagnostics)


def simulate_book(weights_frame, returns_frame, interval=REBALANCE_INTERVAL,
                  cost_bps=TXN_COST_BPS, rebalance=True):
    """Simulate target allocations, drifted holdings, turnover, and costs.

    Between scheduled rebalances, realized returns change market-value weights.
    Turnover compares the next target with those drifted holdings, not with the
    previous target.  The one-way turnover cap and 10-basis-point cost are implementation
    frictions; they are not calibrated volume, spread, market-impact, or forced
    liquidation assumptions and therefore do not constitute a full liquidity
    stress model.
    """
    w = weights_frame.to_numpy(dtype=float)
    r = returns_frame.reindex(weights_frame.index).to_numpy(dtype=float)
    n_days, n_assets = r.shape

    wealth = np.ones(n_days)
    returns = np.zeros(n_days)
    held = np.zeros_like(w)
    turnover = np.zeros(n_days)
    costs = np.zeros(n_days)

    value = None
    capital = 1.0
    for i in range(n_days):
        if i == 0:
            value = w[i] * capital
        elif rebalance and i % interval == 0:
            current = value / capital
            traded = float(np.abs(w[i] - current).sum() / 2.0)
            cost = cost_bps / 1e4 * traded
            capital *= (1.0 - cost)
            turnover[i] = traded
            costs[i] = cost
            value = w[i] * capital

        held[i] = value / capital
        day_return = float(np.dot(held[i], r[i])) if np.isfinite(r[i]).all() else np.nan
        
        
        
        
        
        returns[i] = day_return - costs[i]
        capital *= (1.0 + returns[i])
        value = value * (1.0 + r[i])
        wealth[i] = capital

    return pd.DataFrame({
        "Return": returns, "Wealth": wealth, "Turnover": turnover, "Cost": costs,
    }, index=weights_frame.index), pd.DataFrame(held, index=weights_frame.index,
                                                columns=weights_frame.columns)


def run_dynamic_book_walk_forward(held_weights, full_returns, realized_returns=None,
                                  confidence_level=PRIMARY_CONFIDENCE,
                                  window=ROLLING_WINDOW,
                                  refit_interval=REBALANCE_INTERVAL,
                                  threshold_quantile=PRIMARY_POT_THRESHOLD_QUANTILE,
                                  innovation_dist=PRIMARY_GARCH_INNOVATION_DISTRIBUTION,
                                  recursion=VARIANCE_RECURSION):
    """Forecast VaR and ES for the book actually held each day.

    The function uses the corrected GARCH-EVT recursion only and aligns the
    realized portfolio return with the drifted held-weight frame.  It returns
    realized return, positive loss, VaR, and ES columns for downstream scoring.
    """
    if recursion != "corrected":
        raise ValueError(
            "the dynamic-book backtest is only run on the corrected recursion; "
            "a legacy result would not be comparable to the Module 6 sweep")

    r = full_returns.to_numpy(dtype=float)
    w = held_weights.to_numpy(dtype=float)
    n_days = len(held_weights)
    if r.shape[0] < n_days + window:
        raise ValueError("full-return frame is too short to warm up the book model")
    var_out = np.full(n_days, np.nan)
    es_out = np.full(n_days, np.nan)

    state = None
    evt = None
    refit_day = -999
    sigma_var = None

    for i in range(n_days):
        hist = r[i: i + window] @ w[i]
        hist = hist[np.isfinite(hist)]
        if hist.size < window // 2:
            continue
        if i - refit_day >= refit_interval or state is None:
            state = fit_garch11_state(hist, dist=innovation_dist)
            sigma_var = state["cond_vol"][-1] ** 2
            evt = fit_evt_pot_diag(state["std_resid"], threshold_quantile,
                                   min_exceedances=10)
            refit_day = i
            if evt["degenerate"]:
                state = None
                continue

        
        
        
        eps = hist[-1] - state["mu"]
        sigma_next = np.sqrt(state["omega"] + state["alpha"] * eps ** 2
                             + state["beta"] * sigma_var)
        sigma_var = sigma_next ** 2

        var_z, es_z = compute_evt_quantiles(
            evt["u"], evt["xi_used"], evt["beta"], evt["n_u"], evt["n_tot"],
            confidence_level)
        
        
        var_out[i] = -state["mu"] + sigma_next * var_z
        es_out[i] = -state["mu"] + sigma_next * es_z

    realized = (np.einsum("ij,ij->i", r[window: window + n_days], w)
                if realized_returns is None
                else np.asarray(realized_returns, dtype=float))
    frame = pd.DataFrame({
        "Return": realized,
        "VaR_GARCH_EVT": var_out,
        "ES_GARCH_EVT": es_out,
    }, index=held_weights.index)
    if not frame.index.equals(held_weights.index):
        raise AssertionError(
            "dynamic-book risk frame and weight schedule are on different dates")
    frame["Loss"] = -frame["Return"]
    return frame


def realised_book_engine(book, confidence_level=PRIMARY_CONFIDENCE):
    
    series = pd.Series(book["Return"].to_numpy(), index=book.index)
    frame = run_walk_forward_backtest(series, confidence_level=confidence_level)
    frame = frame.dropna(subset=["VaR_GARCH_EVT"])
    return frame


def strategy_metrics(name, book, risk_frame, notional=NOTIONAL_USD, realised_frame=None):
    
    returns = book["Return"].to_numpy(dtype=float)
    wealth = book["Wealth"].to_numpy(dtype=float)
    years = returns.size / 252.0
    ann_return = float(np.mean(returns)) * 252.0
    ann_vol = float(np.std(returns, ddof=1)) * np.sqrt(252.0)
    peak = np.maximum.accumulate(wealth)
    drawdown = wealth / peak - 1.0

    scores = score_forecasts(risk_frame["Loss"].to_numpy(dtype=float),
                             risk_frame["VaR_GARCH_EVT"].to_numpy(dtype=float),
                             PRIMARY_CONFIDENCE,
                             es_forecasts=risk_frame["ES_GARCH_EVT"].to_numpy(dtype=float),
                             notional=notional)
    cp_low, cp_high = scores["Breach Rate 95% CI (%)"]
    out = {
        "Strategy": name,
        "Ann return (%)": ann_return * 100.0,
        "Ann volatility (%)": ann_vol * 100.0,
        "Sharpe": ann_return / ann_vol if ann_vol > 0 else np.nan,
        "Max drawdown (%)": float(drawdown.min() * 100.0),
        "One-way turnover (annual)": float(book["Turnover"].sum() / years)
        if years else np.nan,
        "Cost drag (% of wealth)": float(book["Cost"].sum() * 100.0),
        "Scored days": scores["Total Obs"],
        "Actual Breaches": scores["Actual Breaches"],
        "Breach Rate (%)": scores["Breach Rate (%)"],
        "Breach CI low (%)": cp_low,
        "Breach CI high (%)": cp_high,
        "Nominal inside CI": scores["Nominal Rate Inside 95% CI"],
        "Kupiec p": scores["Kupiec p-val"],
        "Christoffersen p": scores["Conditional Cov p-val"],
        "Mean Excess Loss (%)": scores["Mean Excess Loss (%)"],
        "Mean VaR (%)": scores["Mean VaR (%)"],
        "Mean ES (%)": scores["Mean ES (%)"],
        "Dropped NaN Forecasts": scores["Dropped NaN Forecasts"],
    }
    if realised_frame is not None:
        rs = score_forecasts(
            realised_frame["Loss"].to_numpy(dtype=float),
            realised_frame["VaR_GARCH_EVT"].to_numpy(dtype=float),
            PRIMARY_CONFIDENCE,
            es_forecasts=realised_frame["ES_GARCH_EVT"].to_numpy(dtype=float),
            notional=notional)
        out.update({
            "Realised engine days": rs["Total Obs"],
            "Realised breaches": rs["Actual Breaches"],
            "Realised rate (%)": rs["Breach Rate (%)"],
            "Realised Kupiec p": rs["Kupiec p-val"],
            "Realised CC p": rs["Conditional Cov p-val"],
        })
    return out


def engine_convention_control(out, window=ROLLING_WINDOW, notional=NOTIONAL_USD):
    
    rows = []
    for name, risk in out["risk_frames"].items():
        scored_full = risk.dropna(subset=["VaR_GARCH_EVT"])
        trimmed = risk.iloc[window:].dropna(subset=["VaR_GARCH_EVT"])
        realised = out["realised_frames"][name].dropna(subset=["VaR_GARCH_EVT"])
        for label, frame in (("A  frozen filter, full sample", scored_full),
                             ("A' frozen filter, B's dates", trimmed),
                             ("B  realised-series engine", realised)):
            scores = score_forecasts(
                frame["Loss"].to_numpy(dtype=float),
                frame["VaR_GARCH_EVT"].to_numpy(dtype=float), PRIMARY_CONFIDENCE,
                es_forecasts=frame["ES_GARCH_EVT"].to_numpy(dtype=float),
                notional=notional)
            low, high = scores["Breach Rate 95% CI (%)"]
            rows.append({
                "Strategy": name, "convention": label,
                "First day": frame.index[0].date().isoformat(),
                "Last day": frame.index[-1].date().isoformat(),
                "Scored days": scores["Total Obs"],
                "Breaches": scores["Actual Breaches"],
                "Breach Rate (%)": scores["Breach Rate (%)"],
                "CI low (%)": low, "CI high (%)": high,
                "Kupiec p": scores["Kupiec p-val"],
                "Christoffersen p": scores["Conditional Cov p-val"],
                "Mean Excess Loss (%)": scores["Mean Excess Loss (%)"],
                "Mean VaR (%)": scores["Mean VaR (%)"],
            })
    return (pd.DataFrame(rows)
            .set_index(["Strategy", "convention"])
            .rename_axis(["Strategy", "engine convention"]))


def book_diagnosis_table(out, windows=STRESS_WINDOWS):
    
    rows = []
    for name, book in out["books"].items():
        x = book["Return"].to_numpy(dtype=float)
        risk = out["risk_frames"][name].dropna(subset=["VaR_GARCH_EVT"])
        var = risk["VaR_GARCH_EVT"].to_numpy(dtype=float)
        breach = (risk["Loss"].to_numpy(dtype=float) > var)
        run = longest = 0
        for flag in breach:
            run = run + 1 if flag else 0
            longest = max(longest, run)
        dates = risk.index[breach]
        row = {
            "Strategy": name,
            "Vol (%)": float(np.std(x, ddof=1) * 100.0),
            "Excess kurtosis": float(kurtosis(x, fisher=True)),
            "Skew": float(pd.Series(x).skew()),
            "Worst day (%)": float(x.min() * 100.0),
            "Days < -5%": int((x < -0.05).sum()),
            "Days < -7%": int((x < -0.07).sum()),
            "Mean VaR (%)": float(var.mean() * 100.0),
            "Median VaR (%)": float(np.median(var) * 100.0),
            "P90 VaR (%)": float(np.quantile(var, 0.90) * 100.0),
            "Mean ES (%)": float(risk["ES_GARCH_EVT"].mean() * 100.0),
            "Breaches": int(breach.sum()),
            "Longest run of breaches": int(longest),
            "Names held": int((out["schedules"][name].to_numpy(dtype=float)
                               > 1e-4).sum(axis=1).mean()),
        }
        counted = 0
        for label, start, end in windows:
            inside = int(((dates >= pd.Timestamp(start))
                          & (dates <= pd.Timestamp(end))).sum())
            row[f"Breaches in {label}"] = inside
            counted += inside
        row["Breaches outside all windows"] = int(breach.sum() - counted)
        rows.append(row)
    return pd.DataFrame(rows).set_index("Strategy")


def breach_date_agreement_table(out, frames_key="realised_frames"):
    
    sets = {}
    for name, frame in out[frames_key].items():
        scored = frame.dropna(subset=["VaR_GARCH_EVT"])
        hits = scored.index[scored["Loss"].to_numpy(dtype=float)
                            > scored["VaR_GARCH_EVT"].to_numpy(dtype=float)]
        sets[name] = set(hits)

    names = list(sets)
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = len(sets[a] & sets[b])
            union = len(sets[a] | sets[b])
            rows.append({
                "Book A": a, "Book B": b,
                "Breaches A": len(sets[a]), "Breaches B": len(sets[b]),
                "Shared exception days": shared,
                "Only in A": len(sets[a]) - shared, "Only in B": len(sets[b]) - shared,
                "Jaccard": shared / union if union else np.nan,
            })
    return pd.DataFrame(rows).set_index(["Book A", "Book B"])


def concentration_summary(schedules):
    
    rows = []
    for name, frame in schedules.items():
        w = frame.to_numpy(dtype=float)
        rows.append({
            "Strategy": name,
            "Mean names held": float((w > 1e-4).sum(axis=1).mean()),
            "Mean Herfindahl": float((w ** 2).sum(axis=1).mean()),
            "Mean max weight": float(w.max(axis=1).mean()),
            "Mean min weight": float(w.min(axis=1).mean()),
        })
    return pd.DataFrame(rows).set_index("Strategy")


def es_reduction_table(matrices, full_returns, alphas=ES_LP_ALPHAS,
                       interval=REBALANCE_INTERVAL, sample_every=5):
    """Compare minimum-ES forecasts with equal weight across alpha levels.

    The table records forecast ES, percentage reduction, number of names,
    Herfindahl concentration, and solver status at sampled decision dates.  It
    is a forecast-risk diagnostic, not proof of superior realized performance.
    """
    dates = matrices["z"].index
    n = matrices["z"].shape[1]
    ew = equal_weight(n)
    rows = []
    for i in range(0, len(dates), interval * sample_every):
        scenarios = scenario_block(matrices, i, full_returns)
        for alpha in alphas:
            mines = min_es_lp(scenarios, alpha=alpha)
            if mines["weights"] is None:
                continue
            base = empirical_es(ew, scenarios, alpha)
            rows.append({
                "date": dates[i], "alpha": alpha,
                "unconditional rows": unconditional_rows_used(matrices, i),
                "EW forecast ES (%)": base * 100.0,
                "Min-ES forecast ES (%)": mines["es"] * 100.0,
                "Reduction (%)": (mines["es"] / base - 1.0) * 100.0
                if base > 0 else np.nan,
                "Names held": mines["names_held"],
                "Herfindahl": mines["herfindahl"],
                "Status": mines["status"],
            })
    return pd.DataFrame(rows)


def run_optimisation(returns_df=None, strategies=STRATEGIES, force=False, quick=False,
                     write_cache=True):
    """Run the complete dynamic allocation comparison and collect outputs.

    The returned payload contains schedules, drifted books, risk frames,
    realized-engine frames, strategy metrics, concentration diagnostics,
    minimum-ES reduction paths, and solver failures.  Optional cache writing
    stores the target-weight history; it does not replace the in-memory held
    weights used for simulation and risk evaluation.
    """
    from data_acquisition import fetch_and_cache_data, process_returns
    from asset_walk_forward import load_asset_store

    if returns_df is None:
        returns_df = process_returns(fetch_and_cache_data())

    if force:
        store = run_asset_walk_forward(returns_df, force=True)
    else:
        try:
            store = load_asset_store()
        except FileNotFoundError:
            store = run_asset_walk_forward(returns_df)
    matrices = assemble(store)

    columns = list(matrices["z"].columns)
    
    
    
    tickers = sorted(columns)[:10] if quick else columns
    for key in matrices:
        matrices[key] = matrices[key][tickers]
    full_returns = returns_df[tickers]

    schedules, failures = build_weight_schedule(matrices, full_returns, strategies)

    results = []
    books = {}
    risk_frames = {}
    realised_frames = {}
    for name, spec in strategies.items():
        book, held = simulate_book(schedules[name], matrices["Return"],
                                   rebalance=spec.get("rebalance", True))
        risk = run_dynamic_book_walk_forward(
            held, full_returns, realized_returns=book["Return"].to_numpy())
        realised = realised_book_engine(book)
        books[name] = book
        risk_frames[name] = risk
        realised_frames[name] = realised
        results.append(strategy_metrics(name, book, risk, realised_frame=realised))

    table = pd.DataFrame(results).set_index("Strategy")
    payload = {
        "matrices": matrices, "full_returns": full_returns, "schedules": schedules,
        "failures": failures, "books": books, "risk_frames": risk_frames,
        "realised_frames": realised_frames,
        "table": table, "concentration": concentration_summary(schedules),
        "mean_off_diagonal_correlation": mean_off_diagonal_correlation(
            matrices["z"].to_numpy()),
        "tickers": tickers,
    }
    payload["es_reduction"] = es_reduction_table(matrices, full_returns)
    payload["breach_date_agreement"] = breach_date_agreement_table(payload)

    if write_cache:
        stacked = pd.concat({name: frame for name, frame in schedules.items()},
                            names=["Strategy", "Date"])
        stacked.to_csv(M6_OPTIMISATION_CACHE)
        payload["weight_history_path"] = M6_OPTIMISATION_CACHE
    return payload


if __name__ == "__main__":
    t0 = time.perf_counter()
    out = run_optimisation()
    print("\n=== Table 18: static versus dynamically optimised books ===")
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(out["table"].to_string(float_format=lambda v: f"{v:,.4f}"))
    print("\n=== concentration ===")
    print(out["concentration"].to_string(float_format=lambda v: f"{v:,.4f}"))
    print(f"\nfailed solves: {len(out['failures'])}")
    if len(out["failures"]):
        print(out["failures"].head(10).to_string())
    print(f"\nmean off-diagonal standardised-residual correlation: "
          f"{out['mean_off_diagonal_correlation']:.3f}")

    print("\n=== engine versus sample: the A / A' / B control ===")
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(engine_convention_control(out).to_string(
            float_format=lambda v: f"{v:,.4f}"))

    print("\n=== why the lower risk measure breaches more ===")
    with pd.option_context("display.width", 240, "display.max_columns", 30):
        print(book_diagnosis_table(out).to_string(float_format=lambda v: f"{v:,.3f}"))

    print("\n=== same count is not the same test: breach-date agreement (realised) ===")
    with pd.option_context("display.width", 240, "display.max_columns", 30):
        print(out["breach_date_agreement"].to_string(float_format=lambda v: f"{v:,.4f}"))

    print(f"\n{time.perf_counter() - t0:.0f}s total")
