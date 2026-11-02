import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
FIGURES_DIR = os.path.join(BASE_DIR, "figures")




if not os.path.isdir(DATA_DIR) and os.path.isdir(
        os.path.join(os.path.dirname(BASE_DIR), "data")):
    BASE_DIR = os.path.dirname(BASE_DIR)
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











POT_THRESHOLD_QUANTILES = [0.80, 0.85, 0.90, 0.95, 0.975, 0.98]
PRIMARY_POT_THRESHOLD_QUANTILE = 0.90


GARCH_INNOVATION_DISTRIBUTIONS = ["normal", "t"]
PRIMARY_GARCH_INNOVATION_DISTRIBUTION = "normal"








VARIANCE_RECURSION = "corrected"


PORTFOLIO_VOL_WINDOW = 20          
PORTFOLIO_REGIME_BANDS = 3         
PORTFOLIO_REGIME_CAL_DAYS = 500    




STRESS_WINDOWS = (("2008 GFC", "2008-09-01", "2009-06-30"),
                  ("2020 COVID", "2020-02-15", "2020-04-30"))


LB_LAGS = [1, 5, 10, 20]
ARCH_LM_LAGS = 5
CLOPPER_PEARSON_ALPHA = 0.05


REBALANCE_INTERVAL = GARCH_REFIT_INTERVAL   
MAX_ASSET_WEIGHT = 0.15
MIN_ASSET_WEIGHT = 0.00
TURNOVER_CAP_ONE_WAY = 0.30        
TXN_COST_BPS = 10.0                
NOTIONAL_USD = 100_000_000.0
ES_LP_ALPHAS = [0.99, 0.975, 0.95]
PRIMARY_ES_LP_ALPHA = 0.975



ASSET_WF_INNOVATION_DISTRIBUTION = "t"
ASSET_SCENARIO_WINDOW = ROLLING_WINDOW


BENCH_REPEATS_FAST = 50
BENCH_REPEATS_SLOW = 3
BENCH_WARMUP = 3
BENCH_REFIT_INTERVALS = [1, 5, 20, 60]



M4_BASELINE_BACKTEST = os.path.join(DATA_DIR, "backtest_results_500w.csv")
M6_WALK_FORWARD_CACHE = os.path.join(DATA_DIR, "m6_multi_config_walkforward.csv")
M6_WALK_FORWARD_CACHE_LEGACY = os.path.join(
    DATA_DIR, "m6_multi_config_walkforward_legacy.csv"
)
M6_ASSET_STORE_DIR = os.path.join(DATA_DIR, "asset_wf")
M6_METRICS_MANIFEST = os.path.join(DATA_DIR, "module6_metrics_manifest.json")


def validate_pot_configuration(threshold_quantile, confidence_level):
    
    if not threshold_quantile < confidence_level:
        raise ValueError(
            f"POT threshold quantile {threshold_quantile} must be strictly "
            f"below the confidence level {confidence_level}; the tail estimate "
            "cannot extrapolate beyond the threshold it was fitted at."
        )
