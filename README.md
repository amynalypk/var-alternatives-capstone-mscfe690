# MScFE 690 Capstone Project - Module 3: Literature Review and Competitor Analysis

## Project Information

**Course:** MScFE 690, Capstone Project  
**Track:** Volatility and Risk (Track 2)  
**Topic 3:** Developing Alternatives to VaR  
**Student Group Number:** 17845


## Project Overview

This project develops and validates alternative risk measures to Value-at-Risk (VaR) for medium-term equity portfolios. The research addresses VaR's documented failures during crisis periods by proposing a composite metric combining Expected Shortfall (ES), Extreme Value Theory (EVT), and GARCH-based volatility filtering.

## Module 3 Deliverables

This code implements the initial data acquisition and baseline VaR calculations referenced in the M3 Literature Review and Competitor Analysis document.

### Implementation Scope

- **Universe:** 5 representative US large-cap stocks (SPY, AAPL, MSFT, JPM, XOM)
- **Time Period:** January 2005 - December 2024 (daily adjusted close prices)
- **Data Source:** Yahoo Finance via `yfinance` library
- **Baseline Models:** Parametric VaR and Historical Simulation VaR at 99% confidence level

## Installation

Install required Python dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the analysis script:

```bash
python m3.py
```

### Output

The script generates:
1. Console output with Parametric and Historical VaR values
2. `portfolio_returns_distribution.png` - visualization of portfolio return distribution with VaR thresholds

## Configuration

Key parameters are defined at the top of `m3.py`:

- `TICKERS`: List of stock symbols
- `START_DATE`: Analysis start date (YYYY-MM-DD)
- `END_DATE`: Analysis end date (YYYY-MM-DD)
- `CONFIDENCE_LEVEL`: VaR confidence level (default: 0.99)

Modify `config.py` to adjust these parameters without editing the main script.

## Project Structure

```
code/
├── m3.py                    # Main analysis script
├── requirements.txt         # Python dependencies
├── config.py               # Configuration parameters
├── README.md               # This file
└── CONTRIBUTORS.md         # Group member information
```

## Dependencies

- **yfinance**: Yahoo Finance data acquisition
- **pandas**: Data manipulation and time series analysis
- **numpy**: Numerical computations
- **matplotlib**: Visualization
- **scipy**: Statistical distributions (normal distribution for parametric VaR)

## Methodology

1. **Data Acquisition**: Download daily adjusted close prices from Yahoo Finance
2. **Return Calculation**: Compute daily log returns
3. **Portfolio Construction**: Equal-weighted portfolio allocation
4. **VaR Calculation**:
   - Parametric VaR: Assumes normal distribution of returns
   - Historical VaR: Empirical quantile from historical data

## Contact

For questions regarding this implementation, contact the project group members listed in `CONTRIBUTORS.md`.


