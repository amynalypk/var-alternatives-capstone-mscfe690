import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
FIGURES_DIR = os.path.join(BASE_DIR, "figures")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

TICKERS = [
    'AAPL', 'MSFT',
    'JNJ', 'PFE',
    'JPM', 'GS',
    'HD', 'DIS',
    'VZ', 'CMCSA',
    'BA', 'CAT',
    'PG', 'KO',
    'XOM', 'CVX',
    'DD', 'LIN',
    'DUK', 'SO'
]

BENCHMARK_TICKER = 'SPY'
VOLATILITY_TICKER = '^VIX'

START_DATE = '2005-01-01'
END_DATE = '2024-12-31'

CONFIDENCE_LEVELS = [0.99, 0.975]
PRIMARY_CONFIDENCE = 0.99

ROLLING_WINDOW = 500
GARCH_REFIT_INTERVAL = 20
POT_THRESHOLD_QUANTILE = 0.90

VIX_CALM_THRESHOLD = 20.0
VIX_CRISIS_THRESHOLD = 30.0

DIRICHLET_SIMULATIONS = 100
RANDOM_SEED = 42
