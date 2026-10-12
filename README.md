# MScFE 690 Capstone Project - Module 4: Core Assets / First Draft Submission

## Project Information

**Course:** MScFE 690, Capstone Project  
**Track:** Volatility and Risk (Track 2)  
**Topic 3:** Developing Alternatives to VaR  
**Student Group Number:** 17845


## Project Overview

This project develops and validates alternative risk measures to Value-at-Risk (VaR) for medium-term equity portfolios. The research addresses VaR's documented failures during crisis periods by proposing a composite metric combining Expected Shortfall (ES), Extreme Value Theory (EVT), and GARCH-based volatility filtering.

## Module 4 Deliverables

This code implements the full data acquisition pipeline, baseline VaR models, two-stage GARCH(1,1)-EVT Expected Shortfall framework, walk-forward backtesting engine, and publication figures referenced in the M4 Project Proposal and First Draft Report.

### Implementation Scope

- **Universe:** 20 representative US large-cap S&P 500 stocks across 10 GICS sectors (AAPL, MSFT, JNJ, PFE, JPM, GS, HD, DIS, VZ, CMCSA, BA, CAT, PG, KO, XOM, CVX, DD, LIN, DUK, SO), plus SPY benchmark and CBOE VIX index (`^VIX`)
- **Time Period:** January 2005 - December 2024 (daily adjusted close prices)
- **Data Source:** Yahoo Finance via `yfinance` library
- **Models Implemented:** Parametric Gaussian VaR, Historical Simulation VaR, Dynamic GARCH(1,1)-EVT VaR, and Dynamic GARCH(1,1)-EVT Expected Shortfall (CVaR) at 99% and 97.5% confidence levels

## Installation

Install required Python dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the analysis script:

```bash
python m4_core_assets.py
```

### Output

The script generates:
1. Console output with summary statistics, GARCH(1,1)-EVT parameters, out-of-sample backtest results, Kupiec POF and Christoffersen test statistics, regime breakdown, and Dirichlet robustness results
2. Cached market data and backtest outputs in `data/`:
   - `sp500_market_data_2005_2024.csv` - historical daily prices
   - `backtest_results_500w.csv` - walk-forward 1-day-ahead risk forecasts
   - `module4_metrics_manifest.json` - summary metrics and test statistics
3. Publication visualizations in `figures/`:
   - `fig1_portfolio_vs_market_drawdowns.png` - cumulative wealth and drawdowns with VIX crisis regimes
   - `fig2_fat_tailed_diagnostics_gpd_fit.png` - return density, Normal Q-Q plot, and GPD tail exceedance fit
   - `fig3_rolling_var_es_backtest_crises.png` - out-of-sample risk forecasts vs realized losses with 2008 GFC and 2020 COVID zoom-ins
   - `fig4_backtest_violations_by_regime.png` - model violation rates across Calm, Normal, and Crisis volatility regimes
   - `fig5_dirichlet_robustness_test.png` - breach rate distribution across 100 randomized Dirichlet portfolio allocations

## Configuration

Key parameters are defined in `config.py`:

- `TICKERS`: List of 20 stock symbols
- `BENCHMARK_TICKER`: Market benchmark symbol (`SPY`)
- `VOLATILITY_TICKER`: Volatility index symbol (`^VIX`)
- `START_DATE`: Analysis start date (YYYY-MM-DD)
- `END_DATE`: Analysis end date (YYYY-MM-DD)
- `PRIMARY_CONFIDENCE`: Primary risk confidence level (default: 0.99)
- `ROLLING_WINDOW`: Rolling calibration window in trading days (default: 500)
- `POT_THRESHOLD_QUANTILE`: Threshold quantile for EVT Peaks-Over-Threshold GPD fit (default: 0.90)
- `DIRICHLET_SIMULATIONS`: Number of randomized portfolio weight simulations (default: 100)

Modify `config.py` to adjust these parameters without editing the main script.

## Project Structure

```
code/
├── m4_core_assets.py        # Main analysis orchestration script
├── config.py                # Configuration parameters
├── data_acquisition.py      # Market data download, caching, and return calculation
├── risk_models.py           # Parametric VaR, Historical VaR, and GARCH(1,1)-EVT-ES models
├── backtester.py            # Walk-forward backtesting, Kupiec, Christoffersen, and Dirichlet tests
├── visualizations.py        # Publication figure generation
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── CONTRIBUTORS.md          # Group member information
├── data/                    # Cached market data and backtest outputs
└── figures/                 # Generated visualizations
```

## Dependencies

- **yfinance**: Yahoo Finance data acquisition
- **pandas**: Data manipulation and time series analysis
- **numpy**: Numerical computations
- **scipy**: Statistical distributions and hypothesis tests (Normal, Generalized Pareto, Chi-squared, Jarque-Bera)
- **arch**: GARCH(1,1) conditional volatility estimation
- **statsmodels**: Econometric diagnostics
- **matplotlib**: Visualization

## Methodology

1. **Data Acquisition**: Download daily adjusted close prices for the 20 S&P 500 stocks, SPY, and VIX from Yahoo Finance
2. **Return Calculation**: Compute daily logarithmic returns
3. **Portfolio Construction**: Equal-weighted 20-stock portfolio allocation and 100 randomized Dirichlet allocations
4. **Risk Model Estimation**:
   - Parametric VaR: Assumes normal distribution of returns
   - Historical VaR: Empirical quantile from historical returns
   - GARCH(1,1)-EVT VaR & Expected Shortfall: Filters conditional volatility via GARCH(1,1) and fits a Generalized Pareto Distribution (GPD) to standardized tail exceedances above the 90th percentile threshold
5. **Backtesting & Validation**: Rolling 500-day walk-forward out-of-sample evaluation using Kupiec POF unconditional coverage tests, Christoffersen independence tests, VIX regime segmentation, and Dirichlet weight robustness checks

## Contact

For questions regarding this implementation, contact the project group members listed in `CONTRIBUTORS.md`.
