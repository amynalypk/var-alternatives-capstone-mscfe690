# MScFE 690 Capstone Project - Module 6: Draft Project Submission

## Project Information

**Course:** MScFE 690, Capstone Project  
**Track:** Volatility and Risk (Track 2)  
**Topic 3:** Developing Alternatives to VaR  
**Student Group Number:** 17845


## Project Overview

This project develops and validates alternative risk measures to Value-at-Risk (VaR) for medium-term equity portfolios. The research addresses VaR's documented failures during crisis periods through a composite framework combining Expected Shortfall (ES), Extreme Value Theory (EVT), and GARCH-based volatility filtering. Module 6 extends the Module 4 framework with threshold and model diagnostics, corrected GARCH variance recursion, portfolio-based regime analysis, economic impact measurement, dynamic portfolio optimisation, and runtime benchmarking.

## Module 6 Deliverables

This code retains the reproducible Module 4 baseline and implements the complete Module 6 analysis pipeline. It evaluates EVT threshold sensitivity, tests GARCH innovation assumptions, compares Gaussian and Student-t filters, measures the economic cost of risk-model breaches, optimises portfolio weights for minimum Expected Shortfall, and generates the metrics and publication figures used in the Module 6 Draft Project Report.

### Implementation Scope

- **Universe:** 20 representative US large-cap S&P 500 stocks across 10 GICS sectors (AAPL, MSFT, JNJ, PFE, JPM, GS, HD, DIS, VZ, CMCSA, BA, CAT, PG, KO, XOM, CVX, DD, LIN, DUK, SO), plus SPY benchmark and CBOE VIX index (`^VIX`)
- **Time Period:** January 2005 - December 2024 (daily adjusted close prices)
- **Data Source:** Yahoo Finance via the `yfinance` library
- **Primary Model:** Dynamic GARCH(1,1)-EVT VaR and Expected Shortfall at 99% confidence, using a 500-day rolling window, 20-day refit interval, and 90th-percentile Peaks-Over-Threshold (POT) threshold
- **Comparisons:** Parametric Gaussian VaR, Historical Simulation VaR, Gaussian versus Student-t GARCH innovations, six EVT thresholds from 80% to 98%, and legacy versus corrected GARCH variance recursion
- **Portfolio Extension:** Dynamic minimum-Expected-Shortfall allocation with a 15% single-asset cap, optional 30% one-way turnover cap, and 10-basis-point transaction cost
- **Economic Scale:** USD 100 million portfolio notional for breach magnitude and reserve-adequacy analysis

## Installation

Install required Python dependencies:

```bash
pip install -r requirements.txt
```

Python 3.14 was used for the submitted analysis.

## Usage

From the Module 6 deliverable root, run the scripts in this order:

```bash
python code/m4_core_assets.py
python code/m6_develop_pipeline.py
python code/visualizations_m6.py
```

If working directly inside the `code/` folder, omit the `code/` prefix.

The first script downloads or reuses the cached market data and reproduces the Module 4 baseline. The second script calculates all Module 6 metrics and writes the metrics manifest. The third script generates the Module 6 publication figures.

Useful Module 6 pipeline options:

```bash
python code/m6_develop_pipeline.py --force
python code/m6_develop_pipeline.py --only threshold,iid
python code/m6_develop_pipeline.py --only optimisation_control
python code/m6_develop_pipeline.py --no-write
```

- `--force` recomputes every section instead of reusing the existing manifest
- `--only` recomputes one or more named sections and merges them into the manifest
- `--no-write` computes and prints results without changing the manifest

The full pipeline can take several minutes because the multi-configuration walk-forward analysis and portfolio optimisation are computationally intensive.

### Output

The scripts generate:

1. Console output containing the Module 4 reproduction check, corrected and legacy recursion results, risk-model breach rates, Kupiec POF and Christoffersen conditional-coverage statistics, threshold recommendations, optimisation results, and data-quality checks
2. Cached market data and analytical outputs in `data/`, including:
   - `sp500_market_data_2005_2024.csv` - historical daily adjusted close prices
   - `backtest_results_500w.csv` - Module 4 walk-forward forecasts retained as the baseline
   - `m6_multi_config_walkforward.csv` - corrected-recursion threshold and innovation sweep
   - `m6_multi_config_walkforward_legacy.csv` - legacy-recursion comparison sweep
   - `m6_breach_register_garch_evt.csv` - Module 6 GARCH-EVT exception register and economic loss measures
   - `m6_optimisation_paths.csv` - realised paths and risk forecasts for the dynamic portfolio strategies
   - `m6_optimisation_weight_history.csv` - asset weights at each rebalance date
   - `m6_runtime_model_costs.csv`, `m6_runtime_refit_cadence.csv`, and `m6_runtime_sweep_sharing.csv` - runtime benchmark results
   - `module6_metrics_manifest.json` - source of the numerical results reported in the Module 6 report
