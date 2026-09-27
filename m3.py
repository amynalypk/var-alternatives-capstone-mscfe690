import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from config import TICKERS, START_DATE, END_DATE, CONFIDENCE_LEVEL

def download_data(tickers, start, end):
    print(f"Downloading data for {tickers}...")
    raw_data = yf.download(tickers, start=start, end=end, group_by='ticker')

    if len(tickers) == 1:
        data = raw_data['Close']
    else:
        data = pd.DataFrame({ticker: raw_data[ticker]['Close'] for ticker in tickers})

    return data

def calculate_returns(data):
    return data.pct_change().dropna()

def calculate_parametric_var(returns, confidence_level=0.99):
    mean = returns.mean()
    std = returns.std()
    z_score = norm.ppf(1 - confidence_level)
    var = -(mean + z_score * std)
    return var

def calculate_historical_var(returns, confidence_level=0.99):
    var = -np.percentile(returns, (1 - confidence_level) * 100)
    return var

def main():
    data = download_data(TICKERS, START_DATE, END_DATE)
    returns = calculate_returns(data)

    weights = np.array([1/len(TICKERS)] * len(TICKERS))
    portfolio_returns = returns.dot(weights)

    param_var = calculate_parametric_var(portfolio_returns, CONFIDENCE_LEVEL)
    hist_var = calculate_historical_var(portfolio_returns, CONFIDENCE_LEVEL)

    print(f"\n--- Initial Risk Analysis Results ({START_DATE} to {END_DATE}) ---")
    print(f"Confidence Level: {CONFIDENCE_LEVEL*100}%")
    print(f"Parametric VaR: {param_var:.4%}")
    print(f"Historical VaR: {hist_var:.4%}")

    plt.figure(figsize=(10, 6))
    plt.hist(portfolio_returns, bins=100, alpha=0.75, label='Portfolio Returns')
    plt.axvline(-param_var, color='r', linestyle='--', label=f'Parametric VaR ({param_var:.2%})')
    plt.axvline(-hist_var, color='g', linestyle='--', label=f'Historical VaR ({hist_var:.2%})')
    plt.title('Distribution of Portfolio Daily Returns (2005-2024)')
    plt.legend()
    plt.savefig('portfolio_returns_distribution.png')
    print("\nChart saved as 'portfolio_returns_distribution.png'")

if __name__ == "__main__":
    main()
