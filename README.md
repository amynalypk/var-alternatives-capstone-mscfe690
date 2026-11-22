# Developing Alternatives to Value-at-Risk

**MScFE 690 Capstone Project: Module 7 Final Submission**  
**Track 2: Volatility and Risk, Topic 3**  
**Group 17845: Amin Ali & Mercy Onyinyechi Uwakwe**  
**WorldQuant University: Master of Science in Financial Engineering**  
**Submission Date: November 2026**

---

## Abstract

This repository contains the complete Python implementation for our capstone thesis investigating alternatives to Value-at-Risk (VaR) for tail-risk measurement in US large-cap equity portfolios. We demonstrate that **GARCH(1,1)-filtered Extreme Value Theory (EVT) with Expected Shortfall (ES)** outperforms traditional parametric and non-parametric VaR models, particularly during crisis regimes.

**Key findings:**
- GARCH-EVT VaR achieves **1.02% breach rate** vs 2.91% (Normal VaR) at 99% confidence
- During crisis periods (VIX ≥ 30), GARCH-EVT reduces breaches from **12.18% to 2.99%** (4× improvement)
- Kupiec test: **p = 0.92** (cannot reject correct coverage)
- Robust across 100 Dirichlet-randomized portfolios (mean breach rate: 0.92% ± 0.10%)

---

## Project Scope

### Research Question
*Can a composite risk measure built on GARCH volatility filtering and Extreme Value Theory provide more reliable tail-risk estimates than traditional VaR, particularly during market stress?*

### Data & Universe
- **Assets:** 20 S&P 500 constituents (diversified across 10 GICS sectors) + SPY (benchmark) + ^VIX (regime proxy)
- **Period:** January 1, 2005, December 31, 2024 (5,031 daily observations)
- **Crisis windows:** 2008 Global Financial Crisis (Sep 2008 – Jun 2009), 2020 COVID-19 crash (Feb – Apr 2020)
- **Source:** Yahoo Finance (daily adjusted close prices)
- **Limitation:** Survivorship bias present, universe uses current S&P 500 constituents, not point-in-time membership

### Models Evaluated
1. **Parametric VaR (Normal)** — Assumes Gaussian returns
2. **Historical Simulation VaR** — Non-parametric empirical quantile
3. **GARCH(1,1)-EVT VaR** — Dynamic volatility filter + Generalized Pareto Distribution (GPD) tail fit
4. **GARCH(1,1)-EVT Expected Shortfall** — Conditional tail expectation (coherent risk measure)

### Validation Framework
- **Walk-forward backtesting:** Rolling 500-day estimation window, 4,531 out-of-sample forecasts
- **Statistical tests:** Kupiec Proportion of Failures (POF), Christoffersen conditional coverage
- **Regime analysis:** VIX-based calm/normal/crisis segmentation + historical stress overlays
- **Robustness:** 100 Dirichlet-randomized portfolio weights
- **Model comparison:** Diebold-Mariano, Model Confidence Set (MCS)
- **Economic impact:** Capital reserve adequacy, worst-breach analysis, turnover-adjusted optimization

---

## Repository Structure

