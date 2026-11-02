import numpy as np
import pandas as pd
from scipy.stats import norm, t as t_dist, genpareto, kurtosis, skew, kstest
from arch import arch_model
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.stats.stattools import jarque_bera as _jarque_bera
from config import (
    LB_LAGS,
    ARCH_LM_LAGS,
    PRIMARY_POT_THRESHOLD_QUANTILE,
    validate_pot_configuration,
)




GARCH_DISTRIBUTION_ALIASES = {"normal": "normal", "gaussian": "normal", "t": "t", "student_t": "t"}





XI_ADMISSIBLE_MIN = 0.001
XI_ADMISSIBLE_MAX = 0.8


class InsufficientExceedances(ValueError):
    pass


class InvalidThresholdConfiguration(ValueError):
    pass


def calculate_parametric_var(returns, confidence_level=0.99):
    mean = np.mean(returns)
    std = np.std(returns, ddof=1)
    z_score = norm.ppf(1 - confidence_level)
    var = -(mean + z_score * std)
    return float(var)

def calculate_historical_var(returns, confidence_level=0.99):
    var = -np.percentile(returns, (1 - confidence_level) * 100)
    return float(var)

def fit_garch11(returns, dist="normal", include_nu=False):
    
    dist = GARCH_DISTRIBUTION_ALIASES[dist]
    
    
    am = arch_model(returns * 100.0, mean='Constant', vol='GARCH', p=1, q=1, dist=dist)
    res = am.fit(disp='off', show_warning=False)

    cond_vol = np.asarray(res.conditional_volatility) / 100.0
    mu = float(res.params['mu'] / 100.0)
    residuals = np.asarray(returns, dtype=float).ravel() - mu
    std_resid = residuals / cond_vol
    nu = float(res.params['nu']) if dist == "t" else float("inf")

    if include_nu:
        return res, cond_vol, std_resid, mu, nu
    return res, cond_vol, std_resid, mu

def fit_garch11_state(returns, dist="normal"):
    
    res, cond_vol, std_resid, mu, nu = fit_garch11(returns, dist=dist, include_nu=True)
    return {
        "dist": GARCH_DISTRIBUTION_ALIASES[dist],
        "mu": mu,
        "omega": float(res.params['omega'] / 10000.0),
        "alpha": float(res.params['alpha[1]']),
        "beta": float(res.params['beta[1]']),
        "nu": nu,
        "persistence": float(res.params['alpha[1]'] + res.params['beta[1]']),
        "cond_vol": cond_vol,
        "std_resid": std_resid,
        "loglikelihood": float(res.loglikelihood),
        "aic": float(res.aic),
        "bic": float(res.bic),
        "nobs": int(res.nobs),
        
        "convergence_flag": int(getattr(res, "convergence_flag", 0)),
    }

def fit_evt_pot(std_resid, threshold_quantile=0.90, clamp_xi=True, min_exceedances=10):
    
    loss_innovations = -np.asarray(std_resid, dtype=float)
    u = float(np.percentile(loss_innovations, threshold_quantile * 100.0))

    exceedances = loss_innovations[loss_innovations > u] - u
    n_exceedances = len(exceedances)
    total_n = len(loss_innovations)

    if n_exceedances < min_exceedances:
        if not clamp_xi:
            raise InsufficientExceedances(
                f"threshold quantile {threshold_quantile} leaves {n_exceedances} "
                f"exceedances; at least {min_exceedances} are required to fit a GPD"
            )
        return u, 0.1, 1.0, n_exceedances, total_n, loss_innovations

    shape_xi, loc_val, scale_beta = genpareto.fit(exceedances, floc=0)

    if clamp_xi:
        shape_xi = max(min(shape_xi, XI_ADMISSIBLE_MAX), XI_ADMISSIBLE_MIN)
        scale_beta = max(scale_beta, 1e-4)

    return u, float(shape_xi), float(scale_beta), n_exceedances, total_n, loss_innovations

def _gpd_negative_log_likelihood(params, exceedances):
    xi, beta = float(params[0]), float(params[1])
    if beta <= 0.0:
        return np.inf
    scaled = xi * exceedances / beta
    if np.any(1.0 + scaled <= 0.0):
        return np.inf
    log_terms = np.log1p(scaled)
    if abs(xi) < 1e-12:
        sum_log = float(np.sum(exceedances / beta))          
    else:
        sum_log = float(np.sum(log_terms) * (1.0 / xi + 1.0))
    return len(exceedances) * np.log(beta) + sum_log


