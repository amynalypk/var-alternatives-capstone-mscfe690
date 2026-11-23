"""Acquire and prepare the market data used by the capstone analysis.

The implementation uses Yahoo Finance through :mod:`yfinance` as its only
runtime data source.  It requests auto-adjusted daily prices for the 20-stock
current-constituent S&P 500 sample, SPY, and ``^VIX`` over the configured
2005--2024 window, then caches the result under ``data/``.  The preparation
step computes aligned daily log returns and an equal-weighted portfolio return.
The checked-in universe is not point-in-time index membership, so it has
survivorship bias; the code does not claim to remove that limitation.

Kenneth French and FRED are declared project data sources for broader research
context, but neither is required by this acquisition path.  No login or secret
key is needed for the Yahoo Finance download.
"""

import os

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import jarque_bera, skew, kurtosis

from config import (
    TICKERS,
    BENCHMARK_TICKER,
    VOLATILITY_TICKER,
    START_DATE,
    END_DATE,
    DATA_DIR,
)


def _validate_prices(prices):
    """Validate the minimum schema and quality required by downstream models."""
    required_columns = TICKERS + [BENCHMARK_TICKER, VOLATILITY_TICKER]
    missing_columns = [column for column in required_columns if column not in prices]
    if prices.empty:
        raise ValueError("Market data is empty; check the Yahoo Finance response or cache.")
    if missing_columns:
        raise ValueError(
            "Market data is missing required columns: " + ", ".join(missing_columns)
        )
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("Market data index must contain parsed trading dates.")
    if not prices.index.is_monotonic_increasing:
        raise ValueError("Market data dates must be sorted in increasing order.")
    if prices.index.has_duplicates:
        raise ValueError("Market data contains duplicate trading dates.")
    if not np.isfinite(prices.to_numpy(dtype=float)).all():
        raise ValueError("Market data contains non-finite prices after missing-value handling.")
    if (prices <= 0).any().any():
        raise ValueError("Market data contains non-positive prices unsuitable for log returns.")


def fetch_and_cache_data(force_reload=False):
    """Load cached adjusted prices or download and cache them from Yahoo Finance.

    Args:
        force_reload: Download fresh data instead of reusing the local CSV cache.

    Returns:
        A validated DataFrame indexed by trading date with one price column for
        every configured equity, SPY, and ``^VIX``.

    Raises:
        ValueError: If the source response or cache is empty, incomplete, or
            contains invalid dates/prices.
    """
    cache_file = os.path.join(DATA_DIR, "sp500_market_data_2005_2024.csv")

    if os.path.exists(cache_file) and not force_reload:
        print(f"[Data] Loading cached market data from: {cache_file}")
        data = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        _validate_prices(data)
        return data

    print(f"[Data] Downloading market data from Yahoo Finance ({START_DATE} to {END_DATE})...")
    all_tickers = TICKERS + [BENCHMARK_TICKER, VOLATILITY_TICKER]

    # auto_adjust=True uses split- and dividend-adjusted prices, avoiding a
    # mixture of raw closes and corporate-action-adjusted observations.
    raw = yf.download(
        all_tickers,
        start=START_DATE,
        end=END_DATE,
        auto_adjust=True,
    )
    if "Close" in raw:
        prices = raw["Close"]
    else:
        prices = raw

    # Yahoo's end date is exclusive.  Fill short gaps caused by non-overlapping
    # trading calendars, then reject any rows still incomplete across the universe.
    prices = prices.ffill().bfill().dropna()
    prices.index = pd.to_datetime(prices.index)
    _validate_prices(prices)

    prices.to_csv(cache_file)
    print(
        f"[Data] Market data successfully downloaded and cached to: {cache_file} "
        f"({prices.shape[0]} rows)"
    )
    return prices


def process_returns(prices_df):
    """Convert prices into aligned log returns and an equal-weight portfolio.

    The return is ``log(P_t / P_(t-1))``.  The one-row shift and ``dropna``
    create a common trading-date sample for all equity assets; VIX is carried
    at those same dates as a level for regime labeling, not as a return.
    """
    _validate_prices(prices_df)
    equity_cols = TICKERS + [BENCHMARK_TICKER]
    # The first observation has no lagged price; dropping it prevents an
    # artificial missing return from entering the walk-forward calculations.
    returns_df = np.log(prices_df[equity_cols] / prices_df[equity_cols].shift(1)).dropna()

    # Equal weights are a declared baseline, not an estimate fitted to returns.
    equal_weights = np.ones(len(TICKERS)) / len(TICKERS)
    returns_df["Portfolio"] = returns_df[TICKERS].dot(equal_weights)

    if VOLATILITY_TICKER in prices_df:
        returns_df["VIX"] = prices_df[VOLATILITY_TICKER].loc[returns_df.index]

    return returns_df


def compute_summary_statistics(returns_series, annualization_factor=252):
    """Return descriptive statistics for a daily return series.

    ``annualization_factor`` defaults to 252 US trading days and affects only
    the annualized return and volatility fields.
    """
    n_obs = len(returns_series)
    mean_daily = returns_series.mean()
    std_daily = returns_series.std()
    ann_return = mean_daily * annualization_factor
    ann_vol = std_daily * np.sqrt(annualization_factor)
    skew_val = float(skew(returns_series))
    kurt_val = float(kurtosis(returns_series, fisher=True))
    jb_stat, jb_pval = jarque_bera(returns_series)

    return {
        "Observations": n_obs,
        "Mean Daily (%)": mean_daily * 100,
        "Daily Volatility (%)": std_daily * 100,
        "Annualized Return (%)": ann_return * 100,
        "Annualized Volatility (%)": ann_vol * 100,
        "Skewness": skew_val,
        "Excess Kurtosis": kurt_val,
        "Jarque-Bera Stat": float(jb_stat),
        "Jarque-Bera p-val": float(jb_pval),
    }

if __name__ == "__main__":
    prices = fetch_and_cache_data()
    returns = process_returns(prices)
    stats = compute_summary_statistics(returns['Portfolio'])
    print("\n--- Equal-Weighted 20-Stock Portfolio Summary Statistics (2005-2024) ---")
    for k, v in stats.items():
        if isinstance(v, float):
            print(f"{k}: {v:.4f}")
        else:
            print(f"{k}: {v}")
