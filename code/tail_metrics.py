

"""Provide tail-coverage intervals and breach-register summaries."""
import numpy as np
import pandas as pd
from scipy.stats import beta as _beta


def clopper_pearson(exceptions, total_obs, alpha=0.05):
    
    """Compute or assemble the clopper_pearson result used by the tail_metrics analysis."""
    if total_obs <= 0:
        raise ValueError("total_obs must be positive")
    if not 0 <= exceptions <= total_obs:
        raise ValueError("exceptions must lie between 0 and total_obs")

    low = 0.0 if exceptions == 0 else float(_beta.ppf(alpha / 2.0, exceptions, total_obs - exceptions + 1.0))
    high = 1.0 if exceptions == total_obs else float(_beta.ppf(1.0 - alpha / 2.0, exceptions + 1.0, total_obs - exceptions))
    return low, high


def clopper_pearson_contains(nominal_rate, exceptions, total_obs, alpha=0.05):
    
    """Compute or assemble the clopper_pearson_contains result used by the tail_metrics analysis."""
    low, high = clopper_pearson(exceptions, total_obs, alpha)
    return bool(low <= nominal_rate <= high), low, high


REGISTER_COLUMNS = ["Return", "Loss", "VaR", "Exceedance", "Exceedance_bps",
                    "USD_Loss", "USD_Excess", "ES_forecast", "ES_also_breached"]


def build_breach_register(index, losses, var_forecasts, returns=None,
                          es_forecasts=None, notional=0.0):
    
    """Compute or assemble the build_breach_register result used by the tail_metrics analysis."""
    losses = np.asarray(losses, dtype=float)
    var_forecasts = np.asarray(var_forecasts, dtype=float)
    forecast_present = ~np.isnan(var_forecasts) & ~np.isnan(losses)
    mask = forecast_present & (losses > var_forecasts)
    full_index = pd.DatetimeIndex(index, name="Date")

    if not mask.any():
        frame = pd.DataFrame(index=full_index[mask])
        for column, dtype in (("Return", float), ("Loss", float), ("VaR", float),
                              ("Exceedance", float), ("Exceedance_bps", float),
                              ("USD_Loss", float), ("USD_Excess", float),
                              ("ES_forecast", float), ("ES_also_breached", bool)):
            frame[column] = pd.Series(dtype=dtype)
        return frame

    excess = losses[mask] - var_forecasts[mask]
    frame = pd.DataFrame({
        "Return": (np.asarray(returns, dtype=float)[mask]
                   if returns is not None else -losses[mask]),
        "Loss": losses[mask],
        "VaR": var_forecasts[mask],
        "Exceedance": excess,
        "Exceedance_bps": excess * 10000.0,
        "USD_Loss": losses[mask] * notional,
        "USD_Excess": excess * notional,
    }, index=full_index[mask])
    if es_forecasts is not None:
        es = np.asarray(es_forecasts, dtype=float)[mask]
        frame["ES_forecast"] = es
        frame["ES_also_breached"] = losses[mask] > es
    else:
        frame["ES_forecast"] = np.nan
        frame["ES_also_breached"] = False
    return frame.sort_values("Exceedance", ascending=False)


def describe_excess_losses(excess, notional=0.0):
    
    """Compute or assemble the describe_excess_losses result used by the tail_metrics analysis."""
    excess = np.asarray(excess, dtype=float)
    if excess.size == 0:
        return {
            "count": 0, "mean_pct": 0.0, "median_pct": 0.0, "max_pct": 0.0,
            "total_pct": 0.0, "total_notional": 0.0, "mean_notional": 0.0, "max_notional": 0.0,
        }
    return {
        "count": int(excess.size),
        "mean_pct": float(excess.mean() * 100.0),
        "median_pct": float(np.median(excess) * 100.0),
        "max_pct": float(excess.max() * 100.0),
        "total_pct": float(excess.sum() * 100.0),
        "total_notional": float(excess.sum() * notional),
        "mean_notional": float(excess.mean() * notional),
        "max_notional": float(excess.max() * notional),
    }
