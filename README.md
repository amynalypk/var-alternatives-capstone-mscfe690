# Alternatives to Value-at-Risk

Final MScFE 690 capstone implementation for evaluating tail-risk measures in US large-cap equity portfolios.

## Scope

- **Universe:** 20 large-cap US equities, plus SPY and VIX
- **Data:** daily adjusted prices from 2005–2024
- **Models:** Normal VaR, Historical Simulation VaR, and GARCH(1,1)-EVT Expected Shortfall
- **Validation:** rolling walk-forward forecasts, crisis/regime analysis, threshold and innovation sensitivity, economic-impact analysis, and portfolio optimisation

The equity universe uses current S&P 500 constituents and therefore has survivorship bias. This repository does not reconstruct point-in-time index membership.

## Layout

```text
code/        Analysis and modelling modules
data/        Market-data snapshot and analytical outputs
figures/     Publication figures
tests/       Automated tests
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

From this directory:

```bash
python code/m4_core_assets.py
python code/m6_develop_pipeline.py
python code/visualizations_m6.py
```

The committed data and figures allow the submitted results to be inspected without downloading data. Yahoo Finance is used only when a fresh market-data snapshot is requested.

## Test

```bash
python -m pytest tests -q -m "not slow"
```

## Contributors

- **amynalypk**
- **Mercy Onyinyechi Uwakwe**