3. Publication visualisations in `figures/`:
   - `fig1`-`fig5` - retained Module 4 drawdown, tail, backtest, regime, and robustness figures
   - `fig6_mean_excess_plot_threshold_selection.png` - mean excess loss and EVT threshold diagnostics
   - `fig7_threshold_sensitivity.png` - walk-forward threshold sensitivity
   - `fig8_innovation_diagnostics.png` - GARCH innovation diagnostics
   - `fig9_garch_normal_vs_t.png` - Gaussian versus Student-t GARCH comparison
   - `fig10_portfolio_vs_vix_regimes.png` - portfolio-volatility and VIX regime comparison
   - `fig11_breach_magnitudes_and_reserves.png` - exception losses and reserve adequacy
   - `fig12_dynamic_portfolio_optimisation.png` - dynamic portfolio performance and allocation results
   - `fig13_es_reduction_and_frontier.png` - Expected Shortfall reduction and portfolio frontier
   - `fig14_cost_vs_accuracy.png` - computational cost and forecast-accuracy comparison

## Configuration

Key parameters are defined in `config.py`:

- `TICKERS`: List of 20 stock symbols
- `BENCHMARK_TICKER`: Market benchmark symbol (`SPY`)
- `VOLATILITY_TICKER`: Volatility index symbol (`^VIX`)
- `START_DATE`: Analysis start date (YYYY-MM-DD)
- `END_DATE`: Analysis end date (YYYY-MM-DD)
- `PRIMARY_CONFIDENCE`: Primary risk confidence level (default: 0.99)
- `ROLLING_WINDOW`: Rolling calibration window in trading days (default: 500)
- `GARCH_REFIT_INTERVAL`: Days between model refits and portfolio rebalances (default: 20)
- `POT_THRESHOLD_QUANTILES`: EVT sensitivity grid (default: 0.80, 0.85, 0.90, 0.95, 0.975, and 0.98)
- `PRIMARY_POT_THRESHOLD_QUANTILE`: Production POT threshold (default: 0.90)
- `GARCH_INNOVATION_DISTRIBUTIONS`: Innovation laws evaluated (`normal` and `t`)
- `VARIANCE_RECURSION`: Primary GARCH variance recursion (`corrected`; `legacy` reproduces Module 4)
- `NOTIONAL_USD`: Portfolio value used for economic impact calculations (default: USD 100,000,000)
- `MAX_ASSET_WEIGHT`: Maximum allocation to one stock (default: 0.15)
- `TURNOVER_CAP_ONE_WAY`: One-way turnover limit for the constrained strategy (default: 0.30)
- `TXN_COST_BPS`: Transaction cost per one-way rebalance (default: 10 basis points)
- `PRIMARY_ES_LP_ALPHA`: Expected Shortfall level used by the portfolio optimiser (default: 0.975)
- `DIRICHLET_SIMULATIONS`: Number of random portfolio allocations used for robustness testing (default: 100)

Modify `config.py` to adjust these parameters without editing the analysis scripts.

## Project Structure

