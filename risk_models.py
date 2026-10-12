import numpy as np
from scipy.stats import norm, genpareto
from arch import arch_model

def calculate_parametric_var(returns, confidence_level=0.99):
    mean = np.mean(returns)
    std = np.std(returns, ddof=1)
    z_score = norm.ppf(1 - confidence_level)
    var = -(mean + z_score * std)
    return float(var)

def calculate_historical_var(returns, confidence_level=0.99):
    var = -np.percentile(returns, (1 - confidence_level) * 100)
    return float(var)

def fit_garch11(returns):
    scaled_returns = returns * 100.0
    am = arch_model(scaled_returns, mean='Constant', vol='GARCH', p=1, q=1, dist='normal')
    res = am.fit(disp='off', show_warning=False)
    
    cond_vol = np.asarray(res.conditional_volatility) / 100.0
    mu = float(res.params['mu'] / 100.0)
    residuals = returns - mu
    std_resid = residuals / cond_vol
    
    return res, cond_vol, std_resid, mu

def fit_evt_pot(std_resid, threshold_quantile=0.90):
    loss_innovations = -np.asarray(std_resid)
    u = float(np.percentile(loss_innovations, threshold_quantile * 100.0))
    
    exceedances = loss_innovations[loss_innovations > u] - u
    n_exceedances = len(exceedances)
    total_n = len(loss_innovations)
    
    if n_exceedances < 10:
        return u, 0.1, 1.0, n_exceedances, total_n, loss_innovations
        
    shape_xi, loc_val, scale_beta = genpareto.fit(exceedances, floc=0)
    
    shape_xi = max(min(shape_xi, 0.8), 0.001)
    scale_beta = max(scale_beta, 1e-4)
    
    return u, float(shape_xi), float(scale_beta), n_exceedances, total_n, loss_innovations

def compute_evt_quantiles(u, xi, beta, n_exceedances, total_n, confidence_level=0.99):
    tail_prob = (1.0 - confidence_level) / (n_exceedances / total_n)
    
    if abs(xi) < 1e-5:
        var_z = u - beta * np.log(tail_prob)
        es_z = var_z + beta
    else:
        var_z = u + (beta / xi) * (np.power(tail_prob, -xi) - 1.0)
        es_z = (var_z / (1.0 - xi)) + ((beta - xi * u) / (1.0 - xi))
        
    return float(var_z), float(es_z)

def calculate_garch_evt_risk(returns, confidence_level=0.99, threshold_quantile=0.90):
    res, cond_vol, std_resid, mu = fit_garch11(returns)
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