```text
.
├── code/                          # Analysis and modelling modules
│   ├── config.py                  # Centralized configuration (universe, dates, model params)
│   ├── data_acquisition.py        # Yahoo Finance ingestion, returns processing
│   ├── risk_models.py             # GARCH(1,1) volatility, EVT-POT tail fitting
│   ├── backtester.py              # Walk-forward engine, Kupiec/Christoffersen tests
│   ├── walkforward_engine.py      # Multi-configuration sensitivity analysis
│   ├── tail_metrics.py            # Breach registers, Clopper-Pearson intervals
│   ├── regime_segmentation.py     # VIX-based regime detection, HMM clustering
│   ├── residual_analysis.py       # Ljung-Box, ARCH-LM, distributional diagnostics
│   ├── threshold_sensitivity.py   # POT threshold selection, mean excess loss profiles
│   ├── forecast_eval.py           # Diebold-Mariano, Model Confidence Set tests
│   ├── economic_impact.py         # Capital reserve adequacy, worst-breach analysis
│   ├── dynamic_portfolio.py       # Time-varying weight optimization, turnover constraints
│   ├── portfolio_optimizer.py     # Mean-CVaR, risk parity, max Sharpe strategies
│   ├── visualizations.py          # Publication-quality figures (300 DPI)
│   ├── visualizations_m6.py       # Module 6 extended figure suite
│   ├── m4_core_assets.py          # **[MAIN] Module 4 baseline pipeline**
│   ├── m6_develop_pipeline.py     # **[MAIN] Module 6 extended metrics manifest**
│   └── runtime_benchmark.py       # GARCH refit interval profiling
├── data/                          # Market-data snapshots and cached results
│   ├── sp500_market_data_2005_2024.csv        # Raw price data (committed)
│   ├── backtest_results_500w.csv              # Walk-forward forecasts (committed)
│   ├── module4_metrics_manifest.json          # Module 4 baseline metrics
│   └── module6_metrics_manifest.json          # Module 6 extended analytics
├── figures/                       # Publication figures (committed, 300 DPI)
│   ├── fig1_portfolio_vs_market_drawdowns.png
│   ├── fig2_fat_tailed_diagnostics_gpd_fit.png
│   ├── fig3_rolling_var_es_backtest_crises.png
│   ├── fig4_backtest_violations_by_regime.png
│   └── fig5_dirichlet_robustness_test.png
├── tests/                         # Automated regression and validation tests
│   ├── test_backtester.py         # Walk-forward schema, regime segmentation
│   ├── test_risk_models.py        # GARCH convergence, EVT parameter bounds
│   ├── test_dynamic_portfolio.py  # Optimization constraints, turnover caps
│   └── test_m6_pipeline.py        # End-to-end pipeline integration tests
├── requirements.txt               # Python dependencies (pinned versions)
├── pyproject.toml                 # pytest configuration
├── README.md                      # This file
├── CONTRIBUTORS.md                # Team roles and responsibilities
└── .gitignore                     # Excludes .venv, __pycache__, .pytest_cache
```

---

## Installation & Setup

### Prerequisites
- **Python:** 3.10 or later (tested on 3.11)
- **Operating System:** Windows 10/11, macOS, or Linux
- **Memory:** Minimum 4 GB RAM (8 GB recommended for full pipeline)

### Step 1: Clone the Repository
```bash
git clone https://github.com/amynalypk/var-alternatives-capstone-mscfe690.git
cd var-alternatives-capstone-mscfe690
git checkout module7
```

### Step 2: Create Virtual Environment
```bash
python -m venv .venv

# Activate:
# Windows (PowerShell):   .venv\Scripts\Activate.ps1
# Windows (Git Bash):     source .venv/Scripts/activate
# macOS/Linux:            source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Key dependencies:**
- `numpy`, `pandas` — Data manipulation
- `scipy`, `statsmodels` — Statistical tests (Kupiec, Ljung-Box, ARCH-LM)
- `arch` — GARCH volatility models
- `scikit-learn` — Regime clustering (KMeans, HMM)
- `matplotlib`, `seaborn` — Visualizations
- `yfinance` — Market data ingestion
- `pytest` — Testing framework

---

## Usage

### Quick Start: Reproduce Module 4 Baseline Results
```bash
cd code
python m4_core_assets.py
```

**Expected runtime:** ~15 seconds (with cached data)  
**Output:**
- Console summary: GARCH parameters, EVT tail index, Kupiec test results, regime breakdown
- 5 publication figures saved to `figures/` (300 DPI PNG)
- Metrics manifest: `data/module4_metrics_manifest.json`

### Full Analysis: Module 6 Extended Pipeline
```bash
cd code
python m6_develop_pipeline.py
```

**Expected runtime:** ~3–5 minutes (first run, no cache)  
**Output:**
- Extended metrics manifest: `data/module6_metrics_manifest.json`
- Threshold sensitivity tables, innovation distribution comparisons
- Residual diagnostics, forecast evaluation scores
- Economic impact metrics (capital reserves, worst breaches)

**Options:**
```bash
# Recompute everything (ignore cache):
python m6_develop_pipeline.py --force

# Run specific sections only:
python m6_develop_pipeline.py --only threshold,iid

