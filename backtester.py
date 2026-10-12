import numpy as np
import pandas as pd
from scipy.stats import chi2
from arch import arch_model
from config import (
    ROLLING_WINDOW, GARCH_REFIT_INTERVAL, POT_THRESHOLD_QUANTILE,
    VIX_CALM_THRESHOLD, VIX_CRISIS_THRESHOLD, DIRICHLET_SIMULATIONS, RANDOM_SEED
)
from risk_models import (
    calculate_parametric_var, calculate_historical_var,
    fit_evt_pot, compute_evt_quantiles
)

def kupiec_pof_test(exceptions, total_obs, confidence_level=0.99):
    p = 1.0 - confidence_level
    x = exceptions
    n = total_obs
    
    if x == 0:
        lr_uc = -2.0 * np.log((1.0 - p) ** n)
        p_value = 1.0 - chi2.cdf(lr_uc, df=1)
        return float(lr_uc), float(p_value)
        
    p_hat = x / n
    if p_hat == 1.0:
        p_hat = 0.999
        
    term_null = ((1.0 - p) ** (n - x)) * (p ** x)
    term_alt = ((1.0 - p_hat) ** (n - x)) * (p_hat ** x)
    
    term_null = max(term_null, 1e-300)
    term_alt = max(term_alt, 1e-300)
    
    lr_uc = -2.0 * np.log(term_null / term_alt)
    p_value = 1.0 - chi2.cdf(lr_uc, df=1)
    
    return float(lr_uc), float(p_value)

def christoffersen_test(exceptions_series, confidence_level=0.99):
    e = np.asarray(exceptions_series, dtype=int)
    n = len(e)
    x = int(np.sum(e))
    
    t00 = np.sum((e[:-1] == 0) & (e[1:] == 0))
    t01 = np.sum((e[:-1] == 0) & (e[1:] == 1))
    t10 = np.sum((e[:-1] == 1) & (e[1:] == 0))
    t11 = np.sum((e[:-1] == 1) & (e[1:] == 1))
    
    pi01 = t01 / (t00 + t01) if (t00 + t01) > 0 else 0.0
    pi11 = t11 / (t10 + t11) if (t10 + t11) > 0 else 0.0
    pi = (t01 + t11) / (t00 + t01 + t10 + t11) if (t00 + t01 + t10 + t11) > 0 else 0.0
    
    num = ((1.0 - pi) ** (t00 + t10)) * (pi ** (t01 + t11)) if pi > 0 and pi < 1 else 1e-300
    denom = (((1.0 - pi01) ** t00) * (pi01 ** t01) if pi01 > 0 and pi01 < 1 else 1.0) * \
            (((1.0 - pi11) ** t10) * (pi11 ** t11) if pi11 > 0 and pi11 < 1 else 1.0)
            
    num = max(num, 1e-300)
    denom = max(denom, 1e-300)
    
    lr_ind = -2.0 * np.log(num / denom)
    lr_ind = max(lr_ind, 0.0)
    p_val_ind = 1.0 - chi2.cdf(lr_ind, df=1)
    
    lr_uc, p_val_uc = kupiec_pof_test(x, n, confidence_level)
    
    lr_cc = lr_uc + lr_ind
    p_val_cc = 1.0 - chi2.cdf(lr_cc, df=2)
    
    return {
        "LR_uc": lr_uc, "p_val_uc": p_val_uc,
        "LR_ind": lr_ind, "p_val_ind": p_val_ind,
        "LR_cc": lr_cc, "p_val_cc": p_val_cc,
        "Transitions": (int(t00), int(t01), int(t10), int(t11))
    }