def gpd_shape_standard_error(exceedances, xi, beta):
    
    exceedances = np.asarray(exceedances, dtype=float)
    if exceedances.size < 5 or not np.isfinite(xi) or not np.isfinite(beta) or beta <= 0:
        return np.nan, np.nan

    for scale in (1e-4, 1e-5, 1e-6):
        se = _observed_information_se(exceedances, xi, beta, scale)
        if se is not None:
            return se
    
    
    return np.nan, np.nan


def _observed_information_se(exceedances, xi, beta, scale):
    
    base = _gpd_negative_log_likelihood(np.array([xi, beta]), exceedances)
    if not np.isfinite(base):
        return None

    step = (scale * max(abs(xi), 1.0), scale * max(abs(beta), 1.0))
    hessian = np.zeros((2, 2))
    p = np.array([xi, beta], dtype=float)
    for i in range(2):
        for j in range(2):
            e_i, e_j = np.zeros(2), np.zeros(2)
            e_i[i] = step[i]
            e_j[j] = step[j]
            probes = [_gpd_negative_log_likelihood(p + a * e_i + b * e_j, exceedances)
                      for a, b in ((1, 1), (1, -1), (-1, 1), (-1, -1))]
            if not all(np.isfinite(v) for v in probes):
                return None
            hessian[i, j] = (probes[0] - probes[1] - probes[2] + probes[3]) \
                / (4.0 * step[i] * step[j])

    if not np.all(np.isfinite(hessian)):
        return None
    try:
        covariance = np.linalg.inv(hessian)
    except np.linalg.LinAlgError:
        return None
    diag = np.diag(covariance)
    if not np.all(diag > 0):
        return None
    return float(np.sqrt(diag[0])), float(np.sqrt(diag[1]))


def fit_evt_pot_diag(std_resid, threshold_quantile=PRIMARY_POT_THRESHOLD_QUANTILE, min_exceedances=10):
    
    loss_innovations = -np.asarray(std_resid, dtype=float)
    u = float(np.percentile(loss_innovations, threshold_quantile * 100.0))
    exceedances = loss_innovations[loss_innovations > u] - u
    n_exceedances = int(len(exceedances))
    total_n = int(len(loss_innovations))

    record = {
        "threshold_quantile": float(threshold_quantile),
        "u": u,
        "n_u": n_exceedances,
        "n_tot": total_n,
        "xi_raw": None,
        "xi_used": None,
        "beta": None,
        "clamped": False,
        
        
        "clamp_direction": "none",
        "degenerate": n_exceedances < min_exceedances,
        "ks_stat": None,
        "ks_pvalue": None,
        "aic_gpd": None,
        "xi_se": None,
        "beta_se": None,
        "xi_ci95": None,
    }
    if record["degenerate"]:
        return record

    xi_raw, _loc, beta_raw = genpareto.fit(exceedances, floc=0)
    xi_raw, beta_raw = float(xi_raw), float(beta_raw)

    xi_used = min(max(xi_raw, XI_ADMISSIBLE_MIN), XI_ADMISSIBLE_MAX)
    beta_used = max(beta_raw, 1e-4)
    if xi_used != xi_raw:
        record["clamped"] = True
        record["clamp_direction"] = "up" if xi_used > xi_raw else "down"

    record["xi_raw"] = xi_raw
    record["xi_used"] = xi_used
    record["beta"] = beta_used

    xi_se, beta_se = gpd_shape_standard_error(exceedances, xi_raw, beta_raw)
    record["xi_se"] = xi_se
    record["beta_se"] = beta_se
    if np.isfinite(xi_se):
        record["xi_ci95"] = (xi_raw - 1.959963985 * xi_se,
                             xi_raw + 1.959963985 * xi_se)

    ks = kstest(exceedances, genpareto.cdf, args=(xi_used, 0.0, beta_used))
    record["ks_stat"] = float(ks.statistic)
    record["ks_pvalue"] = float(ks.pvalue)

    
    ll = float(np.sum(genpareto.logpdf(exceedances, xi_used, 0.0, beta_used)))
    record["aic_gpd"] = float(2.0 * 2.0 - 2.0 * ll)
    return record

