import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.stats import norm, t, probplot, genpareto
from config import FIGURES_DIR, VIX_CRISIS_THRESHOLD

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9.5
plt.rcParams['figure.titlesize'] = 13
plt.rcParams['lines.linewidth'] = 1.3
plt.rcParams['grid.alpha'] = 0.35
plt.rcParams['grid.linestyle'] = '--'

def plot_cumulative_performance_and_drawdowns(returns_df, save_name="fig1_portfolio_vs_market_drawdowns.png"):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True, gridspec_kw={'height_ratios': [2, 1.2]})
    
    port_cum = (1.0 + returns_df['Portfolio']).cumprod() * 100.0
    spy_cum = (1.0 + returns_df['SPY']).cumprod() * 100.0
    
    port_dd = (port_cum / port_cum.cummax() - 1.0) * 100.0
    spy_dd = (spy_cum / spy_cum.cummax() - 1.0) * 100.0
    
    ax1.plot(port_cum.index, port_cum, label='20-Stock Equal-Weighted Portfolio', color='#1f77b4', lw=1.6)
    ax1.plot(spy_cum.index, spy_cum, label='S&P 500 Benchmark (SPY)', color='#ff7f0e', lw=1.4, linestyle='--')
    ax1.set_ylabel('Growth of $100 ($)')
    ax1.set_title('Figure 1: Cumulative Portfolio Wealth and Historical Drawdowns (2005–2024)', fontweight='bold', pad=10)
    ax1.grid(True)
    ax1.legend(loc='upper left', framealpha=0.9)
    
    if 'VIX' in returns_df:
        crisis_mask = returns_df['VIX'] >= VIX_CRISIS_THRESHOLD
        ax1.fill_between(returns_df.index, 0, port_cum.max() * 1.08, where=crisis_mask,
                         color='red', alpha=0.12, label='Crisis Regime (VIX ≥ 30)')
        ax2.fill_between(returns_df.index, -65, 0, where=crisis_mask,
                         color='red', alpha=0.12)
        ax1.legend(loc='upper left', framealpha=0.9)
        
    ax2.plot(port_dd.index, port_dd, label='20-Stock Portfolio Drawdown', color='#1f77b4', lw=1.2)
    ax2.plot(spy_dd.index, spy_dd, label='SPY Drawdown', color='#ff7f0e', lw=1.0, linestyle=':')
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xlabel('Calendar Year')
    ax2.set_ylim(-62, 3)
    ax2.grid(True)
    ax2.legend(loc='lower left', framealpha=0.9)
    
    ax2.xaxis.set_major_locator(mdates.YearLocator(2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    fig.autofmt_xdate()
    plt.tight_layout()
    
    save_path = os.path.join(FIGURES_DIR, save_name)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[Viz] Saved Figure 1 to: {save_path}")
    return save_path

def plot_tail_diagnostics_and_gpd(portfolio_returns, std_resid, save_name="fig2_fat_tailed_diagnostics_gpd_fit.png"):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    
    ax = axes[0]
    r_pct = portfolio_returns.values * 100.0
    x_grid = np.linspace(np.percentile(r_pct, 0.2), np.percentile(r_pct, 99.8), 500)
    
    ax.hist(r_pct, bins=120, density=True, alpha=0.5, color='#4a7c59', edgecolor='none', label='Empirical Density')
    
    mu_norm, std_norm = norm.fit(r_pct)
    ax.plot(x_grid, norm.pdf(x_grid, mu_norm, std_norm), 'r--', lw=1.5, label=f'Gaussian N({mu_norm:.2f}, {std_norm:.2f})')
    
    df_t, loc_t, scale_t = t.fit(r_pct)
    ax.plot(x_grid, t.pdf(x_grid, df_t, loc_t, scale_t), 'b-', lw=1.5, label=f'Student-t (df={df_t:.1f})')
    
    ax.set_title('(A) Daily Return Density vs Models', fontweight='bold')
    ax.set_xlabel('Daily Return (%)')
    ax.set_ylabel('Probability Density')
    ax.set_xlim(-6, 6)
    ax.grid(True)
    ax.legend(loc='upper right', fontsize=8.5)
    
    ax = axes[1]
    probplot(r_pct, dist="norm", plot=ax)
    ax.get_lines()[0].set_color('#1f77b4')
    ax.get_lines()[0].set_markersize(2.5)
    ax.get_lines()[0].set_alpha(0.6)
    ax.get_lines()[1].set_color('red')
    ax.get_lines()[1].set_linewidth(1.5)
    ax.set_title('(B) Normal Q-Q Plot (Fat Tail Curvature)', fontweight='bold')
    ax.set_xlabel('Theoretical Normal Quantiles')
    ax.set_ylabel('Ordered Empirical Quantiles (%)')
    ax.grid(True)
    
    ax = axes[2]
    losses = -np.asarray(std_resid)
    u = np.percentile(losses, 90.0)
    exceedances = losses[losses > u] - u
    
    c_xi, loc_gpd, scale_beta = genpareto.fit(exceedances, floc=0)
    y_vals = np.sort(exceedances)
    empirical_tail = 1.0 - np.arange(1, len(y_vals) + 1) / len(y_vals)
    gpd_tail = genpareto.sf(y_vals, c_xi, loc=0, scale=scale_beta)
    
    ax.semilogy(y_vals, empirical_tail, 'o', color='#1f77b4', markersize=3, alpha=0.7, label='Empirical Tail Exceedances')
    ax.semilogy(y_vals, gpd_tail, 'r-', lw=1.8, label=f'GPD Fit (ξ={c_xi:.2f}, β={scale_beta:.2f})')
    
    ax.set_title('(C) EVT-POT GPD Tail Exceedance Fit', fontweight='bold')
    ax.set_xlabel('Excess Standardized Loss (y - u)')
    ax.set_ylabel('Exceedance Probability P(Y > y | Y > u)')
    ax.grid(True, which='both')
    ax.legend(loc='upper right', fontsize=8.5)
    
    plt.tight_layout()
    save_path = os.path.join(FIGURES_DIR, save_name)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[Viz] Saved Figure 2 to: {save_path}")
    return save_path

def plot_walk_forward_backtest_with_crises(results_df, save_name="fig3_rolling_var_es_backtest_crises.png"):
    fig = plt.figure(figsize=(15, 9))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.3, 1.0])
    
    ax_main = fig.add_subplot(gs[0, :])
    ax_gfc = fig.add_subplot(gs[1, 0])
    ax_covid = fig.add_subplot(gs[1, 1])
    
    loss_pct = results_df['Loss'] * 100.0
    var_n_pct = results_df['VaR_Normal'] * 100.0
    var_h_pct = results_df['VaR_Historical'] * 100.0
    var_e_pct = results_df['VaR_GARCH_EVT'] * 100.0
    es_e_pct = results_df['ES_GARCH_EVT'] * 100.0
    
    ax_main.scatter(results_df.index, loss_pct, color='#555555', alpha=0.35, s=6, label='Realized Daily Loss (%)')
    ax_main.plot(results_df.index, var_n_pct, label='99% Parametric VaR (Gaussian)', color='red', lw=1.1, alpha=0.85)
    ax_main.plot(results_df.index, var_h_pct, label='99% Historical Simulation VaR', color='orange', lw=1.1, alpha=0.85)
    ax_main.plot(results_df.index, var_e_pct, label='99% Dynamic GARCH-EVT VaR', color='blue', lw=1.3)
    ax_main.plot(results_df.index, es_e_pct, label='99% Dynamic GARCH-EVT ES (CVaR)', color='purple', lw=1.4, linestyle='--')
    
    ax_main.set_ylabel('Loss / Risk Measure (%)')
    ax_main.set_title('Figure 3: Out-of-Sample 99% Walk-Forward Risk Forecasts vs Realized Losses (2007–2024)', fontweight='bold')
    ax_main.set_ylim(-3, 16)
    ax_main.grid(True)
    ax_main.legend(loc='upper right', ncol=3, framealpha=0.9, fontsize=9)
    ax_main.xaxis.set_major_locator(mdates.YearLocator(2))
    ax_main.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    
    gfc_df = results_df.loc['2008-09-01':'2009-03-31']
    if len(gfc_df) > 0:
        ax_gfc.scatter(gfc_df.index, gfc_df['Loss'] * 100, color='#333333', s=16, label='Losses')
        ax_gfc.plot(gfc_df.index, gfc_df['VaR_Normal'] * 100, color='red', lw=1.4, label='Parametric VaR')
        ax_gfc.plot(gfc_df.index, gfc_df['VaR_Historical'] * 100, color='orange', lw=1.4, label='Historical VaR')
        ax_gfc.plot(gfc_df.index, gfc_df['VaR_GARCH_EVT'] * 100, color='blue', lw=1.5, label='GARCH-EVT VaR')
        ax_gfc.plot(gfc_df.index, gfc_df['ES_GARCH_EVT'] * 100, color='purple', lw=1.6, linestyle='--', label='GARCH-EVT ES')
        ax_gfc.set_title('(B) 2008 Global Financial Crisis Shock', fontweight='bold', fontsize=10.5)
        ax_gfc.set_ylabel('Loss / Risk Measure (%)')
        ax_gfc.grid(True)
        ax_gfc.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
        ax_gfc.legend(loc='upper right', fontsize=8)
        
    covid_df = results_df.loc['2020-02-15':'2020-05-31']
    if len(covid_df) > 0:
        ax_covid.scatter(covid_df.index, covid_df['Loss'] * 100, color='#333333', s=16, label='Losses')
        ax_covid.plot(covid_df.index, covid_df['VaR_Normal'] * 100, color='red', lw=1.4, label='Parametric VaR')
        ax_covid.plot(covid_df.index, covid_df['VaR_Historical'] * 100, color='orange', lw=1.4, label='Historical VaR')
        ax_covid.plot(covid_df.index, covid_df['VaR_GARCH_EVT'] * 100, color='blue', lw=1.5, label='GARCH-EVT VaR')
        ax_covid.plot(covid_df.index, covid_df['ES_GARCH_EVT'] * 100, color='purple', lw=1.6, linestyle='--', label='GARCH-EVT ES')
        ax_covid.set_title('(C) March 2020 COVID-19 Liquidity Crash', fontweight='bold', fontsize=10.5)
        ax_covid.set_ylabel('Loss / Risk Measure (%)')
        ax_covid.grid(True)
        ax_covid.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
        ax_covid.legend(loc='upper right', fontsize=8)
        
    plt.tight_layout()
    save_path = os.path.join(FIGURES_DIR, save_name)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[Viz] Saved Figure 3 to: {save_path}")
    return save_path

