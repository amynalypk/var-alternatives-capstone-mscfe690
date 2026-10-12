import os
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import jarque_bera, skew, kurtosis
from config import (
    TICKERS, BENCHMARK_TICKER, VOLATILITY_TICKER,
    START_DATE, END_DATE, DATA_DIR
)

def fetch_and_cache_data(force_reload=False):
    cache_file = os.path.join(DATA_DIR, "sp500_market_data_2005_2024.csv")
    
    if os.path.exists(cache_file) and not force_reload:
        print(f"[Data] Loading cached market data from: {cache_file}")
        data = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        return data
        
    print(f"[Data] Downloading market data from Yahoo Finance ({START_DATE} to {END_DATE})...")
    all_tickers = TICKERS + [BENCHMARK_TICKER, VOLATILITY_TICKER]
    
    raw = yf.download(all_tickers, start=START_DATE, end=END_DATE, auto_adjust=True)
    if 'Close' in raw:
        prices = raw['Close']
    else:
        prices = raw
        
    prices = prices.ffill().bfill().dropna()
    
    prices.to_csv(cache_file)
    print(f"[Data] Market data successfully downloaded and cached to: {cache_file} ({prices.shape[0]} rows)")
    return prices

def process_returns(prices_df):
    equity_cols = TICKERS + [BENCHMARK_TICKER]
    returns_df = np.log(prices_df[equity_cols] / prices_df[equity_cols].shift(1)).dropna()
    
    equal_weights = np.ones(len(TICKERS)) / len(TICKERS)
    returns_df['Portfolio'] = returns_df[TICKERS].dot(equal_weights)
    
    if VOLATILITY_TICKER in prices_df:
        returns_df['VIX'] = prices_df[VOLATILITY_TICKER].loc[returns_df.index]
        
    return returns_df

def compute_summary_statistics(returns_series, annualization_factor=252):
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
        "Jarque-Bera p-val": float(jb_pval)
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
