"""Tests for the dynamic optimisation schedule: look-ahead, drift, cost and dates.

The data here is generated, not cached, so the suite stays offline. The shape of
the matrices is the shape ``asset_walk_forward.assemble`` returns, which is what
makes the no-look-ahead result transfer to the real run.
"""

import numpy as np
import pandas as pd
import pytest

from config import REBALANCE_INTERVAL, ROLLING_WINDOW
from dynamic_portfolio import (
    STRATEGIES, breach_date_agreement_table, build_weight_schedule, scenario_block,
    simulate_book, unconditional_rows_used,
)

SCHEDULE_DAYS = 900
N_ASSETS = 8   # seven at 15% is the least that can sum to 1 under the cap
CUT = 600


def make_matrices(n_days=SCHEDULE_DAYS, n_assets=N_ASSETS, window=ROLLING_WINDOW,
                  seed=3):
    """Date-aligned z / mu / sigma / Return, the contract assemble() honours.

    The residual store starts `window` days after the return history, because a
    standardised residual only exists once the filter has been fitted. So the
    matrices carry n_days rows and the return frame carries n_days + window: that
    offset is what lets a decision price itself off trailing history.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2010-01-04", periods=n_days + window)
    z_all = pd.DataFrame(rng.standard_normal((len(dates), n_assets)), index=dates)
    sigma_all = pd.DataFrame(
        0.010 + 0.004 * np.abs(rng.standard_normal((len(dates), n_assets))), index=dates)
    mu_all = pd.DataFrame(0.0004 + 0.0006 * rng.standard_normal((len(dates), n_assets)),
                          index=dates)
    ret = mu_all + sigma_all * z_all
    schedules = {"z": z_all.iloc[window:], "mu": mu_all.iloc[window:],
                 "sigma": sigma_all.iloc[window:]}
    return schedules, ret


def optimised_strategies():
    return {k: v for k, v in STRATEGIES.items() if v["kind"] in ("mines", "minvar")}


@pytest.fixture(scope="module")
def matrices_and_returns():
    return make_matrices()


class TestNoLookAhead:
    def test_perturbing_data_after_the_cut_leaves_earlier_weights_unchanged(
            self, matrices_and_returns):
        """A weight decided on day t must not move when day t+1 is rewritten.

        Decision i reads the residual rows behind it and the one-step forecasts for
        that day. Rewriting everything from row CUT onwards therefore cannot touch
        any decision before CUT. This is the property the whole of table 18 rests
        on, and it is the one that would break if a full-sample quantity - a
        tercile, a normalisation, a covariance - leaked into the schedule.
        """
        matrices, full_returns = matrices_and_returns
        strategies = optimised_strategies()

        schedule_a, _ = build_weight_schedule(matrices, full_returns,
                                              strategies=strategies)

        rng = np.random.default_rng(7)
        perturbed = {k: v.copy() for k, v in matrices.items()}
        for key in ("z", "mu"):
            perturbed[key].iloc[CUT:] = rng.normal(
                0.0, 1.0, (SCHEDULE_DAYS - CUT, N_ASSETS))
        perturbed["sigma"].iloc[CUT:] = np.abs(rng.normal(
            0.02, 0.01, (SCHEDULE_DAYS - CUT, N_ASSETS)))
        returns_b = full_returns.copy()
        cut_in_returns = ROLLING_WINDOW + CUT
        returns_b.iloc[cut_in_returns:] = rng.normal(
            0.0, 0.05, (len(returns_b) - cut_in_returns, N_ASSETS))

        schedule_b, _ = build_weight_schedule(perturbed, returns_b,
                                              strategies=strategies)

        for name in strategies:
            a = schedule_a[name].iloc[:CUT].to_numpy()
            b = schedule_b[name].iloc[:CUT].to_numpy()
            assert np.array_equal(a, b), (
                f"{name}: weights before day {CUT} moved when future data changed")


class TestScenarioBlock:
    def test_the_first_days_use_raw_returns_then_switch_to_residuals(
            self, matrices_and_returns):
        matrices, full_returns = matrices_and_returns
        assert unconditional_rows_used(matrices, 0) == ROLLING_WINDOW
        assert unconditional_rows_used(matrices, ROLLING_WINDOW // 2) \
            == ROLLING_WINDOW // 2
        assert unconditional_rows_used(matrices, ROLLING_WINDOW) == 0

    def test_a_decision_far_enough_in_uses_only_conditional_rows(
            self, matrices_and_returns):
        matrices, full_returns = matrices_and_returns
        block = scenario_block(matrices, ROLLING_WINDOW + 5, full_returns)
        assert block.shape == (ROLLING_WINDOW, N_ASSETS)

    def test_raw_returns_early_in_the_sample_stay_in_the_block(
            self, matrices_and_returns):
        """Dropping the prefix would cut the crisis out of the optimisation sample."""
        matrices, full_returns = matrices_and_returns
        block = scenario_block(matrices, 0, full_returns)
        np.testing.assert_allclose(block, full_returns.iloc[:ROLLING_WINDOW].to_numpy())

    def test_a_day_without_enough_price_history_raises(self, matrices_and_returns):
        matrices, full_returns = matrices_and_returns
        with pytest.raises(ValueError):
            scenario_block(matrices, SCHEDULE_DAYS - 1, full_returns.iloc[:200])


class TestWeightSchedule:
    def test_every_row_is_a_full_weight_vector(self, matrices_and_returns):
        matrices, full_returns = matrices_and_returns
        schedules, failures = build_weight_schedule(
            matrices, full_returns, strategies=STRATEGIES)
        for name, frame in schedules.items():
            assert not frame.isna().any().any(), name
            np.testing.assert_allclose(frame.to_numpy().sum(axis=1), 1.0, atol=1e-8)
            assert frame.to_numpy().max() <= 0.15 + 1e-8
        assert len(failures) == 0

    def test_weights_are_held_between_rebalances(self, matrices_and_returns):
        matrices, full_returns = matrices_and_returns
        schedules, _ = build_weight_schedule(
            matrices, full_returns, strategies={"Minimum ES": STRATEGIES["Minimum ES"]})
        frame = schedules["Minimum ES"].to_numpy()
        changed = np.where(np.abs(np.diff(frame, axis=0)).sum(axis=1) > 0)[0] + 1
        assert set(changed) <= set(range(0, SCHEDULE_DAYS, REBALANCE_INTERVAL))

    def test_buy_and_hold_is_decided_once(self, matrices_and_returns):
        matrices, full_returns = matrices_and_returns
        name = "Equal weight (buy-and-hold)"
        schedules, _ = build_weight_schedule(
            matrices, full_returns, strategies={name: STRATEGIES[name]})
        frame = schedules[name].to_numpy()
        assert np.array_equal(frame, np.tile(frame[0], (SCHEDULE_DAYS, 1)))


class TestBookSimulation:
    def test_cost_is_netted_into_the_return_not_only_into_wealth(self):
        """A table reporting a return gross of a cost it also lists invites double subtraction."""
        index = pd.bdate_range("2020-01-01", periods=5)
        weights = pd.DataFrame(np.tile([0.5, 0.5], (5, 1)), columns=["A", "B"],
                               index=index)
        drift = pd.DataFrame([[0.10, -0.10], [0.02, 0.00], [0.01, 0.03],
                              [-0.05, 0.04], [0.03, -0.01]], columns=["A", "B"],
                             index=index)
        book, held = simulate_book(weights, drift, interval=2, cost_bps=1000.0)
        gross = held.to_numpy() * drift.to_numpy()
        np.testing.assert_allclose(book["Return"].to_numpy() + book["Cost"].to_numpy(),
                                   gross.sum(axis=1))
        assert (book["Cost"].to_numpy() > 0).any()

    def test_a_static_book_earns_the_weighted_return_when_cost_is_zero(self):
        weights = pd.DataFrame(
            np.tile([0.7, 0.3], (4, 1)), columns=["A", "B"],
            index=pd.bdate_range("2020-01-01", periods=4))
        drift = pd.DataFrame([[0.01, -0.02], [0.02, -0.01], [-0.03, 0.04],
                              [0.00, 0.01]], columns=["A", "B"], index=weights.index)
        book, held = simulate_book(weights, drift, cost_bps=0.0)
        assert book["Return"].iloc[0] == pytest.approx(0.7 * 0.01 + 0.3 * -0.02)
        assert book["Wealth"].iloc[0] == pytest.approx(1.0 + book["Return"].iloc[0])
        assert (book["Turnover"].to_numpy() == 0.0).all()

    def test_turnover_is_measured_one_way(self):
        index = pd.bdate_range("2020-01-01", periods=25)
        target = np.tile([0.5, 0.5], (25, 1))
        target[20:] = [0.65, 0.35]
        weights = pd.DataFrame(target, columns=["A", "B"], index=index)
        flat = pd.DataFrame(np.zeros((25, 2)), columns=["A", "B"], index=index)
        book, _held = simulate_book(weights, flat, cost_bps=0.0)
        assert book["Turnover"].iloc[20] == pytest.approx(0.15)
        assert book["Turnover"].drop(book.index[[20]]).abs().max() == 0.0

    def test_held_weights_drift_away_from_the_target_between_rebalances(self):
        index = pd.bdate_range("2020-01-01", periods=6)
        weights = pd.DataFrame(np.tile([0.5, 0.5], (6, 1)), columns=["A", "B"],
                               index=index)
        drift = pd.DataFrame([[0.20, -0.20]] * 6, columns=["A", "B"], index=index)
        _book, held = simulate_book(weights, drift, interval=5)
        assert held["A"].iloc[3] > 0.5
        assert held["A"].iloc[5] == pytest.approx(0.5)

    def test_the_backtest_refuses_the_legacy_recursion(self):
        """A dynamic-book row scored on the legacy recursion is not comparable to table 11."""
        from dynamic_portfolio import run_dynamic_book_walk_forward
        index = pd.bdate_range("2020-01-01", periods=600)
        weights = pd.DataFrame(0.5, columns=["A", "B"], index=index)
        returns = pd.DataFrame(0.001, columns=["A", "B"], index=index)
        with pytest.raises(ValueError):
            run_dynamic_book_walk_forward(weights, returns, recursion="legacy")


def agreement_input():
    """Three books, six days, and exception sets that can be checked on the page.

    Equal weight and minimum variance clear their 2% forecast on the same two days;
    minimum ES clears on a different calendar. A day whose forecast is missing has to
    be dropped rather than counted, which is why equal weight reads 2 exceptions and
    not 3 despite a 50% loss on the last day.
    """
    dates = pd.bdate_range("2011-01-03", periods=6)
    loss = [0.03, 0.005, 0.005, 0.04, 0.005, 0.50]
    var = {
        "Equal weight (rebalanced)": [0.02, 0.02, 0.02, 0.02, 0.02, None],
        "Minimum variance": [0.02, 0.02, 0.02, 0.02, 0.02, None],
        "Minimum ES": [0.05, 0.004, 0.004, 0.02, 0.02, 0.02],
    }
    frames = {}
    for name, series in var.items():
        frames[name] = pd.DataFrame({"Loss": loss, "VaR_GARCH_EVT": series},
                                    index=dates)
    return {"realised_frames": frames}


class TestBreachDateAgreement:
    """Same number of exceptions and same exception days are different claims.

    Table 18's realised block shows 43 exceptions for three books, which reads like
    a copy-paste defect unless the dates are compared.
    """

    @pytest.fixture(scope="class")
    def table(self):
        return breach_date_agreement_table(agreement_input())

    def test_each_unordered_pair_appears_once_in_book_order(self, table):
        assert list(table.index) == [("Equal weight (rebalanced)", "Minimum variance"),
                                     ("Equal weight (rebalanced)", "Minimum ES"),
                                     ("Minimum variance", "Minimum ES")]

    def test_two_books_that_breach_together_score_a_jaccard_of_one(self, table):
        row = table.loc[("Equal weight (rebalanced)", "Minimum variance")]
        assert row["Shared exception days"] == 2
        assert row["Only in A"] == 0 and row["Only in B"] == 0
        assert row["Jaccard"] == pytest.approx(1.0)

    def test_a_matching_count_on_different_days_reads_as_a_small_overlap(self, table):
        row = table.loc[("Equal weight (rebalanced)", "Minimum ES")]
        assert (row["Breaches A"], row["Breaches B"]) == (2, 4)
        assert row["Shared exception days"] == 1
        assert row["Jaccard"] == pytest.approx(1 / 5)

    def test_a_day_without_a_forecast_cannot_be_an_exception(self, table):
        assert table.loc[:, "Breaches A"].iloc[0] == 2

    def test_the_pieces_add_up_to_each_books_own_count(self, table):
        for (_a, _b), row in table.iterrows():
            assert row["Shared exception days"] + row["Only in A"] == row["Breaches A"]
            assert row["Shared exception days"] + row["Only in B"] == row["Breaches B"]

    def test_two_silent_books_give_no_ratio_rather_than_a_division_by_zero(self):
        quiet = agreement_input()
        for frame in quiet["realised_frames"].values():
            frame["VaR_GARCH_EVT"] = 1.0
        table = breach_date_agreement_table(quiet)
        assert (table["Shared exception days"] == 0).all()
        assert table["Jaccard"].isna().all()

    def test_another_frames_key_can_be_scored_instead(self):
        payload = {"risk_frames": agreement_input()["realised_frames"]}
        table = breach_date_agreement_table(payload, frames_key="risk_frames")
        assert len(table) == 3
