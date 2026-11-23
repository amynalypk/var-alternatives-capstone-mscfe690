

"""Run and cache per-asset walk-forward GARCH forecasts and standardised innovations."""
import os
import time

import numpy as np
import pandas as pd

from config import (
    TICKERS, ROLLING_WINDOW, GARCH_REFIT_INTERVAL, VARIANCE_RECURSION,
    M6_ASSET_STORE_DIR, ASSET_WF_INNOVATION_DISTRIBUTION,
)
from risk_models import fit_garch11_state

ASSET_FIELDS = ["Return", "mu", "sigma", "z"]


def _asset_path(values, window=ROLLING_WINDOW, refit_interval=GARCH_REFIT_INTERVAL,
                dist=ASSET_WF_INNOVATION_DISTRIBUTION,
                recursion=VARIANCE_RECURSION):
    
    """Compute or assemble the _asset_path result used by the asset_walk_forward analysis."""
    if recursion not in ("legacy", "corrected"):
        raise ValueError(f"unknown variance_recursion: {recursion}")

    n_total = len(values)
    n_test = n_total - window
    mu_out = np.full(n_test, np.nan)
    sigma_out = np.full(n_test, np.nan)
    z_out = np.full(n_test, np.nan)

    state = None
    refit_day = -999

    for i in range(n_test):
        train_slice = values[i: window + i]
        refitted_today = (i - refit_day >= refit_interval) or state is None

        if refitted_today:
            state = fit_garch11_state(train_slice, dist=dist)
            state["sigma_var"] = state["cond_vol"][-1] ** 2
            refit_day = i

        eps = train_slice[-1] - state["mu"]
        if recursion == "legacy" and not refitted_today:
            state["sigma_var"] = (state["omega"] + state["alpha"] * eps ** 2
                                  + state["beta"] * state["sigma_var"])
        sigma_next = np.sqrt(
            state["omega"] + state["alpha"] * eps ** 2 + state["beta"] * state["sigma_var"]
        )
        if recursion == "corrected":
            state["sigma_var"] = sigma_next ** 2

        mu_out[i] = state["mu"]
        sigma_out[i] = sigma_next
        z_out[i] = (values[window + i] - state["mu"]) / sigma_next

    return mu_out, sigma_out, z_out


def run_asset_walk_forward(returns_df, tickers=TICKERS,
                           dist=ASSET_WF_INNOVATION_DISTRIBUTION,
                           window=ROLLING_WINDOW, refit_interval=GARCH_REFIT_INTERVAL,
                           recursion=VARIANCE_RECURSION,
                           store_dir=M6_ASSET_STORE_DIR, force=False):
    
    """Compute or assemble the run_asset_walk_forward result used by the asset_walk_forward analysis."""
    os.makedirs(store_dir, exist_ok=True)
    store = {}
    n_cached = 0
    t_start = time.perf_counter()

    for j, ticker in enumerate(tickers, start=1):
        path = _store_path(store_dir, ticker, dist, window, refit_interval, recursion)
        if os.path.exists(path) and not force:
            store[ticker] = pd.read_csv(path, index_col=0, parse_dates=True)
            n_cached += 1
            continue

        values = np.asarray(returns_df[ticker].to_numpy(dtype=float))
        dates = returns_df.index[window:]
        mu, sigma, z = _asset_path(values, window=window, refit_interval=refit_interval,
                                   dist=dist, recursion=recursion)
        frame = pd.DataFrame({
            "Return": values[window:], "mu": mu, "sigma": sigma, "z": z,
        }, index=pd.DatetimeIndex(dates, name="Date"))
        frame.to_csv(path)
        store[ticker] = frame
        print(f"[AssetWF] {ticker}: {len(frame):,} days fitted "
              f"({time.perf_counter() - t_start:.0f}s elapsed)")

    print(f"[AssetWF] {len(store)} assets, {n_cached} read from cache, "
          f"{time.perf_counter() - t_start:.1f}s total")
    return store


def _store_suffix(dist, window, refit_interval, recursion):
    """Compute or assemble the _store_suffix result used by the asset_walk_forward analysis."""
    return f"_dist-{dist}_win-{window}_refit-{refit_interval}_{recursion}.csv"


def _store_path(store_dir, ticker, dist, window, refit_interval, recursion):
    
    """Compute or assemble the _store_path result used by the asset_walk_forward analysis."""
    return os.path.join(
        store_dir, f"{ticker}{_store_suffix(dist, window, refit_interval, recursion)}")


def list_store(store_dir=M6_ASSET_STORE_DIR, dist=ASSET_WF_INNOVATION_DISTRIBUTION,
               window=ROLLING_WINDOW, refit_interval=GARCH_REFIT_INTERVAL,
               recursion=VARIANCE_RECURSION):
    
    """Compute or assemble the list_store result used by the asset_walk_forward analysis."""
    if not os.path.isdir(store_dir):
        return []
    suffix = _store_suffix(dist, window, refit_interval, recursion)
    return sorted(name[:-len(suffix)] for name in os.listdir(store_dir)
                  if name.endswith(suffix))


def assemble(store):
    
    """Compute or assemble the assemble result used by the asset_walk_forward analysis."""
    common = None
    for frame in store.values():
        common = frame.index if common is None else common.intersection(frame.index)
    common = pd.DatetimeIndex(sorted(common))
    out = {}
    for field in ASSET_FIELDS:
        out[field] = pd.DataFrame(
            {t: store[t][field].reindex(common) for t in store},
            index=common,
        )
    return out


def load_asset_store(tickers=TICKERS, dist=ASSET_WF_INNOVATION_DISTRIBUTION,
                     window=ROLLING_WINDOW, refit_interval=GARCH_REFIT_INTERVAL,
                     recursion=VARIANCE_RECURSION, store_dir=M6_ASSET_STORE_DIR):
    
    """Compute or assemble the load_asset_store result used by the asset_walk_forward analysis."""
    kwargs = dict(dist=dist, window=window, refit_interval=refit_interval,
                  recursion=recursion)
    missing = [t for t in tickers
               if not os.path.exists(_store_path(store_dir, t, **kwargs))]
    if missing:
        raise FileNotFoundError(
            f"no cached asset paths for {missing} under this configuration; run "
            f"run_asset_walk_forward first")
    return {t: pd.read_csv(_store_path(store_dir, t, **kwargs),
                           index_col=0, parse_dates=True) for t in tickers}


if __name__ == "__main__":
    from data_acquisition import fetch_and_cache_data, process_returns

    returns_df = process_returns(fetch_and_cache_data())
    store = run_asset_walk_forward(returns_df)
    matrices = assemble(store)
    summary = pd.DataFrame({
        "mean sigma (%)": matrices["sigma"].mean() * 100.0,
        "mean mu (bps)": matrices["mu"].mean() * 10000.0,
        "z kurtosis": matrices["z"].kurtosis(),
        "z std": matrices["z"].std(),
    })
    print(summary.to_string(float_format=lambda v: f"{v:,.4f}"))
    print(f"\ncorrelation matrix mean off-diagonal: "
          f"{matrices['z'].corr().to_numpy()[np.triu_indices(len(TICKERS), 1)].mean():.3f}")