```text
Module 6 Develop/
├── code/
│   ├── m4_core_assets.py          # Module 4 baseline reproduction pipeline
│   ├── m6_develop_pipeline.py     # Main Module 6 analysis and manifest generator
│   ├── config.py                  # Data, model, backtest, and optimisation parameters
│   ├── data_acquisition.py        # Market data download, caching, and return calculation
│   ├── risk_models.py             # VaR, GARCH, EVT, and Expected Shortfall models
│   ├── backtester.py              # Walk-forward backtesting and statistical tests
│   ├── walkforward_engine.py      # Multi-threshold and multi-innovation walk-forward sweep
│   ├── threshold_sensitivity.py   # Mean excess and EVT threshold diagnostics
│   ├── residual_analysis.py       # GARCH residual and innovation-law diagnostics
│   ├── regime_segmentation.py     # Portfolio-volatility and VIX regime analysis
│   ├── economic_impact.py         # Breach losses, concentration, and reserve adequacy
│   ├── asset_walk_forward.py      # Per-asset volatility and innovation forecasts
│   ├── portfolio_optimizer.py     # Minimum-Expected-Shortfall linear programmes
│   ├── dynamic_portfolio.py       # Rebalancing, turnover, and transaction-cost analysis
│   ├── runtime_benchmark.py       # Model timing and refit-cadence benchmarks
│   ├── tail_metrics.py            # Exact confidence intervals and tail statistics
│   ├── forecast_eval.py           # Shared forecast evaluation functions
│   ├── visualizations.py          # Module 4 figures 1-5
│   ├── visualizations_m6.py       # Module 6 figures 6-14
│   ├── requirements.txt           # Python dependencies
│   ├── pyproject.toml             # Pytest configuration
│   ├── README.md                  # This file
│   └── CONTRIBUTORS.md            # Group member information
├── tests/                         # Automated model, pipeline, and regression tests
├── data/                          # Cached inputs and generated analytical outputs
└── figures/                       # Generated publication visualisations
```

## Dependencies

- **yfinance**: Yahoo Finance data acquisition
- **pandas**: Data manipulation and time-series analysis
- **numpy**: Numerical computations and portfolio operations
- **scipy**: Statistical distributions, hypothesis tests, exact intervals, and linear programming
- **arch**: GARCH(1,1) conditional volatility estimation with Gaussian and Student-t innovations
- **statsmodels**: Residual diagnostics and econometric tests
- **matplotlib**: Publication visualisation generation
- **pytest**: Automated model, pipeline, figure, and regression tests

## Methodology

1. **Data Acquisition:** Download daily adjusted close prices for the 20 S&P 500 stocks, SPY, and VIX from Yahoo Finance and compute daily logarithmic returns
2. **Baseline Reproduction:** Reproduce the Module 4 equal-weighted portfolio and legacy GARCH variance recursion before introducing Module 6 changes
3. **Corrected Risk Estimation:** Apply the corrected GARCH(1,1) variance recursion and fit a Generalized Pareto Distribution to standardised losses above the POT threshold
4. **Threshold Sensitivity:** Evaluate six POT thresholds using mean excess diagnostics, tail-parameter stability, exceedance counts, and out-of-sample forecast performance
5. **Innovation Diagnostics:** Test standardised GARCH residuals for serial correlation, remaining ARCH effects, and distributional fit; compare Gaussian and Student-t innovations
6. **Walk-Forward Validation:** Produce one-day-ahead forecasts over a rolling 500-day window with 20-day refits and assess coverage using Kupiec POF, Christoffersen independence, conditional-coverage tests, and exact Clopper-Pearson intervals
7. **Regime Analysis:** Compare portfolio-realised-volatility states with VIX-defined Calm, Normal, and Crisis regimes and evaluate model performance within each state
8. **Economic Impact:** Convert exceptions, excess losses, and reserve adequacy into dollar values using a USD 100 million portfolio notional
9. **Dynamic Portfolio Optimisation:** Minimise Expected Shortfall under full-investment, long-only, single-name, turnover, and return-floor constraints, including transaction costs
10. **Robustness and Reproducibility:** Compare corrected and legacy recursions, run 100 Dirichlet weight simulations, benchmark computational cost, and store report values in a machine-readable manifest

### Important Data Limitation

The equity universe consists of companies that were S&P 500 constituents in 2024. It therefore contains survivorship bias because firms that were delisted, acquired, or removed from the index during 2005-2024 are not represented. The project reports this limitation explicitly and includes a mechanically selected reduced-universe control, but it does not claim to reconstruct point-in-time index membership.

## Testing

From the Module 6 deliverable root, run:

```bash
python -m pytest code/tests -q
```

If the tests are stored beside the `code/` folder in the unzipped working directory, run:

```bash
python -m pytest tests -q
```

The suite checks the walk-forward no-look-ahead property, risk-test arithmetic, threshold logic, optimisation constraints, recursion compatibility, figure labels, economic calculations, and regression stability of the published Module 4 baseline.

## Contact

For questions regarding this implementation, contact the project group members listed in `CONTRIBUTORS.md`.