def plot_regime_failure_rates(regime_summary, save_name="fig4_backtest_violations_by_regime.png"):
    regimes_to_plot = ["Calm (VIX < 20)", "Normal (20 <= VIX < 30)", "Crisis (VIX >= 30)"]
    labels = ["Calm\n(VIX < 20)", "Normal\n(20 ≤ VIX < 30)", "Crisis\n(VIX ≥ 30)"]
    
    norm_rates = [regime_summary[r]["VaR_Normal_Rate (%)"] for r in regimes_to_plot]
    hist_rates = [regime_summary[r]["VaR_Historical_Rate (%)"] for r in regimes_to_plot]
    evt_rates = [regime_summary[r]["VaR_GARCH_EVT_Rate (%)"] for r in regimes_to_plot]
    es_rates = [regime_summary[r]["ES_GARCH_EVT_Rate (%)"] for r in regimes_to_plot]
    
    x = np.arange(len(labels))
    width = 0.18
    
    fig, ax = plt.subplots(figsize=(10, 5.5))
    
    rects1 = ax.bar(x - 1.5 * width, norm_rates, width, label='Parametric VaR (Gaussian)', color='#d9534f', edgecolor='black', lw=0.6)
    rects2 = ax.bar(x - 0.5 * width, hist_rates, width, label='Historical Simulation VaR', color='#f0ad4e', edgecolor='black', lw=0.6)
    rects3 = ax.bar(x + 0.5 * width, evt_rates, width, label='Dynamic GARCH-EVT VaR', color='#337ab7', edgecolor='black', lw=0.6)
    rects4 = ax.bar(x + 1.5 * width, es_rates, width, label='Dynamic GARCH-EVT ES', color='#5cb85c', edgecolor='black', lw=0.6)
    
    ax.axhline(1.0, color='black', linestyle='--', lw=1.4, label='Basel 99% Theoretical Failure Target (1.0%)')
    
    ax.set_ylabel('Empirical Failure Rate (%)')
    ax.set_title('Figure 4: Out-of-Sample Violation Rates by Volatility Regime', fontweight='bold', pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontweight='bold')
    ax.legend(loc='upper left', framealpha=0.9)
    ax.grid(True, axis='y')
    ax.set_ylim(0, max(norm_rates) * 1.25)
    
    for rects in [rects1, rects2, rects3, rects4]:
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.2f}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=8)
                        
    plt.tight_layout()
    save_path = os.path.join(FIGURES_DIR, save_name)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[Viz] Saved Figure 4 to: {save_path}")
    return save_path