# Dry run (compute without writing manifest):
python m6_develop_pipeline.py --no-write
```

### Generate Additional Visualizations
```bash
cd code
python visualizations_m6.py
```

**Output:** Extended figure suite covering:
- Threshold sensitivity (mean excess loss profiles)
- GARCH innovation distribution comparisons (Normal vs Student-t)
- Regime-conditional VaR coverage
- Economic impact waterfall charts

### Fresh Data Download (Optional)
By default, the pipeline uses **committed cached data** (`data/sp500_market_data_2005_2024.csv`) to ensure reproducibility. To fetch fresh data from Yahoo Finance:

```bash
cd code
python -c "from data_acquisition import fetch_and_cache_data; fetch_and_cache_data(force_download=True)"
```

️ **Warning:** Fresh downloads may introduce minor discrepancies due to Yahoo Finance data revisions.

---

## Testing

### Run Fast Test Suite (Recommended)
```bash
python -m pytest tests -q -m "not slow"
```

**Expected:** 200 tests pass in ~65 seconds  
**Coverage:**
- Walk-forward backtest schema validation (Module 4 contract)
- GARCH convergence and parameter bounds
- EVT shape clamp logic (ξ < 1 enforcement)
- Regime segmentation (VIX bands, HMM agreement)
- Dirichlet robustness (100 portfolios)
- Dynamic portfolio optimization constraints
- Forecast evaluation edge cases

### Run Full Test Suite (Including Slow Tests)
```bash
python -m pytest tests -v
```

**Expected runtime:** ~5–10 minutes

### Test Coverage Report
```bash
python -m pytest tests --cov=code --cov-report=html
```

---

## Key Results Summary

### Backtesting Performance (99% Confidence, 4,531 Out-of-Sample Days)

| Model | Breaches | Rate | Kupiec p-value | Mean Excess Loss |
|:---|---:|---:|---:|---:|
| **Normal VaR** | 132 | 2.91% | 0.000 ❌ | 1.12% |
| **Historical VaR** | 78 | 1.72% | 0.000 ❌ | 1.22% |
| **GARCH-EVT VaR** | 46 | 1.02% | **0.918 ✅** | 0.81% |
| **GARCH-EVT ES** | 20 | 0.44% | — | 0.82% |

### Crisis-Regime Performance (VIX ≥ 30, N = 435 Days)

| Model | Breaches | Rate | Mean Excess Loss |
|:---|---:|---:|---:|
| **Normal VaR** | 53 | 12.18% ❌ | 2.03% |
| **Historical VaR** | 37 | 8.51% ❌ | 2.06% |
| **GARCH-EVT VaR** | 13 | **2.99% ✅** | 1.54% |
| **GARCH-EVT ES** | 8 | **1.84% ✅** | — |

**Interpretation:** GARCH-EVT reduces crisis-regime breaches by **4× vs Normal VaR** (12.18% → 2.99%).

### 2020 COVID-19 Crash (N = 52 Days, Feb 15 – Apr 30, 2020)

| Model | Breaches | Rate |
|:---|---:|---:|
| **Normal VaR** | 13 | 25.00% ❌ |
| **Historical VaR** | 10 | 19.23% ❌ |
| **GARCH-EVT VaR** | 3 | **5.77% ✅** |

**Interpretation:** Normal VaR failed **1 in 4 days** during COVID crash; GARCH-EVT failed **1 in 17 days**.

---

## Reproducibility

- **Random seed:** Fixed at 42 (`config.py`)
- **Data snapshot:** Committed to `data/` (no internet required to reproduce)
- **GARCH optimizer:** `scipy.optimize.minimize` with `SLSQP` (deterministic)
- **EVT threshold:** Fixed at 90th percentile (configurable in `config.py`)
- **Python version:** Tested on 3.10.11, 3.11.4

To verify exact replication:
```bash
python code/m4_core_assets.py > output.txt 2>&1
diff output.txt tests/expected_m4_output.txt
```

---

## Data Sources & Acknowledgments

| Source | Use | License |
|:---|:---|:---|
| **Yahoo Finance** (`yfinance`) | Daily adjusted close prices (20 stocks + SPY + ^VIX) | Free, no API key required |
| **CBOE** | Historical VIX levels (regime labeling) | Public data, attribution required |
| **Kenneth French Data Library** | Factor returns (robustness cross-check) | Academic use permitted |
| **FRED (St. Louis Fed)** | Risk-free rate (T-bill yields) | Public domain |

**Course acknowledgment:**  
This work was completed as part of **MScFE 690, Capstone Project** at **WorldQuant University**. All analysis, code, and interpretation are the original work of Group 17845.


## License

**Academic Use Only** — This repository is submitted for academic evaluation as part of the MScFE 690 Capstone Course at WorldQuant University. Redistribution or commercial use is prohibited without prior written consent from the authors.

---

## Contact & Support

**Project Repository:** [https://github.com/amynalypk/var-alternatives-capstone-mscfe690](https://github.com/amynalypk/var-alternatives-capstone-mscfe690)  
**Branch:** `module7` (final submission)

For questions or access requests, see `CONTRIBUTORS.md` for team member details.

---

**Last Updated:** November 22, 2026  
**Submission Status:** Module 7 (Final Presentation Report)
