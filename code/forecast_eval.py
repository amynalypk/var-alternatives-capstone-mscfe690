"""Forecast scoring helpers for out-of-sample VaR and ES evaluation.

The primary evaluator uses positive loss magnitudes and treats a forecast as
breached only when ``loss > VaR``.  It combines exception-frequency,
independence, exact-binomial-interval, and excess-loss diagnostics.  The
module deliberately does not implement general forecast-loss scores, a
Diebold--Mariano test, or a Model Confidence Set procedure; the submitted
comparison path uses coverage and economic-impact measures instead.
"""

import numpy as np

from backtester import christoffersen_test
from tail_metrics import clopper_pearson, describe_excess_losses
from config import CLOPPER_PEARSON_ALPHA, NOTIONAL_USD


def score_forecasts(losses, var_forecasts, confidence_level, es_forecasts=None,
                    notional=NOTIONAL_USD):
    """Score positive-loss forecasts against realized losses.

    Parameters
    ----------
    losses : array-like
        Realized positive loss magnitudes, normally ``-Return``.
    var_forecasts : array-like
        One-step-ahead VaR loss forecasts at ``confidence_level``.  Rows with
        missing VaR are excluded from the scored sample and counted in the
        ``Dropped NaN Forecasts`` result.
    confidence_level : float
        VaR confidence level.  The nominal exception probability is
        ``1 - confidence_level``.
    es_forecasts : array-like, optional
        Optional Expected Shortfall forecasts aligned to the input arrays.  ES
        diagnostics use the same rows retained by the VaR mask.
    notional : float, default=NOTIONAL_USD
        Portfolio value used to express excess losses in currency units.

    Returns
    -------
    dict
        Counts, breach rate, mean/median/maximum VaR, Kupiec unconditional
        coverage and Christoffersen independence/conditional-coverage
        statistics, exact 95% Clopper--Pearson interval, and percentage/USD
        excess-loss measures.  With ES supplied, the dictionary also includes
        ES breaches, mean ES, the ES--VaR spread in basis points, and the mean
        loss beyond ES on VaR-breach days.

    Notes
    -----
    A breach is strictly ``loss > VaR``; a tie is not an exception.  The
    function filters missing VaR forecasts, but does not independently filter
    missing losses or validate missing/misaligned ES values.  Callers should
    align and validate those arrays before scoring.  Empty scored samples and
    zero-breach samples return zero-valued rate/severity summaries where the
    underlying helper permits it; the coverage-test behavior is inherited from
    ``christoffersen_test`` and ``clopper_pearson``.
    """
    losses = np.asarray(losses, dtype=float)
    var_forecasts = np.asarray(var_forecasts, dtype=float)
    keep = ~np.isnan(var_forecasts)
    nan_forecasts = int((~keep).sum())
    losses = losses[keep]
    var_forecasts = var_forecasts[keep]

    n_obs = int(losses.size)
    breach_mask = losses > var_forecasts
    x = int(breach_mask.sum())
    rate = x / n_obs if n_obs else 0.0

    excess = losses[breach_mask] - var_forecasts[breach_mask]
    severity = describe_excess_losses(excess, notional)
    cc = christoffersen_test(breach_mask, confidence_level)
    cp_low, cp_high = clopper_pearson(x, n_obs, CLOPPER_PEARSON_ALPHA)
    nominal = 1.0 - confidence_level

    out = {
        "Total Obs": n_obs,
        "Expected Breaches": n_obs * nominal,
        "Actual Breaches": x,
        "Breach Rate (%)": rate * 100.0,
        "Kupiec LR_uc": cc["LR_uc"],
        "Kupiec p-val": cc["p_val_uc"],
        "Christoffersen LR_ind": cc["LR_ind"],
        "Independence p-val": cc["p_val_ind"],
        "Conditional Cov LR_cc": cc["LR_cc"],
        "Conditional Cov p-val": cc["p_val_cc"],
        "Mean Excess Loss (%)": severity["mean_pct"],
        "Median Excess Loss (%)": severity["median_pct"],
        "Max Excess Loss (%)": severity["max_pct"],
        "Total Excess Loss (%)": severity["total_pct"],
        "Mean Excess (USD)": severity["mean_notional"],
        "Max Excess (USD)": severity["max_notional"],
        "Total Excess (USD)": severity["total_notional"],
        "Breach Rate 95% CI (%)": (cp_low * 100.0, cp_high * 100.0),
        "Nominal Rate Inside 95% CI": bool(cp_low <= nominal <= cp_high),
        
        
        
        
        "Mean VaR (%)": float(np.mean(var_forecasts) * 100.0) if n_obs else 0.0,
        "Median VaR (%)": float(np.median(var_forecasts) * 100.0) if n_obs else 0.0,
        "Max VaR (%)": float(np.max(var_forecasts) * 100.0) if n_obs else 0.0,
        "Dropped NaN Forecasts": int(nan_forecasts),
    }

    if es_forecasts is not None:
        es_forecasts = np.asarray(es_forecasts, dtype=float)[keep]
        es_breach = losses > es_forecasts
        x_es = int(es_breach.sum())
        es_excess = describe_excess_losses(
            losses[es_breach] - es_forecasts[es_breach], notional
        )
        out["ES Actual Breaches"] = x_es
        out["ES Breach Rate (%)"] = (x_es / n_obs * 100.0) if n_obs else 0.0
        out["ES Mean Excess Beyond ES (%)"] = es_excess["mean_pct"]
        out["Mean ES (%)"] = float(np.mean(es_forecasts) * 100.0) if n_obs else 0.0
        
        
        out["Mean ES minus VaR (bps)"] = (
            float(np.mean(es_forecasts - var_forecasts) * 10000.0) if n_obs else 0.0
        )
        
        
        if x:
            out["ES Calibration Discrepancy (%)"] = float(
                np.mean(losses[breach_mask] - es_forecasts[breach_mask]) * 100.0
            )
        else:
            out["ES Calibration Discrepancy (%)"] = 0.0

    return out