def compute_evt_quantiles(u, xi, beta, n_exceedances, total_n, confidence_level=0.99):
    tail_prob = (1.0 - confidence_level) / (n_exceedances / total_n)

    if tail_prob >= 1.0:
        
        
        
        
        raise InvalidThresholdConfiguration(
            f"tail probability {tail_prob:.4f} >= 1: {n_exceedances} of {total_n} "
            f"exceedances already implies coverage above {confidence_level}"
        )

    if abs(xi) < 1e-5:
        var_z = u - beta * np.log(tail_prob)
        es_z = var_z + beta
    else:
        var_z = u + (beta / xi) * (np.power(tail_prob, -xi) - 1.0)
        es_z = (var_z / (1.0 - xi)) + ((beta - xi * u) / (1.0 - xi))

    return float(var_z), float(es_z)

def mean_excess_curve(std_resid, u_grid=None, n_points=40, threshold_quantiles=None):
    
    losses = -np.asarray(std_resid, dtype=float)
    if u_grid is None:
        lo, hi = np.percentile(losses, [50.0, 98.0])
        u_grid = np.linspace(lo, hi, n_points)

    rows = []
    for u in np.asarray(u_grid, dtype=float):
        exceed = losses[losses > u] - u
        n = int(len(exceed))
        rows.append({
            "u": float(u),
            "mean_excess": float(exceed.mean()) if n > 0 else np.nan,
            
            
            
            
            "se_excess": float(exceed.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan,
            "n_exceedances": n,
        })
    curve = pd.DataFrame(rows)

    if threshold_quantiles is not None:
        curve["implied_quantile"] = [
            float((np.sum(losses <= u) / len(losses)) * 100.0) for u in curve["u"]
        ]
    return curve

def gpd_mean_excess(u, xi, beta):
    
    if xi is None or beta is None:
        return np.nan
    if xi >= 1.0:
        return np.nan
    return float(beta / (1.0 - xi) + (xi * u) / (1.0 - xi))

def gpd_profile_over_thresholds(std_resid, quantiles, confidence_level=0.99,
                                min_exceedances=10):
    
    rows = []
    for q in quantiles:
        validate_pot_configuration(q, confidence_level)
        diag = fit_evt_pot_diag(std_resid, q, min_exceedances=min_exceedances)
        row = dict(diag)
        row["confidence_level"] = float(confidence_level)

        if diag["degenerate"]:
            row.update({
                "var_z": None, "es_z": None,
                "var_z_raw": None, "es_z_raw": None,
                "gpd_mean_excess_at_u": np.nan,
            })
        else:
            var_z, es_z = compute_evt_quantiles(
                diag["u"], diag["xi_used"], diag["beta"],
                diag["n_u"], diag["n_tot"], confidence_level,
            )
            row["var_z"] = var_z
            row["es_z"] = es_z
            
            
            
            
            
            
            if diag["xi_raw"] < 1.0:
                var_z_raw, es_z_raw = compute_evt_quantiles(
                    diag["u"], diag["xi_raw"], diag["beta"],
                    diag["n_u"], diag["n_tot"], confidence_level,
                )
                row["var_z_raw"] = var_z_raw
                row["es_z_raw"] = es_z_raw
            else:
                row["var_z_raw"] = None
                row["es_z_raw"] = None
            row["gpd_mean_excess_at_u"] = gpd_mean_excess(
                diag["u"], diag["xi_used"], diag["beta"]
            )
        rows.append(row)

    columns = [
        "threshold_quantile", "u", "n_u", "n_tot", "confidence_level",
        "xi_raw", "xi_used", "xi_se", "xi_ci95", "beta", "beta_se", "clamped",
        "clamp_direction", "degenerate", "ks_stat", "ks_pvalue", "aic_gpd",
        "var_z", "es_z", "var_z_raw", "es_z_raw", "gpd_mean_excess_at_u",
    ]
    return pd.DataFrame(rows, columns=columns)

def residual_diagnostics(std_resid, garch_result=None, lags=None, nlags=None, nu=None):
    
    lags = LB_LAGS if lags is None else lags
    nlags = ARCH_LM_LAGS if nlags is None else nlags

    
    
    z = pd.Series(np.asarray(std_resid, dtype=float))
    z2 = pd.Series(z.values ** 2)

    def _lb(series):
        out = acorr_ljungbox(series, lags=lags, return_df=True)
        return {int(lag): float(out["lb_pvalue"].iloc[i]) for i, lag in enumerate(lags)}

    lb_z = _lb(z)
    lb_z2 = _lb(z2)

    lm_stat, lm_p, _f_stat, _f_p = het_arch(z.values, nlags=nlags)[:4]

    jb_stat, jb_p, _sk, _ku = _jarque_bera(z.values)

    cross_check = None
    if garch_result is not None and hasattr(garch_result, "arch_lm_test"):
        
        
        
        cc = garch_result.arch_lm_test(lags=nlags, standardized=True)
        cross_check = {"stat": float(cc.stat), "pvalue": float(cc.pval), "standardized": True}

    observed_kurt = float(kurtosis(z.values, fisher=False))
    if nu is None and observed_kurt > 3.0:
        
        
        excess = observed_kurt - 3.0
        nu = float(4.0 + 6.0 / excess) if excess > 0 else float("inf")

    ks_normal = kstest(z.values, norm.cdf)
    ks_t = None
    if nu is not None and np.isfinite(nu):
        scale = float(np.sqrt((nu - 2.0) / nu))   
        ks_t = kstest(z.values, t_dist.cdf, args=(nu, 0.0, scale))

    p_values = np.array(list(lb_z.values()) + list(lb_z2.values()) + [lm_p, jb_p])
    if not np.all(np.isfinite(p_values)):
        raise ValueError("residual diagnostics produced a non-finite p-value")

    return {
        "n_obs": int(len(z)),
        "ljung_box_z_pvalues": lb_z,
        "ljung_box_z2_pvalues": lb_z2,
        "arch_lm": {"stat": float(lm_stat), "pvalue": float(lm_p), "nlags": int(nlags)},
        "arch_lm_cross_check": cross_check,
        "jarque_bera": {"stat": float(jb_stat), "pvalue": float(jb_p)},
        "kurtosis": observed_kurt,
        "skewness": float(skew(z.values)),
        "implied_t_dof": None if nu is None or not np.isfinite(nu) else float(nu),
        "ks_vs_normal": {"stat": float(ks_normal.statistic), "pvalue": float(ks_normal.pvalue)},
        "ks_vs_student_t": None if ks_t is None else {
            "stat": float(ks_t.statistic), "pvalue": float(ks_t.pvalue), "nu": float(nu)
        },
        
        
        "second_order_rejected_at_5pct": bool(min(lb_z2.values()) < 0.05 or lm_p < 0.05),
        "first_order_rejected_at_5pct": bool(min(lb_z.values()) < 0.05),
        "normality_rejected": bool(jb_p < 0.05),
    }

def calculate_garch_evt_risk(returns, confidence_level=0.99, threshold_quantile=0.90, dist="normal"):
    res, cond_vol, std_resid, mu = fit_garch11(returns, dist=dist)
    u, xi, beta, n_u, n_tot, _ = fit_evt_pot(std_resid, threshold_quantile)
    var_z, es_z = compute_evt_quantiles(u, xi, beta, n_u, n_tot, confidence_level)

    latest_vol = cond_vol[-1]
    omega = float(res.params['omega'] / 10000.0)
    alpha = float(res.params['alpha[1]'])
    beta_garch = float(res.params['beta[1]'])
    latest_resid = float(returns.iloc[-1] - mu) if hasattr(returns, 'iloc') else float(returns[-1] - mu)

    sigma_next = np.sqrt(omega + alpha * (latest_resid ** 2) + beta_garch * (latest_vol ** 2))

    var_forecast = -mu + sigma_next * var_z
    es_forecast = -mu + sigma_next * es_z

    return float(var_forecast), float(es_forecast), {
        'mu': mu,
        'sigma_next': float(sigma_next),
        'u': u,
        'xi': xi,
        'beta': beta,
        'var_z': var_z,
        'es_z': es_z
    }
