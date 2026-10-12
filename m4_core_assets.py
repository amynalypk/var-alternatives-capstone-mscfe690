import os
import sys
import json
import numpy as np
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from config import (
    TICKERS, BENCHMARK_TICKER, VOLATILITY_TICKER,
    START_DATE, END_DATE, PRIMARY_CONFIDENCE,
    ROLLING_WINDOW, DATA_DIR, FIGURES_DIR
)
from data_acquisition import fetch_and_cache_data, process_returns, compute_summary_statistics
from risk_models import fit_garch11, fit_evt_pot, compute_evt_quantiles, calculate_garch_evt_risk
from backtester import (
    run_walk_forward_backtest, evaluate_risk_model_performance,
    segment_performance_by_regimes, run_dirichlet_robustness_test
)
from visualizations import (
    plot_cumulative_performance_and_drawdowns,
    plot_tail_diagnostics_and_gpd,
    plot_walk_forward_backtest_with_crises,
    plot_regime_failure_rates,
    plot_dirichlet_robustness
)

def run_module4_pipeline():
    print("=" * 80)
    print("  MSCFE 690 CAPSTONE PROJECT - MODULE 4: CORE ASSETS PIPELINE")
    print("  Topic 3: Developing Alternatives to Value-at-Risk (VaR)")
    print("  Group 17845: Amin Ali & Mercy Madu Onyinyechi")
    print("=" * 80)
    
    print("\n[Step 1/6] Ingesting and processing market data (2005-2024)...")
    prices_df = fetch_and_cache_data()
    returns_df = process_returns(prices_df)
    
    port_returns = returns_df['Portfolio']
    spy_returns = returns_df['SPY']
    vix_series = returns_df['VIX'] if 'VIX' in returns_df else None
    
    summary_stats = compute_summary_statistics(port_returns)
    spy_stats = compute_summary_statistics(spy_returns)
    
    print("\n--- Portfolio Summary Statistics (20-Stock Equal-Weighted) ---")
    for k, v in summary_stats.items():
        val_str = f"{v:.4f}" if isinstance(v, float) else str(v)
        print(f"  {k:25s}: {val_str}")
        
    print("\n--- S&P 500 (SPY Benchmark) Summary Statistics ---")
    for k, v in spy_stats.items():
        val_str = f"{v:.4f}" if isinstance(v, float) else str(v)
        print(f"  {k:25s}: {val_str}")
        
    print("\n[Step 2/6] Fitting full-sample GARCH(1,1) volatility and EVT-POT...")
    garch_res, cond_vol, std_resid, mu = fit_garch11(port_returns)
    u, xi, beta, n_u, n_tot, loss_innov = fit_evt_pot(std_resid, threshold_quantile=0.90)
    var_z_99, es_z_99 = compute_evt_quantiles(u, xi, beta, n_u, n_tot, confidence_level=0.99)
    var_z_975, es_z_975 = compute_evt_quantiles(u, xi, beta, n_u, n_tot, confidence_level=0.975)
    
    print(f"  GARCH Parameters: mu={mu:.6f}, omega={garch_res.params['omega']/10000:.6e}, "
          f"alpha={garch_res.params['alpha[1]']:.4f}, beta={garch_res.params['beta[1]']:.4f}")
    print(f"  GARCH Persistence (alpha + beta): {garch_res.params['alpha[1]'] + garch_res.params['beta[1]']:.4f}")
    print(f"  EVT-POT (90th percentile threshold u): {u:.4f}")
    print(f"  EVT Tail Index (Shape xi): {xi:.4f}, Scale (beta): {beta:.4f} (Exceedances: {n_u}/{n_tot})")
    print(f"  Standardized 99% VaR(Z): {var_z_99:.4f}, Standardized 99% ES(Z): {es_z_99:.4f}")
    print(f"  Standardized 97.5% VaR(Z): {var_z_975:.4f}, Standardized 97.5% ES(Z): {es_z_975:.4f}")
    
    print("\n[Step 3/6] Executing rolling walk-forward backtest (500-day window)...")
    backtest_cache = os.path.join(DATA_DIR, "backtest_results_500w.csv")
    if os.path.exists(backtest_cache):
        print(f"  Loading cached walk-forward backtest results from: {backtest_cache}")
        backtest_df = pd.read_csv(backtest_cache, index_col=0, parse_dates=True)
    else:
        backtest_df = run_walk_forward_backtest(port_returns, vix_series, confidence_level=PRIMARY_CONFIDENCE, window=ROLLING_WINDOW)
        backtest_df.to_csv(backtest_cache)
        print(f"  Backtest results saved to: {backtest_cache}")
        
    print("\n[Step 4/6] Evaluating Kupiec POF, Christoffersen independence, and regime stress...")
    perf_summary = evaluate_risk_model_performance(backtest_df, confidence_level=PRIMARY_CONFIDENCE)
    regime_summary = segment_performance_by_regimes(backtest_df, confidence_level=PRIMARY_CONFIDENCE)
    
    print("\n--- Out-of-Sample Backtesting Performance Summary (99% Confidence Level) ---")
    print(f"{'Model':20s} | {'Obs':5s} | {'Exp':5s} | {'Breaches':8s} | {'Rate (%)':8s} | {'Kupiec p':8s} | {'Christoffersen p':16s} | {'Mean Excess (%)':15s}")
    print("-" * 105)
    for m in ['VaR_Normal', 'VaR_Historical', 'VaR_GARCH_EVT']:
        st = perf_summary[m]
        print(f"{m:20s} | {st['Total Obs']:5d} | {st['Expected Breaches']:5.1f} | {st['Actual Breaches']:8d} | "
              f"{st['Breach Rate (%)']:8.2f}% | {st['Kupiec p-val']:8.4f} | {st['Conditional Cov p-val']:16.4f} | "
              f"{st['Mean Excess Loss (%)']:15.2f}%")
              
    es_st = perf_summary['ES_GARCH_EVT']
    print(f"{'ES_GARCH_EVT':20s} | {es_st['Total Obs']:5d} | {'--':5s} | {es_st['Actual Breaches']:8d} | "
          f"{es_st['Breach Rate (%)']:8.2f}% | {'--':8s} | {'--':16s} | {es_st['Mean Excess Beyond ES (%)']:15.2f}%")
          
    print("\n--- Volatility Regime Breakdown ---")
    for r_name, r_st in regime_summary.items():
        print(f"Regime: {r_name} (N = {r_st['Observations']})")
        print(f"  Parametric VaR Breaches: {r_st['VaR_Normal_Breaches']} ({r_st['VaR_Normal_Rate (%)']:.2f}%), Mean Excess: {r_st['VaR_Normal_MeanExcess (%)']:.2f}%")
        print(f"  Historical VaR Breaches: {r_st['VaR_Historical_Breaches']} ({r_st['VaR_Historical_Rate (%)']:.2f}%), Mean Excess: {r_st['VaR_Historical_MeanExcess (%)']:.2f}%")
        print(f"  GARCH-EVT VaR Breaches : {r_st['VaR_GARCH_EVT_Breaches']} ({r_st['VaR_GARCH_EVT_Rate (%)']:.2f}%), Mean Excess: {r_st['VaR_GARCH_EVT_MeanExcess (%)']:.2f}%")
        print(f"  GARCH-EVT ES Breaches  : {r_st['ES_GARCH_EVT_Breaches']} ({r_st['ES_GARCH_EVT_Rate (%)']:.2f}%)")
        
    print("\n[Step 5/6] Executing Dirichlet 100-portfolio robustness evaluation...")
    dirichlet_res = run_dirichlet_robustness_test(returns_df, TICKERS, n_simulations=100, confidence_level=PRIMARY_CONFIDENCE)
    
    dir_norm = np.array(dirichlet_res["VaR_Normal_Rates"])
    dir_hist = np.array(dirichlet_res["VaR_Historical_Rates"])
    dir_evt = np.array(dirichlet_res["VaR_GARCH_EVT_Rates"])
    
    print("\n--- Dirichlet 100-Portfolio Breach Rate Distribution (%) ---")
    print(f"  Parametric VaR  : Mean = {dir_norm.mean():.2f}%, Std = {dir_norm.std():.2f}%, 5th-95th = [{np.percentile(dir_norm, 5):.2f}%, {np.percentile(dir_norm, 95):.2f}%]")
    print(f"  Historical VaR  : Mean = {dir_hist.mean():.2f}%, Std = {dir_hist.std():.2f}%, 5th-95th = [{np.percentile(dir_hist, 5):.2f}%, {np.percentile(dir_hist, 95):.2f}%]")
    print(f"  GARCH-EVT VaR   : Mean = {dir_evt.mean():.2f}%, Std = {dir_evt.std():.2f}%, 5th-95th = [{np.percentile(dir_evt, 5):.2f}%, {np.percentile(dir_evt, 95):.2f}%]")
    
    print("\n[Step 6/6] Generating publication-quality figures (300 DPI)...")
    fig1_path = plot_cumulative_performance_and_drawdowns(returns_df)
    fig2_path = plot_tail_diagnostics_and_gpd(port_returns, std_resid)
    fig3_path = plot_walk_forward_backtest_with_crises(backtest_df)
    fig4_path = plot_regime_failure_rates(regime_summary)
    fig5_path = plot_dirichlet_robustness(dirichlet_res)
    
    metrics_manifest = {
        "summary_stats": summary_stats,
        "spy_stats": spy_stats,
        "garch_params": {
            "mu": mu,
            "omega": float(garch_res.params['omega'] / 10000.0),
            "alpha": float(garch_res.params['alpha[1]']),
            "beta": float(garch_res.params['beta[1]']),
            "persistence": float(garch_res.params['alpha[1]'] + garch_res.params['beta[1]'])
        },
        "evt_params": {
            "u": u,
            "xi": xi,
            "beta": beta,
            "n_u": int(n_u),
            "n_tot": int(n_tot),
            "var_z_99": var_z_99,
            "es_z_99": es_z_99,
            "var_z_975": var_z_975,
            "es_z_975": es_z_975
        },
        "perf_summary": perf_summary,
        "regime_summary": regime_summary,
        "dirichlet_stats": {
            "norm_mean": float(dir_norm.mean()), "norm_std": float(dir_norm.std()),
            "hist_mean": float(dir_hist.mean()), "hist_std": float(dir_hist.std()),
            "evt_mean": float(dir_evt.mean()), "evt_std": float(dir_evt.std())
        }
    }
    
    manifest_file = os.path.join(DATA_DIR, "module4_metrics_manifest.json")
    with open(manifest_file, "w") as f:
        json.dump(metrics_manifest, f, indent=4)
        
    print(f"\n[Done] Pipeline executed successfully! Metrics manifest saved to: {manifest_file}")
    return metrics_manifest

if __name__ == "__main__":
    run_module4_pipeline()
