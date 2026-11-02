"""Shared synthetic data for the Module 6 tests.

Everything here is generated, not downloaded, so the suite runs offline and in
seconds. A GARCH(1,1) path driven by Student-t innovations is the right fixture
because it has the two properties the models are asked to find: volatility
clustering for the filter and excess kurtosis for the tail. Real data is used
only by the tests marked slow, which check the published Module 4 numbers.
"""

import numpy as np
import pandas as pd
import pytest

TRADING_DAYS = 252


def simulate_garch_t(n, seed=42, mu=0.0005, omega=1e-5, alpha=0.08, beta=0.90, nu=5.0):
    """A GARCH(1,1) path with standardised t(nu) innovations.

    The unconditional variance is honoured on purpose. A fixture whose variance
    does not match its own coefficients makes a fitted alpha + beta look wrong for
    reasons that have nothing to do with the estimator, and the first such mistake
    in this project's history cost a day of debugging.
    """
    rng = np.random.default_rng(seed)
    uncond = omega / (1.0 - alpha - beta)
    sigma2 = np.empty(n)
    eps = np.empty(n)
    x = np.empty(n)
    sigma2[0] = uncond
    for t in range(n):
        if t > 0:
            sigma2[t] = omega + alpha * eps[t - 1] ** 2 + beta * sigma2[t - 1]
        # rng.standard_t is already unit-variance only after scaling by (nu-2)/nu.
        z = rng.standard_t(nu) * np.sqrt((nu - 2.0) / nu)
        eps[t] = np.sqrt(sigma2[t]) * z
        x[t] = mu + eps[t]
    return x


@pytest.fixture(scope="session")
def returns_array():
    return simulate_garch_t(1200)


@pytest.fixture(scope="session")
def returns_series(returns_array):
    index = pd.bdate_range("2015-01-05", periods=len(returns_array))
    return pd.Series(returns_array, index=index, name="Portfolio")


@pytest.fixture(scope="session")
def returns_frame(returns_series):
    """A frame shaped like process_returns output, for the call sites that want one."""
    rng = np.random.default_rng(1)
    n = len(returns_series)
    cols = [f"A{i:02d}" for i in range(6)]
    common = returns_series.to_numpy()
    assets = np.column_stack([0.6 * common + 0.8 * rng.normal(0, common.std(), n)
                              for _ in cols])
    frame = pd.DataFrame(assets, index=returns_series.index, columns=cols)
    frame["Portfolio"] = returns_series.to_numpy()
    frame["^VIX"] = 15.0 + 40.0 * np.abs(common - common.mean()) / common.std()
    return frame


@pytest.fixture()
def std_resid():
    """Standardised residuals with a visible right tail, as the POT step receives them."""
    rng = np.random.default_rng(7)
    z = rng.standard_t(4, size=800) * np.sqrt(2.0 / 4.0)
    return pd.Series(np.asarray(z), index=pd.RangeIndex(len(z)))
