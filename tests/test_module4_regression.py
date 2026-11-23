"""The Module 4 numbers, re-produced on the Module 6 code.

Marked slow because they read the cached market data and run a full walk-forward.
They exist so that a reviewer can be told, in one command, that nothing in the
refactor moved a published figure: the legacy recursion still reproduces the
Module 4 frame bit for bit, and the corrected recursion is the only thing that
changes it.

    python -m pytest tests/test_module4_regression.py -m slow -q
"""

import os

import numpy as np
import pandas as pd
import pytest

from config import M6_WALK_FORWARD_CACHE, M6_WALK_FORWARD_CACHE_LEGACY
from walkforward_engine import slice_config

BASELINE = os.path.join("data", "m4_baseline_backtest.csv")
MARKET_DATA = os.path.join("data", "sp500_market_data_2005_2024.csv")

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not os.path.exists(BASELINE), reason="baseline not frozen"),
]

M4_COLUMNS = ["Return", "Loss", "VaR_Normal", "VaR_Historical",
              "VaR_GARCH_EVT", "ES_GARCH_EVT"]


@pytest.fixture(scope="module")
def baseline():
    return pd.read_csv(BASELINE, index_col=0, parse_dates=True)


@pytest.fixture(scope="module")
def portfolio_returns():
    if not os.path.exists(MARKET_DATA):
        pytest.skip("the cached market data is not present")
    from data_acquisition import fetch_and_cache_data, process_returns
    return process_returns(fetch_and_cache_data())


class TestPublishedFrameStillReproduces:
    def test_legacy_recursion_matches_the_module_4_artefact(self, portfolio_returns,
                                                           baseline):
        frame = pd.read_csv(M6_WALK_FORWARD_CACHE_LEGACY, index_col=0, parse_dates=True)
        slice_ = slice_config(frame, "normal", 0.90, 0.99)
        for column in ("VaR_GARCH_EVT", "ES_GARCH_EVT"):
            diff = np.max(np.abs(slice_[column].to_numpy() - baseline[column].to_numpy()))
            assert diff < 1e-12, (column, diff)

    def test_the_engine_reproduces_it_without_going_through_the_cache(
            self, portfolio_returns, baseline):
        from backtester import run_walk_forward_backtest
        frame = run_walk_forward_backtest(portfolio_returns["Portfolio"],
                                          variance_recursion="legacy")
        assert list(frame.columns) == M4_COLUMNS
        assert len(frame) == len(baseline)
        diff = np.max(np.abs(frame["VaR_GARCH_EVT"].to_numpy()
                             - baseline["VaR_GARCH_EVT"].to_numpy()))
        assert diff < 1e-12, diff

    def test_module_4_headline_is_46_exceptions_in_4531_days(self, portfolio_returns):
        from backtester import run_walk_forward_backtest
        frame = run_walk_forward_backtest(portfolio_returns["Portfolio"],
                                          variance_recursion="legacy")
        exceptions = int((frame["Loss"] > frame["VaR_GARCH_EVT"]).sum())
        assert exceptions == 46
        assert len(frame) == 4531

    def test_the_corrected_recursion_is_the_only_thing_that_moves_the_count(
            self, portfolio_returns):
        from backtester import run_walk_forward_backtest
        legacy = run_walk_forward_backtest(portfolio_returns["Portfolio"],
                                           variance_recursion="legacy")
        corrected = run_walk_forward_backtest(portfolio_returns["Portfolio"],
                                             variance_recursion="corrected")
        legacy_x = int((legacy["Loss"] > legacy["VaR_GARCH_EVT"]).sum())
        corrected_x = int((corrected["Loss"] > corrected["VaR_GARCH_EVT"]).sum())
        assert (legacy_x, corrected_x) == (46, 44)
        # The two recursions must be identical except in the GARCH columns.
        assert np.allclose(legacy["VaR_Historical"], corrected["VaR_Historical"])
        assert np.allclose(legacy["VaR_Normal"], corrected["VaR_Normal"])

    def test_both_recursions_clear_kupiec_so_the_choice_is_not_a_rescue(self):
        """If only the corrected recursion passed, the switch would be a repair, not a disclosure."""
        from backtester import evaluate_risk_model_performance, run_walk_forward_backtest
        from data_acquisition import fetch_and_cache_data, process_returns
        portfolio = process_returns(fetch_and_cache_data())["Portfolio"]
        for recursion in ("legacy", "corrected"):
            frame = run_walk_forward_backtest(portfolio, variance_recursion=recursion)
            perf = evaluate_risk_model_performance(frame)["VaR_GARCH_EVT"]
            assert perf["Kupiec p-val"] > 0.05, recursion
            assert perf["Conditional Cov p-val"] > 0.05, recursion
            assert perf["Nominal Rate Inside 95% CI"], recursion


class TestSweepCacheGeometry:
    def test_both_caches_hold_the_whole_grid(self):
        for path in (M6_WALK_FORWARD_CACHE, M6_WALK_FORWARD_CACHE_LEGACY):
            if not os.path.exists(path):
                pytest.skip(f"{path} missing")
            frame = pd.read_csv(path, index_col=0, parse_dates=True)
            n_configs = frame.groupby(
                ["innovation_dist", "threshold_q", "confidence_level"]).ngroups
            assert n_configs == 20, n_configs
            assert len(frame) == 4531 * n_configs

    def test_no_cached_row_has_a_threshold_at_its_own_coverage_level(self):
        frame = pd.read_csv(M6_WALK_FORWARD_CACHE, index_col=0, parse_dates=True)
        assert (frame["threshold_q"] < frame["confidence_level"]).all()