def run_walk_forward_backtest(portfolio_returns, vix_series=None, confidence_level=0.99, window=ROLLING_WINDOW):
    n_total = len(portfolio_returns)
    n_test = n_total - window
    
    print(f"[Backtester] Starting walk-forward evaluation: {n_test} out-of-sample days (Window={window})...")
    
    test_dates = portfolio_returns.index[window:]
    realized_returns = portfolio_returns.iloc[window:].values
    losses = -realized_returns
    
    var_norm = np.zeros(n_test)
    var_hist = np.zeros(n_test)
    var_evt = np.zeros(n_test)
    es_evt = np.zeros(n_test)
    
    cached_garch_res = None
    cached_garch_day = -999
    
    for i in range(n_test):
        idx = window + i
        train_slice = portfolio_returns.iloc[idx - window : idx].values
        
        var_norm[i] = calculate_parametric_var(train_slice, confidence_level)
        
        var_hist[i] = calculate_historical_var(train_slice, confidence_level)
        
        if (i - cached_garch_day >= GARCH_REFIT_INTERVAL) or (cached_garch_res is None):
            scaled_train = train_slice * 100.0
            am = arch_model(scaled_train, mean='Constant', vol='GARCH', p=1, q=1, dist='normal')
            cached_garch_res = am.fit(disp='off', show_warning=False)
            cached_garch_day = i
            
            c_vol = np.asarray(cached_garch_res.conditional_volatility) / 100.0
            c_mu = float(cached_garch_res.params['mu'] / 100.0)
            c_resids = train_slice - c_mu
            c_z = c_resids / c_vol
            
            u_t, xi_t, beta_t, n_u, n_tot, _ = fit_evt_pot(c_z, POT_THRESHOLD_QUANTILE)
            var_z_t, es_z_t = compute_evt_quantiles(u_t, xi_t, beta_t, n_u, n_tot, confidence_level)
            
            c_omega = float(cached_garch_res.params['omega'] / 10000.0)
            c_alpha = float(cached_garch_res.params['alpha[1]'])
            c_beta = float(cached_garch_res.params['beta[1]'])
            
            state_mu = c_mu
            state_var_z = var_z_t
            state_es_z = es_z_t
            state_omega = c_omega
            state_alpha = c_alpha
            state_beta = c_beta
            last_vol = c_vol[-1]
        else:
            prev_return = train_slice[-1]
            prev_resid = prev_return - state_mu
            last_vol = np.sqrt(state_omega + state_alpha * (prev_resid ** 2) + state_beta * (last_vol ** 2))
            
        latest_resid = train_slice[-1] - state_mu
        sigma_next = np.sqrt(state_omega + state_alpha * (latest_resid ** 2) + state_beta * (last_vol ** 2))
        
        var_evt[i] = -state_mu + sigma_next * state_var_z
        es_evt[i] = -state_mu + sigma_next * state_es_z
        
        if (i + 1) % 1000 == 0 or (i + 1) == n_test:
            print(f"[Backtester] Processed {i + 1}/{n_test} out-of-sample days...")
            
    results_df = pd.DataFrame({
        'Date': test_dates,
        'Return': realized_returns,
        'Loss': losses,
        'VaR_Normal': var_norm,
        'VaR_Historical': var_hist,
        'VaR_GARCH_EVT': var_evt,
        'ES_GARCH_EVT': es_evt
    }).set_index('Date')
    
    if vix_series is not None:
        results_df['VIX'] = vix_series.loc[results_df.index]
        
    return results_df

def evaluate_risk_model_performance(results_df, confidence_level=0.99):
    n_obs = len(results_df)
    models = ['VaR_Normal', 'VaR_Historical', 'VaR_GARCH_EVT']
    perf_summary = {}
    
    expected_failures = n_obs * (1.0 - confidence_level)
    
    for m in models:
        breaches = results_df['Loss'] > results_df[m]
        x = int(breaches.sum())
        fail_rate = x / n_obs
        
        excess_losses = results_df.loc[breaches, 'Loss'] - results_df.loc[breaches, m]
        mean_excess = float(excess_losses.mean()) if x > 0 else 0.0
        max_excess = float(excess_losses.max()) if x > 0 else 0.0
        
        chr_res = christoffersen_test(breaches, confidence_level)
        
        perf_summary[m] = {
            "Total Obs": n_obs,
            "Expected Breaches": expected_failures,
            "Actual Breaches": x,
            "Breach Rate (%)": fail_rate * 100.0,
            "Kupiec LR_uc": chr_res['LR_uc'],
            "Kupiec p-val": chr_res['p_val_uc'],
            "Christoffersen LR_ind": chr_res['LR_ind'],
            "Independence p-val": chr_res['p_val_ind'],
            "Conditional Cov LR_cc": chr_res['LR_cc'],
            "Conditional Cov p-val": chr_res['p_val_cc'],
            "Mean Excess Loss (%)": mean_excess * 100.0,
            "Max Excess Loss (%)": max_excess * 100.0,
            "Transitions (00,01,10,11)": chr_res['Transitions']
        }
        
    es_breaches = results_df['Loss'] > results_df['ES_GARCH_EVT']
    x_es = int(es_breaches.sum())
    es_excess = results_df.loc[es_breaches, 'Loss'] - results_df.loc[es_breaches, 'ES_GARCH_EVT']
    
    var_breach_idx = results_df['Loss'] > results_df['VaR_GARCH_EVT']
    actual_breach_losses = results_df.loc[var_breach_idx, 'Loss']
    predicted_es = results_df.loc[var_breach_idx, 'ES_GARCH_EVT']
    es_diff = (actual_breach_losses - predicted_es).mean() if len(actual_breach_losses) > 0 else 0.0
    
    perf_summary['ES_GARCH_EVT'] = {
        "Total Obs": n_obs,
        "Actual Breaches": x_es,
        "Breach Rate (%)": (x_es / n_obs) * 100.0,
        "Mean Excess Beyond ES (%)": float(es_excess.mean() * 100.0) if x_es > 0 else 0.0,
        "ES Calibration Discrepancy (%)": float(es_diff * 100.0)
    }
    
    return perf_summary