def plot_dirichlet_robustness(dirichlet_results, save_name="fig5_dirichlet_robustness_test.png"):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    
    data = [
        dirichlet_results["VaR_Normal_Rates"],
        dirichlet_results["VaR_Historical_Rates"],
        dirichlet_results["VaR_GARCH_EVT_Rates"]
    ]
    labels = ['Parametric VaR', 'Historical VaR', 'GARCH-EVT VaR']
    colors = ['#d9534f', '#f0ad4e', '#337ab7']
    
    bplot = ax1.boxplot(data, patch_artist=True, tick_labels=labels, widths=0.55)
    for patch, color in zip(bplot['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    for median in bplot['medians']:
        median.set(color='black', linewidth=1.5)
        
    ax1.axhline(1.0, color='red', linestyle='--', lw=1.3, label='Theoretical 1.0% Target')
    ax1.set_ylabel('Full-Sample Breach Rate (%)')
    ax1.set_title('(A) 100 Dirichlet Portfolios: Breach Rate Spread', fontweight='bold')
    ax1.grid(True, axis='y')
    ax1.legend(loc='upper right')
    
    for rates, label, color in zip(data, labels, colors):
        ax2.hist(rates, bins=15, alpha=0.5, label=label, color=color, density=True)
        
    ax2.axvline(1.0, color='red', linestyle='--', lw=1.3, label='Theoretical 1.0%')
    ax2.set_xlabel('Breach Rate (%)')
    ax2.set_ylabel('Probability Density')
    ax2.set_title('(B) Empirical Distribution Across Allocations', fontweight='bold')
    ax2.grid(True)
    ax2.legend(loc='upper right')
    
    plt.suptitle('Figure 5: Allocation Robustness Evaluation Across 100 Dirichlet Portfolio Weightings', fontweight='bold', y=1.02)
    plt.tight_layout()
    save_path = os.path.join(FIGURES_DIR, save_name)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[Viz] Saved Figure 5 to: {save_path}")
    return save_path
