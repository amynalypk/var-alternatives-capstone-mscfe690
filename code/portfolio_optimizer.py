

import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize
from sklearn.covariance import LedoitWolf

from config import (
    MAX_ASSET_WEIGHT, MIN_ASSET_WEIGHT, PRIMARY_ES_LP_ALPHA,
)

LP_SUCCESS_STATUSES = (0,)


def build_scenarios(mu, sigma, z_window):
    
    mu = np.asarray(mu, dtype=float).ravel()
    sigma = np.asarray(sigma, dtype=float).ravel()
    z = np.asarray(z_window, dtype=float)
    if z.ndim != 2:
        raise ValueError("z_window must be a K-by-N matrix")
    if z.shape[1] != mu.size or mu.size != sigma.size:
        raise ValueError("scenario matrix has a different asset count to mu/sigma")
    if not (np.isfinite(mu).all() and np.isfinite(sigma).all() and (sigma > 0).all()):
        raise ValueError("mu/sigma forecast is not finite and positive for every asset")
    usable_rows = np.isfinite(z).all(axis=1)
    if not usable_rows.any():
        raise ValueError("no usable residual rows in the scenario window")
    return mu + z[usable_rows] * sigma


def portfolio_losses(weights, scenarios):
    
    return -np.asarray(scenarios, dtype=float) @ np.asarray(weights, dtype=float).ravel()


def empirical_es(weights, scenarios, alpha=PRIMARY_ES_LP_ALPHA):
    
    losses = portfolio_losses(weights, scenarios)
    tail_weight = 1.0 / ((1.0 - alpha) * losses.size)
    candidates = np.unique(losses)
    values = candidates + tail_weight * np.maximum(losses[None, :] - candidates[:, None], 0.0).sum(axis=1)
    return float(values.min())


def min_es_lp(scenarios, alpha=PRIMARY_ES_LP_ALPHA, min_weight=MIN_ASSET_WEIGHT,
              max_weight=MAX_ASSET_WEIGHT, w_prev=None, turnover_cap=None,
              expected_returns=None, return_floor=None):
    
    scenarios = np.asarray(scenarios, dtype=float)
    k, n = scenarios.shape
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must lie in (0, 1), got {alpha}")
    if not min_weight <= max_weight:
        raise ValueError("min_weight exceeds max_weight")
    if n * max_weight < 1.0 - 1e-12:
        raise ValueError(
            f"weight cap {max_weight} admits no portfolio summing to 1 with {n} assets")
    if turnover_cap is not None and w_prev is None:
        raise ValueError("a turnover cap needs the weights it is measured against")

    use_turnover = turnover_cap is not None
    n_extra = n if use_turnover else 0
    n_var = n + 1 + k + n_extra
    tail_weight = 1.0 / ((1.0 - alpha) * k)

    cost = np.zeros(n_var)
    cost[n] = 1.0
    cost[n + 1:n + 1 + k] = tail_weight

    a_ub = np.zeros((k, n_var))
    a_ub[:, :n] = -scenarios
    a_ub[:, n] = -1.0
    a_ub[np.arange(k), n + 1 + np.arange(k)] = -1.0
    b_ub = np.zeros(k)

    if use_turnover:
        offset = n + 1 + k
        rows = np.zeros((2 * n + 1, n_var))
        rhs = np.zeros(2 * n + 1)
        for i in range(n):
            rows[i, i] = 1.0
            rows[i, offset + i] = -1.0
            rhs[i] = w_prev[i]
            rows[n + i, i] = -1.0
            rows[n + i, offset + i] = -1.0
            rhs[n + i] = -w_prev[i]
        rows[2 * n, offset:offset + n] = 1.0
        rhs[2 * n] = turnover_cap
        a_ub = np.vstack([a_ub, rows])
        b_ub = np.concatenate([b_ub, rhs])

    if return_floor is not None:
        if expected_returns is None:
            raise ValueError("a return floor needs the expected returns to floor against")
        row = np.zeros((1, n_var))
        row[0, :n] = -np.asarray(expected_returns, dtype=float).ravel()
        a_ub = np.vstack([a_ub, row])
        b_ub = np.concatenate([b_ub, [-float(return_floor)]])

    a_eq = np.zeros((1, n_var))
    a_eq[0, :n] = 1.0
    bounds = [(min_weight, max_weight)] * n + [(None, None)] + [(0, None)] * k
    if use_turnover:
        bounds += [(0, None)] * n

    res = linprog(cost, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=[1.0],
                  bounds=bounds, method="highs")

    if res.status != 0 or res.x is None:
        return {
            "weights": None, "objective": None, "es": None, "t": None,
            "status": int(res.status), "message": res.message,
            "n_scenarios": k, "n_assets": n, "alpha": alpha,
            "binding_cap": None, "turnover": None,
        }

    w = res.x[:n]
    t = res.x[n]
    u = res.x[n + 1:n + 1 + k]
    es = float(t + tail_weight * u.sum())
    turnover = (float(np.abs(w - w_prev).sum() / 2.0) if w_prev is not None else None)
    n_at_cap = int((w >= max_weight - 1e-8).sum())
    n_at_floor = int((w <= min_weight + 1e-8).sum())
    return {
        "weights": w, "objective": float(res.fun), "es": es, "t": float(t),
        "status": int(res.status), "message": res.message,
        "n_scenarios": k, "n_assets": n, "alpha": alpha,
        "n_at_cap": n_at_cap, "n_at_floor": n_at_floor,
        "binding_cap": bool(n_at_cap or n_at_floor),
        "names_held": int((w > 1e-6).sum()),
        "herfindahl": float((w ** 2).sum()),
        "turnover": turnover,
        "max_weight_used": float(w.max()),
        "min_weight_used": float(w.min()),
        "empirical_es_check": empirical_es(w, scenarios, alpha),
    }