def segment_performance_by_regimes(results_df, confidence_level=0.99):
    if 'VIX' not in results_df:
        return {}
        
    regimes = {
        "Calm (VIX < 20)": results_df[results_df['VIX'] < VIX_CALM_THRESHOLD],
        "Normal (20 <= VIX < 30)": results_df[(results_df['VIX'] >= VIX_CALM_THRESHOLD) & (results_df['VIX'] < VIX_CRISIS_THRESHOLD)],
        "Crisis (VIX >= 30)": results_df[results_df['VIX'] >= VIX_CRISIS_THRESHOLD],
        "2008 GFC Shock": results_df.loc['2008-09-01':'2009-06-30'],
        "2020 COVID Crash": results_df.loc['2020-02-15':'2020-04-30']
    }
    
    regime_summary = {}
    for r_name, r_df in regimes.items():
        if len(r_df) == 0:
            continue
        n_sub = len(r_df)
        sub_stats = {"Observations": n_sub}
        for m in ['VaR_Normal', 'VaR_Historical', 'VaR_GARCH_EVT']:
            b_cnt = int((r_df['Loss'] > r_df[m]).sum())
            b_rate = (b_cnt / n_sub) * 100.0
            excess = r_df.loc[r_df['Loss'] > r_df[m], 'Loss'] - r_df.loc[r_df['Loss'] > r_df[m], m]
            mean_exc = float(excess.mean() * 100.0) if b_cnt > 0 else 0.0
            
            sub_stats[f"{m}_Breaches"] = b_cnt
            sub_stats[f"{m}_Rate (%)"] = b_rate
            sub_stats[f"{m}_MeanExcess (%)"] = mean_exc
            
        es_cnt = int((r_df['Loss'] > r_df['ES_GARCH_EVT']).sum())
        sub_stats["ES_GARCH_EVT_Breaches"] = es_cnt
        sub_stats["ES_GARCH_EVT_Rate (%)"] = (es_cnt / n_sub) * 100.0
        
        regime_summary[r_name] = sub_stats
        
    return regime_summary

def run_dirichlet_robustness_test(returns_df, tickers, n_simulations=DIRICHLET_SIMULATIONS, confidence_level=0.99):
    print(f"[Robustness] Running {n_simulations} Dirichlet randomized portfolio simulations...")
    np.random.seed(RANDOM_SEED)
    k = len(tickers)
    
    rates_norm = []
    rates_hist = []
    rates_evt = []
    rates_es = []
    
    for s in range(n_simulations):
        w = np.random.dirichlet(np.ones(k))
        port_ret = returns_df[tickers].dot(w)
        loss = -port_ret
        
        v_norm = calculate_parametric_var(port_ret, confidence_level)
        v_hist = calculate_historical_var(port_ret, confidence_level)
        
        scaled = port_ret * 100.0
        am = arch_model(scaled, mean='Constant', vol='GARCH', p=1, q=1, dist='normal')
        res = am.fit(disp='off', show_warning=False)
        c_vol = np.asarray(res.conditional_volatility) / 100.0
        mu = float(res.params['mu'] / 100.0)
        c_z = (port_ret.values - mu) / c_vol
        
        u, xi, beta, n_u, n_tot, _ = fit_evt_pot(c_z, POT_THRESHOLD_QUANTILE)
        var_z, es_z = compute_evt_quantiles(u, xi, beta, n_u, n_tot, confidence_level)
        
        dynamic_var_evt = -mu + c_vol * var_z
        dynamic_es_evt = -mu + c_vol * es_z
        
        rate_n = (loss > v_norm).mean() * 100.0
        rate_h = (loss > v_hist).mean() * 100.0
        rate_e = (loss.values > dynamic_var_evt).mean() * 100.0
        rate_es = (loss.values > dynamic_es_evt).mean() * 100.0
        
        rates_norm.append(rate_n)
        rates_hist.append(rate_h)
        rates_evt.append(rate_e)
        rates_es.append(rate_es)
        
    return {
        "VaR_Normal_Rates": rates_norm,
        "VaR_Historical_Rates": rates_hist,
        "VaR_GARCH_EVT_Rates": rates_evt,
        "ES_GARCH_EVT_Rates": rates_es
    }