def min_variance_weights(cov, min_weight=MIN_ASSET_WEIGHT, max_weight=MAX_ASSET_WEIGHT,
                         w_prev=None, turnover_cap=None, expected_returns=None,
                         return_floor=None):
    
    cov = np.asarray(cov, dtype=float)
    n = cov.shape[0]
    x0 = np.full(n, 1.0 / n)
    bounds = [(min_weight, max_weight)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0,
                    "jac": lambda w: np.ones(n)}]
    if turnover_cap is not None and w_prev is not None:
        constraints.append({
            "type": "ineq",
            "fun": lambda w: turnover_cap - np.abs(w - w_prev).sum() / 2.0,
        })
    if return_floor is not None:
        mu = np.asarray(expected_returns, dtype=float).ravel()
        constraints.append({"type": "ineq", "fun": lambda w: mu @ w - return_floor})

    res = minimize(lambda w: 0.5 * w @ cov @ w, x0, method="SLSQP", bounds=bounds,
                   constraints=constraints, options={"maxiter": 500, "ftol": 1e-14})
    
    
    
    
    
    
    w = np.clip(res.x, min_weight, max_weight)
    deficit = float(w.sum() - 1.0)
    if res.status != 0 or abs(deficit) > 1e-8:
        return {
            "weights": None, "variance": None, "vol": None,
            "status": int(res.status) or 1,
            "message": res.message if res.status != 0
                       else f"budget constraint missed by {deficit:.3e}",
            "names_held": None, "herfindahl": None, "turnover": None,
        }
    return {
        "weights": w, "variance": float(w @ cov @ w), "vol": float(np.sqrt(w @ cov @ w)),
        "status": int(res.status), "message": res.message,
        "names_held": int((w > 1e-6).sum()), "herfindahl": float((w ** 2).sum()),
        "turnover": float(np.abs(w - w_prev).sum() / 2.0) if w_prev is not None else None,
    }


def scenario_covariance(scenarios):
    
    return np.cov(np.asarray(scenarios, dtype=float), rowvar=False, ddof=1)


def shrunk_covariance(scenarios):
    
    return LedoitWolf(store_precision=False).fit(
        np.asarray(scenarios, dtype=float)).covariance_


def equal_weight(n):
    return np.full(n, 1.0 / n)


def concentration_report(weights):
    w = np.asarray(weights, dtype=float).ravel()
    return {"herfindahl": float((w ** 2).sum()), "names_held": int((w > 1e-6).sum()),
            "max_weight": float(w.max()), "effective_names": float(1.0 / (w ** 2).sum())}


def mean_off_diagonal_correlation(matrix):
    corr = np.asarray(pd.DataFrame(matrix).corr().to_numpy(), dtype=float)
    upper = corr[np.triu_indices(corr.shape[0], 1)]
    return float(np.nanmean(upper))


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    n_assets, k = 20, 500
    loadings = np.abs(rng.normal(0.0, 0.012, size=n_assets)) + 0.004
    common = rng.standard_t(4, size=k) * 0.010
    idio = rng.standard_t(4, (k, n_assets)) * loadings
    scenarios = common[:, None] + idio
    ew = equal_weight(n_assets)

    print(f"mean off-diagonal correlation of this synthetic block: "
          f"{mean_off_diagonal_correlation(scenarios):.3f}")
    for alpha in (0.99, 0.975, 0.95):
        out = min_es_lp(scenarios, alpha=alpha)
        print(f"alpha={alpha}: status {out['status']}, ES {out['es'] * 100:.4f}% "
              f"vs EW {empirical_es(ew, scenarios, alpha) * 100:.4f}%, "
              f"names {out['names_held']}, HHI {out['herfindahl']:.3f}, "
              f"objective-vs-check gap {abs(out['es'] - out['empirical_es_check']):.2e}")

    print("\nturnover cap and return floor:")
    w = min_es_lp(scenarios, alpha=0.975)["weights"]
    capped = min_es_lp(scenarios, alpha=0.975, w_prev=ew, turnover_cap=0.10)
    print(f"  capped turnover {capped['turnover']:.4f} (cap 0.10), status {capped['status']}")
    floored = min_es_lp(scenarios, alpha=0.975, expected_returns=scenarios.mean(axis=0),
                        return_floor=0.0002)
    print(f"  floored expected return {scenarios.mean(axis=0) @ floored['weights']:.6f} "
          f"(floor 0.0002), status {floored['status']}")
    print(f"  unconstrained ES {out['es']:.6f}, capped {capped['es']:.6f}, "
          f"floored {floored['es']:.6f}")

    mv = min_variance_weights(scenario_covariance(scenarios))
    mw = min_variance_weights(shrunk_covariance(scenarios))
    print(f"\nmin-variance: sample vol {mv['vol'] * 100:.4f}%, "
          f"Ledoit-Wolf vol {mw['vol'] * 100:.4f}%, names "
          f"{mv['names_held']}/{mw['names_held']}")
