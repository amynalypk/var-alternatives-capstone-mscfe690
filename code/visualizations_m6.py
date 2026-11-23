"""Generate the Module 6/7 extension publication figures (Figures 6–14).

These figures document EVT threshold selection, innovation diagnostics,
regime segmentation, breach economics, dynamic portfolio optimisation, and
runtime-versus-accuracy trade-offs. They are generated reproducibly from the
cached analysis data and metrics manifest and saved as 300-DPI PNG files in
the configured ``figures/`` directory.
"""

import json
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.text as mtext
from matplotlib.transforms import Bbox
from scipy.stats import probplot, t as student_t
from statsmodels.tsa.stattools import acf

from config import (
    FIGURES_DIR, M6_METRICS_MANIFEST, NOTIONAL_USD, PRIMARY_CONFIDENCE,
    PRIMARY_GARCH_INNOVATION_DISTRIBUTION, PRIMARY_POT_THRESHOLD_QUANTILE,
    VIX_CALM_THRESHOLD, VIX_CRISIS_THRESHOLD,
)
from tail_metrics import clopper_pearson

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 11.5
plt.rcParams['axes.labelsize'] = 10.5
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 8.8
plt.rcParams['figure.titlesize'] = 13
plt.rcParams['lines.linewidth'] = 1.3
plt.rcParams['grid.alpha'] = 0.35
plt.rcParams['grid.linestyle'] = '--'

BLUE, ORANGE, RED, GREEN, PURPLE, GREY = ("#1f77b4", "#ff7f0e", "#d9534f",
                                          "#5cb85c", "#7b3fa0", "#555555")
REGIME_COLORS = {"calm": "#2e7d32", "normal": "#f9a825", "crisis": "#b71c1c"}
PERCENT = 100.0  




def _assert_annotations_visible(fig, save_name):
    
    """Compute or assemble the _assert_annotations_visible result used by the visualizations_m6 analysis."""
    fig.canvas.draw()
    for artist in fig.findobj(mtext.Annotation):
        if not artist.get_visible() or artist.axes is None:
            continue
        if getattr(artist, "_annotation_clip", True) is False:
            continue
        box = artist.get_window_extent()
        overlap = Bbox.intersection(box, artist.axes.get_window_extent())
        if overlap is None or overlap.width <= 0 or overlap.height <= 0:
            raise ValueError(
                f"{save_name}: caption {artist.get_text()!r} falls outside its axes "
                f"and would be clipped away")


def _finish(fig, save_name, suptitle, top=0.955):

    """Compute or assemble the _finish result used by the visualizations_m6 analysis."""
    for ax in fig.axes:
        if ax.get_title():
            if not ax.get_xlabel():
                raise ValueError(f"{save_name}: panel '{ax.get_title()}' has no x label")
            if not ax.get_ylabel():
                raise ValueError(f"{save_name}: panel '{ax.get_title()}' has no y label")
    fig.suptitle(suptitle, fontweight="bold", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, top))
    _assert_annotations_visible(fig, save_name)
    os.makedirs(FIGURES_DIR, exist_ok=True)
    path = os.path.join(FIGURES_DIR, save_name)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[Viz] Saved {save_name}")
    return path


def _year_locator(ax, every=2):
    """Compute or assemble the _year_locator result used by the visualizations_m6 analysis."""
    ax.xaxis.set_major_locator(mdates.YearLocator(every))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def _to_frame(data):
    """Compute or assemble the _to_frame result used by the visualizations_m6 analysis."""
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    return frame.drop(columns=["index"], errors="ignore")


def _stagger_xlabels(axis, values, fontsize=8.6, labelpad=6.0):
    
    """Compute or assemble the _stagger_xlabels result used by the visualizations_m6 analysis."""
    axis.set_xticks(values)
    axis.set_xticklabels([])
    points_to_display = axis.get_figure().dpi / 72.0
    row_step = 11.0 * points_to_display
    placed = []
    deepest = 0
    for value in values:
        text = f"{value:g}"
        need = (len(text) * fontsize * 0.62 + 3.0) * points_to_display
        x = float(axis.transData.transform((value, 0.0))[0])
        row = 0
        while any(r == row and abs(x - px) < need for r, px in placed):
            row += 1
        placed.append((row, x))
        deepest = max(deepest, row)
        axis.annotate(text, xy=(value, 0.0),
                      xycoords=("data", "axes fraction"),
                      xytext=(0, -(6.0 + row * 11.0)), textcoords="offset points",
                      ha="center", va="top", fontsize=fontsize,
                      annotation_clip=False)
    axis.set_xlabel(axis.get_xlabel(), labelpad=labelpad + deepest * 11.0)




def plot_mean_excess_plot(z, curve, band, production_u,
                          production_q=PRIMARY_POT_THRESHOLD_QUANTILE,
                          min_exceedances=100,
                          save_name="fig6_mean_excess_plot_threshold_selection.png",
                          innovation="Gaussian", n_observations=None):
    
    """Compute or assemble the plot_mean_excess_plot result used by the visualizations_m6 analysis."""
    losses = -np.asarray(z, dtype=float)
    curve = _to_frame(curve)
    n_tot = losses.size if n_observations is None else int(n_observations)

    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    counts = curve["n_exceedances"].to_numpy(dtype=float)
    ax.errorbar(curve["u"], curve["sample_e_hat"],
                yerr=curve["se_excess"].to_numpy(dtype=float), fmt="none",
                ecolor=GREY, elinewidth=0.8, capsize=2, alpha=0.75,
                label="±1 standard error of $\\hat{e}(u)$")
    ax.scatter(curve["u"], curve["sample_e_hat"], s=12 + 90 * counts / counts.max(),
               c=BLUE, alpha=0.8, edgecolor="white", linewidth=0.4, zorder=3,
               label="Sample mean excess $\\hat{e}(u)$ (marker area ∝ exceedances)")
    ax.plot(curve["u"], curve["gpd_e_hat"], color=RED, lw=1.6, zorder=4,
            label="GPD-implied $\\beta/(1-\\xi)+\\xi u/(1-\\xi)$")
    ax.axvspan(band["u_lo"], band["u_hi"], color=GREEN, alpha=0.13, zorder=0,
               label=(f"Widest near-linear band: u ∈ [{band['u_lo']:.2f}, "
                      f"{band['u_hi']:.2f}]"))
    eligible = curve.loc[curve["n_exceedances"] >= min_exceedances, "u"]
    floor = float(eligible.max()) if len(eligible) else float(curve["u"].max())
    ax.axvline(floor, color="black", lw=1.1, ls=":",
               label=f"{min_exceedances}-exceedance data floor (u = {floor:.2f})")
    ax.axvline(production_u, color=PURPLE, lw=1.6, ls="--",
               label=f"Production q = {production_q:g} (u = {production_u:.2f})")

    ax.set_xlabel("Threshold $u$, in standardised loss units")
    ax.set_ylabel("Mean excess loss above $u$, $e(u)$")
    
    
    
    caveat = ("\nThe near-linear band ends at the data floor, not at a break in linearity"
              if band.get("band_at_support_edge") else "")
    ax.set_title(f"Mean excess plot, {innovation} innovations "
                 f"({n_tot:,} observations){caveat}", fontweight="bold")
    ax.grid(True)
    ax.legend(loc="lower left", fontsize=8.0, framealpha=0.92)

    
    
    
    
    
    
    top = ax.twiny()
    top.set_xlim(ax.get_xlim())
    marks = [0.50, 0.70, 0.80, 0.85, 0.90, 0.95, 0.975, 0.98]
    top.set_xticks([float(np.percentile(losses, PERCENT * q)) for q in marks],
                   [f"{q:g}" for q in marks], fontsize=8.6)
    top.set_xlabel("Implied quantile of the standardised loss distribution, q")

    return _finish(fig, save_name,
                   "Figure 6: The peaks-over-threshold level is measured, not assumed")




def plot_threshold_sensitivity(profile, sensitivity, production_q,
                               confidence_level=PRIMARY_CONFIDENCE,
                               save_name="fig7_threshold_sensitivity.png"):
    
    """Compute or assemble the plot_threshold_sensitivity result used by the visualizations_m6 analysis."""
    prof = _to_frame(profile)
    if {"threshold_quantile", "confidence_level"} <= set(prof.columns):
        prof = prof.set_index(["threshold_quantile", "confidence_level"])
    at_alpha = prof.xs(confidence_level, level="confidence_level").reset_index()
    sens = _to_frame(sensitivity)
    q = at_alpha["threshold_quantile"].to_numpy(dtype=float)
    clamped = at_alpha["clamped"].astype(bool).to_numpy(dtype=bool)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.8))

    if clamped.any():
        lo, hi = q[clamped].min(), q[clamped].max()
        ax1.axvspan(lo, hi, color=RED, alpha=0.10, zorder=0,
                    label=f"$\\xi$ clamp active, q ∈ [{lo:g}, {hi:g}]")
    ax1.plot(q, at_alpha["var_z"], "o-", color=BLUE, lw=1.6, ms=6,
             label="99% VaR quantile used, $z$")
    raw = at_alpha["var_z_raw"].to_numpy(dtype=float)
    keep = np.isfinite(raw)
    if keep.any():
        ax1.plot(q[keep], raw[keep], "s--", color=PURPLE, lw=1.3, ms=6, mfc="none",
                 label="99% VaR from the unclamped $\\xi$ (defined for $\\xi < 1$)")
    ax1.plot(q, at_alpha["es_z"], "^-", color=GREEN, lw=1.2, ms=5,
             label="99% ES quantile used")
    ax1.axvline(production_q, color="black", ls=":", lw=1.1,
                label=f"production q = {production_q:g}")

    ax1b = ax1.twinx()
    ax1b.axhline(0.0, color=GREY, lw=0.9)
    ax1b.plot(q, at_alpha["xi_raw"], "v:", color=ORANGE, lw=1.2, ms=6,
              label="raw shape estimate $\\xi$")
    ax1b.set_ylabel("GPD shape estimate, $\\xi$", color=ORANGE)
    ax1b.tick_params(axis="y", colors=ORANGE)

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax1b.get_legend_handles_labels()
    ax1.set_xlabel("POT threshold quantile, q")
    ax1.set_ylabel("Standardised 99% VaR / ES quantile")
    ax1.set_title("(A) One tail claim per threshold, and what the clamp did to it",
                  fontweight="bold")

    
    
    
    
    
    for dist, color in (("normal", BLUE), ("t", ORANGE)):
        rows = sens[(sens["innovation_dist"] == dist)
                    & (sens["confidence_level"] == confidence_level)]
        rows = rows.sort_values("threshold_q")
        if not len(rows):
            continue
        interval = np.array([[clopper_pearson(int(x), int(n), 0.05)
                              for x, n in zip(rows["Actual Breaches"], rows["Total Obs"])]])
        interval = interval.reshape(-1, 2) * PERCENT
        threshold = rows["threshold_q"].to_numpy(dtype=float)
        rate = rows["Breach Rate (%)"].to_numpy(dtype=float)
        ax2.fill_between(threshold, interval[:, 0], interval[:, 1], color=color,
                         alpha=0.16,
                         label=f"95% Clopper–Pearson band, {dist} innovations")
        ax2.plot(threshold, rate, "o-", color=color, lw=1.5, ms=6,
                 label=f"breach rate, {dist} innovations")
    ax2.axhline(PERCENT * (1.0 - confidence_level), color="black", ls="--", lw=1.2,
                label=f"nominal {PERCENT * (1.0 - confidence_level):.1f}%")
    ax2.axvline(production_q, color="black", ls=":", lw=1.1)
    ax2.set_xlabel("POT threshold quantile, q")
    ax2.set_ylabel("Out-of-sample breach rate (%)")
    ax2.set_title(f"(B) Walk-forward breach rate against the same grid, "
                  f"at {PERCENT * confidence_level:.1f}% coverage",
                  fontweight="bold")
    for axis in (ax1, ax2):
        axis.grid(True)
        _stagger_xlabels(axis, q)
    ax1.legend(handles1 + handles2, labels1 + labels2, loc="center left",
               fontsize=7.8, framealpha=0.92)
    ax2.legend(fontsize=7.6, loc="upper left")

    return _finish(fig, save_name,
                   "Figure 7: The tail quantile is insensitive to the threshold; the "
                   "shape estimate is not")




def _unit_variance_t(nu):
    
    """Compute or assemble the _unit_variance_t result used by the visualizations_m6 analysis."""
    scale = float(np.sqrt(max(nu - 2.0, 1e-9) / max(nu, 2.0 + 1e-9)))
    return student_t(nu, scale=scale)


def plot_innovation_diagnostics(z_normal, z_t, nu, n_lags=24,
                                save_name="fig8_innovation_diagnostics.png"):
    
    """Compute or assemble the plot_innovation_diagnostics result used by the visualizations_m6 analysis."""
    zn = np.asarray(z_normal, dtype=float)
    zt = np.asarray(z_t, dtype=float)
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9))

    for ax, pair, label, panel in ((axes[0, 0], (zn, zt), "standardised", "A"),
                                   (axes[0, 1], (zn ** 2, zt ** 2), "squared", "B")):
        for values, name in ((pair[0], "Gaussian innovations"),
                             (pair[1], "Student-t innovations")):
            ax.plot(range(n_lags + 1), acf(values, nlags=n_lags, fft=False),
                    "o-", ms=3.5, lw=1.2, label=name)
        band = 1.96 / np.sqrt(len(pair[0]))
        ax.axhline(band, color=GREY, ls="--", lw=1.0,
                   label="±95% white-noise band")
        ax.axhline(-band, color=GREY, ls="--", lw=1.0)
        ax.axhline(0.0, color="black", lw=0.8)
        ax.set_xlabel("Lag (trading days)")
        ax.set_ylabel(f"Autocorrelation of {label} innovations")
        ax.set_title(f"({panel}) {label.capitalize()} innovation autocorrelation",
                     fontweight="bold")
        ax.grid(True)
        ax.legend(fontsize=7.8)

    for ax, series, dist, color, panel, xlab in (
            (axes[1, 0], zn, "norm", BLUE, "C", "Theoretical $N(0,1)$ quantile"),
            (axes[1, 1], zn, _unit_variance_t(nu), ORANGE, "D",
             f"Theoretical unit-variance $t({nu:.1f})$ quantile")):
        probplot(series, dist=dist, plot=ax)
        ax.get_lines()[0].set(marker="o", ms=2.2, color=color, alpha=0.45,
                              linestyle="none")
        ax.get_lines()[1].set(color="black", lw=1.4)
        ax.set_xlabel(xlab)
        ax.set_ylabel("Ordered standardised innovation")
        title = (f"({panel}) Gaussian innovations against $N(0,1)$" if panel == "C"
                 else f"({panel}) The same innovations against the fitted "
                      f"$t(\\hat{{\\nu}})$, $\\hat{{\\nu}}$ = {nu:.2f}")
        ax.set_title(title, fontweight="bold")
        ax.grid(True)

    return _finish(fig, save_name,
                   "Figure 8: Second-order dependence is absent, first-order is not, "
                   "and the tails are heavier than Gaussian")




def plot_filter_comparison(vol_paths, parameters, save_name="fig9_garch_normal_vs_t.png"):
    
    """Compute or assemble the plot_filter_comparison result used by the visualizations_m6 analysis."""
    fig = plt.figure(figsize=(13, 8.5))
    gs = fig.add_gridspec(2, 2, height_ratios=(1.15, 1.0), width_ratios=(1.45, 1.0))
    styles = {"normal": (BLUE, "-"), "t": (ORANGE, "--")}
    names = list(vol_paths)

    ax_path = fig.add_subplot(gs[0, :])
    for dist in names:
        index, sigma = vol_paths[dist]
        color, linestyle = styles.get(dist, (GREY, ":"))
        label = "Gaussian innovations" if dist == "normal" else "Student-t innovations"
        ax_path.plot(index, np.asarray(sigma) * PERCENT, color=color, ls=linestyle,
                     lw=1.2, label=f"{label}, α+β = {parameters[dist]['persistence']:.4f}")
    ax_path.set_xlabel("Date")
    ax_path.set_ylabel("Conditional volatility $\\sigma_t$ (%)")
    ax_path.set_title("(A) The two filters price the same book", fontweight="bold")
    ax_path.grid(True)
    ax_path.legend(fontsize=8.2, ncol=2, loc="upper left")
    _year_locator(ax_path, 2)

    ax_ic = fig.add_subplot(gs[1, 0])
    base = parameters[names[0]]
    x = np.arange(len(names))
    aic = [parameters[d]["aic"] - base["aic"] for d in names]
    bic = [parameters[d]["bic"] - base["bic"] for d in names]
    ax_ic.bar(x - 0.18, aic, 0.34, label="ΔAIC vs Gaussian", color=BLUE,
              edgecolor="black", lw=0.5)
    ax_ic.bar(x + 0.18, bic, 0.34, label="ΔBIC vs Gaussian", color=GREEN,
              edgecolor="black", lw=0.5)
    for j, dist in enumerate(names):
        ax_ic.annotate(f"logL {parameters[dist]['loglikelihood']:.1f}",
                       (x[j], 8.0), ha="center", fontsize=7.5)
        for offset, value in ((-0.18, aic[j]), (0.18, bic[j])):
            if value:
                ax_ic.text(x[j] + offset, value - 5.0, f"{value:+.0f}", ha="center",
                           va="top", fontsize=7.4)
    ax_ic.axhline(0.0, color="black", lw=0.9)
    ax_ic.set_ylim(min(min(aic), min(bic)) * 1.18, 22.0)
    ax_ic.set_xticks(x, ["Gaussian\ninnovations", "Student-t\ninnovations"][:len(names)])
    ax_ic.set_xlabel("Innovation distribution (labels show the log-likelihood)")
    ax_ic.set_ylabel("Information criterion, points below the Gaussian fit")
    ax_ic.set_title("(B) The t filter fits materially better", fontweight="bold")
    ax_ic.grid(True, axis="y")
    ax_ic.legend(fontsize=8)

    ax_nu = fig.add_subplot(gs[1, 1])
    nu_values = [parameters[d].get("nu", np.nan) for d in names]
    heights = [min(value, 30.0) if np.isfinite(value) else 30.0 for value in nu_values]
    ax_nu.bar(x, heights, 0.5, color=[styles[d][0] for d in names],
              edgecolor="black", lw=0.5)
    for j, value in enumerate(nu_values):
        ax_nu.text(x[j], heights[j] + 0.8,
                   "∞ (Gaussian)" if not np.isfinite(value) else f"{value:.2f}",
                   ha="center", fontsize=8.5)
    ax_nu.axhline(8.0, color=GREY, ls="--", lw=1.0)
    ax_nu.annotate("ν = 8: Gaussian tails already adequate", (0.98, 9.2),
                   xycoords=("axes fraction", "data"), fontsize=7.2, color=GREY,
                   ha="right", va="bottom")
    ax_nu.set_ylim(0, 34)
    ax_nu.set_xticks(x, names)
    ax_nu.set_xlabel("Innovation distribution")
    ax_nu.set_ylabel("Estimated degrees of freedom, ν (axis capped at 30)")
    ax_nu.set_title("(C) Where the extra tail weight comes from", fontweight="bold")
    ax_nu.grid(True, axis="y")

    return _finish(fig, save_name,
                   "Figure 9: Student-t innovations fit far better and move the risk "
                   "measure very little")




def plot_regime_panels(regime_frame, cross_tab, agreement, sector,
                       save_name="fig10_portfolio_vs_vix_regimes.png"):
    
    """Compute or assemble the plot_regime_panels result used by the visualizations_m6 analysis."""
    frame = regime_frame.dropna(subset=["RealisedVol", "VIX_lag",
                                         "portfolio_regime_balanced"])
    fig, axes = plt.subplots(2, 2, figsize=(14, 9.5))

    ax = axes[0, 0]
    ax.plot(frame.index, frame["RealisedVol"] * PERCENT, color=BLUE, lw=0.9,
            label="Portfolio 20-day realised volatility (lagged, left)")
    for label in ("calm", "crisis"):
        ax.fill_between(frame.index, 0, frame["RealisedVol"].max() * PERCENT,
                        where=frame["vix_regime"] == label, color=REGIME_COLORS[label],
                        alpha=0.10)
    ax_r = ax.twinx()
    ax_r.plot(frame.index, frame["VIX_lag"], color=RED, lw=0.8, alpha=0.85,
              label="CBOE VIX (lagged, right)")
    for level in (VIX_CALM_THRESHOLD, VIX_CRISIS_THRESHOLD):
        ax_r.axhline(level, color=GREY, ls="--", lw=0.8)
    ax.set_xlabel("Date")
    ax.set_ylabel("Portfolio realised volatility (%)", color=BLUE)
    ax_r.set_ylabel("VIX (index points)", color=RED)
    ax.set_title("(A) The book and the index do not share a state", fontweight="bold")
    ax.legend(ax.get_lines()[:1] + ax_r.get_lines()[:1],
              ["Portfolio realised volatility (left)", "VIX (right)"],
              fontsize=7.6, loc="upper left")
    _year_locator(ax, 3)

    ax = axes[0, 1]
    tab = _to_frame(cross_tab)
    counts = tab.pivot(index="portfolio_regime", columns="vix_regime",
                       values="Observations")
    rates = tab.pivot(index="portfolio_regime", columns="vix_regime",
                      values="Breach Rate (%)")
    order_vix = [c for c in ("calm", "normal", "crisis") if c in counts.columns]
    order_port = [r for r in ("low_vol", "mid_vol", "high_vol") if r in counts.index]
    grid = counts.reindex(index=order_port, columns=order_vix).to_numpy(dtype=float)
    rate_grid = rates.reindex(index=order_port, columns=order_vix).to_numpy(dtype=float)
    ax.imshow(grid, cmap="Blues")
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            dark = grid[i, j] > 0.6 * np.nanmax(grid)
            ax.text(j, i - 0.14, f"{int(grid[i, j]):,}", ha="center", va="center",
                    fontsize=9.5, fontweight="bold",
                    color="white" if dark else "black")
            note = (f"{rate_grid[i, j]:.2f}% breach" if np.isfinite(rate_grid[i, j])
                    else "no exception")
            ax.text(j, i + 0.20, note, ha="center", va="center", fontsize=7.8,
                    color="white" if dark else "black")
    ax.set_xticks(range(len(order_vix)), [f"VIX: {v}" for v in order_vix], fontsize=8.5)
    ax.set_yticks(range(len(order_port)),
                  [f"book: {p.replace('_', ' ')}" for p in order_port], fontsize=8.5)
    ax.set_xlabel("Market state (VIX band)")
    ax.set_ylabel("Book state (lagged realised volatility tercile)")
    ax.set_title("(B) 3×3 cross-tabulation; the diagonal is agreement",
                 fontweight="bold")

    ax = axes[1, 0]
    names = list(agreement)
    metrics = (("pct_agreement", "Share of days in agreement"),
               ("kappa_unweighted", "Cohen’s $\\kappa$, unweighted"),
               ("kappa_quadratic", "Cohen’s $\\kappa$, quadratic"))
    colours = (BLUE, GREEN, ORANGE)
    width, x = 0.24, np.arange(len(names))
    for k, ((metric, pretty), color) in enumerate(zip(metrics, colours)):
        values = [agreement[name][metric] / PERCENT if metric == "pct_agreement"
                  else agreement[name][metric] for name in names]
        bars = ax.bar(x + (k - 1) * width, values, width, label=pretty, color=color,
                      edgecolor="black", lw=0.5)
        for bar, value in zip(bars, values):
            ax.annotate(f"{value:.2f}",
                        (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 2), textcoords="offset points", ha="center",
                        fontsize=7.5)
    ax.axhline(0.60, color="black", ls="--", lw=1.0)
    ax.annotate("κ = 0.60: the conventional\n'substantial agreement' cut-off",
                (0.97, 0.60), xytext=(0, 4), textcoords="offset points", fontsize=7.2,
                ha="right")
    ax.set_xticks(x, [name.replace("portfolio_regime_", "portfolio\n") for name in names],
                  fontsize=8.2)
    ax.set_xlabel("Portfolio regime definition")
    ax.set_ylabel("Share of days, and Cohen’s κ")
    ax.set_title("(C) Agreement is weak on either cut", fontweight="bold")
    ax.set_ylim(0, 1.0)
    ax.grid(True, axis="y")
    ax.legend(fontsize=7.4, loc="upper left")

    ax = axes[1, 1]
    sec = _to_frame(sector).sort_values("contribution_pct")
    ax.barh(sec["sector"], sec["contribution_pct"], color=PURPLE, alpha=0.85,
            edgecolor="black", lw=0.5)
    for y, (value, names_) in enumerate(zip(sec["contribution_pct"], sec["names"])):
        ax.annotate(f"{value:+.3f}%  ({names_})", (value, y), xytext=(3, 0),
                    textcoords="offset points", va="center", fontsize=7.0)
    ax.axvline(0.0, color="black", lw=0.9)
    ax.set_xlabel("Mean daily contribution to the portfolio return on the "
                  "disagreement days (%)")
    ax.set_ylabel("GICS sector")
    ax.set_title("(D) Who moved when the VIX said nothing", fontweight="bold")
    ax.grid(True, axis="x")
    lo = float(sec["contribution_pct"].min())
    hi = float(sec["contribution_pct"].max())
    
    
    
    span = max(hi - lo, abs(hi), 1e-6)
    ax.set_xlim(lo - 0.12 * span, hi + 1.15 * span)

    return _finish(fig, save_name,
                   "Figure 10: VIX is a market-state proxy, not a portfolio-state proxy")




def plot_breach_magnitudes(register, adequacy, vix, notional=NOTIONAL_USD,
                           save_name="fig11_breach_magnitudes_and_reserves.png"):
    
    """Compute or assemble the plot_breach_magnitudes result used by the visualizations_m6 analysis."""
    reg = _to_frame(register).copy()
    if "Date" in reg.columns and not np.issubdtype(reg.index.dtype, np.datetime64):
        reg = reg.set_index("Date")
    reg.index = pd.to_datetime(reg.index)
    reg = reg.sort_index()
    regime = pd.cut(pd.Series(vix).reindex(reg.index),
                    bins=[-np.inf, VIX_CALM_THRESHOLD, VIX_CRISIS_THRESHOLD, np.inf],
                    labels=list(REGIME_COLORS))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9),
                                   gridspec_kw={"height_ratios": (1.05, 1.0)})

    for label, color in REGIME_COLORS.items():
        sub = reg[np.asarray((regime == label).fillna(False), dtype=bool)]
        ax1.vlines(sub.index, 0.0, sub["Exceedance"] * PERCENT, color=color, lw=0.9,
                   alpha=0.8)
        ax1.scatter(sub.index, sub["Exceedance"] * PERCENT, color=color, s=20,
                    label=f"VIX {label}: {len(sub)} exceptions")
    mean_excess = float(reg["Exceedance"].mean()) * PERCENT
    ax1.axhline(mean_excess, color=GREY, ls="--", lw=1.1,
                label=f"mean excess {mean_excess:.2f} pp")
    ax1.axhline(0.0, color="black", lw=0.8)
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Loss in excess of 99% VaR (percentage points)")
    ax1.set_title("(A) Every exception, sized and dated", fontweight="bold")
    ax1.grid(True)
    ax1.legend(fontsize=8, loc="upper right")
    _year_locator(ax1, 2)

    
    
    
    
    
    
    cumulative_var = (np.maximum(reg["Loss"] - reg["VaR"], 0.0).cumsum() * notional)
    cumulative_es = (np.maximum(reg["Loss"] - reg["ES_forecast"], 0.0).cumsum()
                     * notional)
    expected = (adequacy["Cumulative Unreserved under VaR (USD)"],
                adequacy["Cumulative Unreserved under ES (USD)"])
    for drawn, wanted, name in ((cumulative_var, expected[0], "VaR"),
                                (cumulative_es, expected[1], "ES")):
        
        
        if wanted is not None and abs(float(drawn.iloc[-1]) - float(wanted)) > 1.0:
            raise AssertionError(
                f"fig11 cumulative {name} shortfall ends at {float(drawn.iloc[-1]):,.0f} "
                f"but the manifest reports {float(wanted):,.0f}")
    ax2.plot(reg.index, cumulative_var / 1e6, color=BLUE, lw=1.5,
             label="Cumulative shortfall against the VaR reserve (flow)")
    ax2.plot(reg.index, cumulative_es / 1e6, color=GREEN, lw=1.5,
             label="Cumulative shortfall against the ES reserve (flow)")
    
    
    
    for level, color, side in ((adequacy["Mean VaR Reserve (USD)"] / 1e6, BLUE, "top"),
                               (adequacy["Mean ES Reserve (USD)"] / 1e6, GREEN,
                                "bottom")):
        ax2.axhline(level, color=color, ls=":", lw=1.2)
        ax2.annotate(f"reserve held daily: ${level:.2f} m", (0.985, level),
                     xycoords=("axes fraction", "data"), ha="right", va=side,
                     xytext=(0, -3 if side == "top" else 3),
                     textcoords="offset points", fontsize=7.8, color=color)
    extra = adequacy["Incremental Capital Held (USD)"] / 1e6
    ax2.axhline(extra, color=PURPLE, ls="--", lw=1.3)
    ax2.annotate(f"incremental capital of the ES reserve: ${extra:.2f} m "
                 f"({adequacy['Incremental Capital (% of notional)']:.2f}% of notional), "
                 f"held every day", (0.02, extra),
                 xycoords=("axes fraction", "data"), xytext=(0, 5),
                 textcoords="offset points", fontsize=7.8, color=PURPLE)
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Cumulative unreserved loss (USD millions)")
    ax2.set_title("(B) A reserve is a stock, a shortfall is a flow — the two are never "
                  "added", fontweight="bold")
    ax2.grid(True)
    ax2.legend(fontsize=8, loc="upper left")
    _year_locator(ax2, 2)

    return _finish(fig, save_name,
                   "Figure 11: What the exceptions cost, and what each reserve would "
                   "have needed")




def plot_dynamic_books(paths, table, headline=("Equal weight (rebalanced)",
                                               "Minimum ES"),
                       save_name="fig12_dynamic_portfolio_optimisation.png"):
    
    """Compute or assemble the plot_dynamic_books result used by the visualizations_m6 analysis."""
    long = _to_frame(paths).copy()
    long["Date"] = pd.to_datetime(long["Date"])
    wide = {column: long.pivot(index="Date", columns="Strategy", values=column)
            for column in ("Wealth", "Turnover", "ES_GARCH_EVT", "VaR_GARCH_EVT")}
    strategies = (list(table.index) if isinstance(table, pd.DataFrame)
                  and table.index.name == "Strategy"
                  else sorted(long["Strategy"].unique()))
    cmap = plt.get_cmap("tab10")
    style = {name: (cmap(i % 10), "-" if name in headline else ":")
             for i, name in enumerate(strategies)}

    fig, axes = plt.subplots(2, 2, figsize=(14, 9.5))

    for ax, values, ylabel, panel, title, leg in (
            
            
            (axes[0, 0], lambda name: wide["Wealth"][name] * PERCENT,
             "Growth of 100 invested (index points)", "A",
             "Wealth under each book, net of 10 bps on turnover", "upper left"),
            (axes[0, 1], lambda name: (wide["Wealth"][name]
                                       / wide["Wealth"][name].cummax() - 1.0) * PERCENT,
             "Drawdown from peak (%)", "B", "The same books in drawdown",
             "lower right")):
        for name in strategies:
            color, linestyle = style[name]
            ax.plot(values(name).index, values(name), color=color, ls=linestyle,
                    lw=1.8 if name in headline else 0.9, label=name)
        ax.set_xlabel("Date")
        ax.set_ylabel(ylabel)
        ax.set_title(f"({panel}) {title}", fontweight="bold")
        ax.grid(True)
        ax.legend(fontsize=6.6, loc=leg, ncol=2)
        _year_locator(ax, 3)

    ax = axes[1, 0]
    for name in headline:
        color = style[name][0]
        es = wide["ES_GARCH_EVT"][name].dropna() * PERCENT
        var = wide["VaR_GARCH_EVT"][name].dropna() * PERCENT
        ax.plot(es.index, es, color=color, lw=1.4, label=f"{name}: forecast ES")
        ax.plot(var.index, var, color=color, lw=1.0, ls="--",
                label=f"{name}: forecast VaR")
    ax.set_yscale("log")
    ax.set_xlabel("Date")
    ax.set_ylabel("99% forecast risk measure (%), log scale")
    
    
    
    
    pair = [wide["ES_GARCH_EVT"][name].dropna() for name in headline]
    gap = (pair[1] - pair[0]).dropna() if len(pair) == 2 else None
    lower = "" if gap is None or not len(gap) else \
        f" on {100 * (gap < 0).mean():.0f}% of days"
    ax.set_title("(C) The optimiser's own ES forecast is the lower one"
                 f"{lower}", fontweight="bold")
    ax.grid(True, which="both")
    ax.legend(fontsize=7.2, loc="upper left")
    _year_locator(ax, 3)

    ax = axes[1, 1]
    for name in headline:
        color = style[name][0]
        turnover = wide["Turnover"][name].dropna() * PERCENT
        ax.bar(turnover.index, turnover, width=3.6, color=color, alpha=0.65,
               label=f"{name}: one-way turnover at rebalance")
    ax.set_xlabel("Date")
    ax.set_ylabel("One-way turnover per rebalance (%)")
    ax.set_title("(D) The price of the reduction, paid every twenty days",
                 fontweight="bold")
    ax.grid(True, axis="y")
    ax.legend(fontsize=7.2, loc="upper left")
    _year_locator(ax, 3)

    return _finish(fig, save_name,
                   "Figure 12: Minimum-ES optimisation cuts forecast tail risk and "
                   "raises the exception count")




def plot_cost_vs_accuracy(model_costs, performance,
                          save_name="fig14_cost_vs_accuracy.png"):
    
    """Compute or assemble the plot_cost_vs_accuracy result used by the visualizations_m6 analysis."""
    costs = _to_frame(model_costs)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.4))

    ordered = costs.sort_values("Calibration median (ms)")
    y = np.arange(len(ordered))
    median = ordered["Calibration median (ms)"].to_numpy(dtype=float)
    ax1.barh(y, median, color=BLUE, alpha=0.85, edgecolor="black", lw=0.5,
             label="median")
    ax1.errorbar(median, y,
                 xerr=[median - ordered["Calibration min (ms)"].to_numpy(dtype=float),
                       ordered["Calibration p95 (ms)"].to_numpy(dtype=float) - median],
                 fmt="none", ecolor=RED, elinewidth=1.0, capsize=2.5,
                 label="min to p95")
    ax1.set_yticks(y, ordered["Model"], fontsize=7.4)
    ax1.set_xscale("log")
    ax1.set_xlim(median.min() * 0.55,
                 float(ordered["Calibration p95 (ms)"].max()) * 1.6)
    ax1.set_xlabel("Time to produce one calibration, log scale (milliseconds)")
    ax1.set_ylabel("Calibration step")
    ax1.set_title("(A) Calibration cost spans four orders of magnitude",
                  fontweight="bold")
    ax1.grid(True, axis="x", which="both")
    ax1.legend(fontsize=8, loc="lower right")

    pairs = (("Historical simulation VaR", "VaR_Historical", ORANGE),
             ("Gaussian parametric VaR", "VaR_Normal", RED),
             ("Full GARCH-EVT calibration", "VaR_GARCH_EVT", BLUE))
    
    
    
    
    offsets = ((9, -4), (9, 9), (9, -4))
    glyphs = ("o", "s", "^")
    for i, (label, column, color) in enumerate(pairs):
        row = costs.loc[costs["Model"] == label]
        if not len(row) or column not in performance:
            continue
        score = performance[column]
        cost = float(row["Full-pass cost (s)"].iloc[0])
        amortised = float(row["Amortised per forecast (us)"].iloc[0])
        ax2.scatter(cost, score["Kupiec p-val"], s=150, marker=glyphs[i % len(glyphs)],
                    color=color, alpha=0.8, zorder=3, edgecolor="black", lw=0.6,
                    label=f"{label}\n{amortised:,.0f} \u00b5s per forecast, amortised")
        ax2.annotate(f"{score['Breach Rate (%)']:.2f}% breach",
                     (cost, score["Kupiec p-val"]), xytext=offsets[i],
                     textcoords="offset points", fontsize=7.6)
    ax2.axhline(0.05, color="black", ls="--", lw=1.2,
                label="Kupiec rejection boundary, p = 0.05")
    ax2.set_xscale("log")
    ax2.set_xlabel("Wall time for the full walk-forward pass, log scale (seconds)")
    ax2.set_ylabel("Kupiec p-value, Module 4 walk-forward "
                   "(larger is better calibration)")
    ax2.set_ylim(-0.06, 1.05)
    ax2.set_title("(B) At a daily horizon, cost buys no accuracy and accuracy costs "
                  "nothing", fontweight="bold")
    ax2.grid(True)
    ax2.legend(fontsize=6.9, loc="center right")

    return _finish(fig, save_name,
                   "Figure 14: Computational efficiency against forecast accuracy")




def plot_es_frontier(reduction_records, table,
                     save_name="fig13_es_reduction_and_frontier.png"):
    
    """Compute or assemble the plot_es_frontier result used by the visualizations_m6 analysis."""
    rec = _to_frame(reduction_records)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.4))

    markers = ["o", "s", "^", "D", "v"]
    for i, alpha in enumerate(sorted(rec["alpha"].unique())):
        rows = rec[rec["alpha"] == alpha]
        ax1.scatter(rows["EW forecast ES (%)"], rows["Min-ES forecast ES (%)"],
                    marker=markers[i % len(markers)], s=32, alpha=0.75,
                    label=f"α = {alpha:g}")
    limit = max(rec["EW forecast ES (%)"].max(), rec["Min-ES forecast ES (%)"].max())
    ax1.plot([0, limit], [0, limit], color="black", ls="--", lw=1.1,
             label="no reduction")
    ax1.set_xlabel("Equal-weight forecast ES at the decision date (%)")
    ax1.set_ylabel("Minimum-ES forecast ES on the same scenarios (%)")
    ax1.set_title("(A) Every sampled decision, priced on identical scenarios",
                  fontweight="bold")
    ax1.grid(True)
    ax1.legend(fontsize=8)

    rows = table if isinstance(table, pd.DataFrame) else pd.DataFrame(table)
    if rows.index.name != "Strategy":
        rows = rows.set_index("Strategy")
    
    
    
    
    glyphs = ("o", "s", "^", "D", "v", "P", "X", "*")
    for i, (name, row) in enumerate(rows.iterrows()):
        color = (BLUE if "Minimum ES" in name
                 else ORANGE if "Equal weight" in name else GREEN)
        kupiec = row.get("Realised Kupiec p", row.get("Kupiec p"))
        stated = ("n/a" if kupiec is None or not np.isfinite(kupiec)
                  else f"{kupiec:.3f}")
        ax2.scatter(row["Ann volatility (%)"], row["Ann return (%)"], s=120,
                    marker=glyphs[i % len(glyphs)], color=color, edgecolor="black",
                    lw=0.6, zorder=3,
                    label=f"{name} — {row['Breach Rate (%)']:.2f}% breach, "
                          f"Kupiec p={stated}")
    ax2.set_xlabel("Annualised realised volatility (%)")
    ax2.set_ylabel("Annualised return (%)")
    ax2.set_title("(B) The realised books: less risk, more exceptions",
                  fontweight="bold")
    ax2.grid(True)
    ax2.set_xlim(13.0, float(rows["Ann volatility (%)"].max()) + 9.0)
    ax2.set_ylim(float(rows["Ann return (%)"].min()) - 2.5,
                 float(rows["Ann return (%)"].max()) + 3.5)
    ax2.legend(fontsize=6.8, loc="lower right", framealpha=0.95)

    return _finish(fig, save_name,
                   "Figure 13: Forecast ES reduction, and what it bought in practice")




def generate_module6_figures(manifest_path=M6_METRICS_MANIFEST, returns_df=None,
                             portfolio=None):
    
    """Compute or assemble the generate_module6_figures result used by the visualizations_m6 analysis."""
    with open(manifest_path) as handle:
        manifest = json.load(handle)
    if returns_df is None or portfolio is None:
        from data_acquisition import fetch_and_cache_data, process_returns
        returns_df = process_returns(fetch_and_cache_data())
        portfolio = returns_df["Portfolio"]

    from regime_segmentation import build_regime_frame
    from threshold_sensitivity import garch_innovations

    saved = []
    z_normal, state_normal = garch_innovations(portfolio, dist="normal", window=None)
    z_t, state_t = garch_innovations(portfolio, dist="t", window=None)

    threshold = manifest["threshold"]["per_innovation"][
        PRIMARY_GARCH_INNOVATION_DISTRIBUTION]["full_sample"]
    production_u = float(threshold["selection"]["recommended_u"]
                         or np.percentile(-z_normal,
                                          PRIMARY_POT_THRESHOLD_QUANTILE * PERCENT))
    saved.append(plot_mean_excess_plot(
        z_normal, threshold["mel_curve"], threshold["selection"]["band"],
        production_u, innovation="Gaussian",
        n_observations=threshold["n_innovations"]))

    saved.append(plot_threshold_sensitivity(
        threshold["profile"], manifest["threshold"]["walk_forward_sensitivity"],
        PRIMARY_POT_THRESHOLD_QUANTILE))

    saved.append(plot_innovation_diagnostics(z_normal, z_t, float(state_t["nu"])))

    saved.append(plot_filter_comparison(
        {"normal": (portfolio.index, state_normal["cond_vol"]),
         "t": (portfolio.index, state_t["cond_vol"])},
        {"normal": {"persistence": state_normal["persistence"],
                    "loglikelihood": state_normal["loglikelihood"],
                    "aic": state_normal["aic"], "bic": state_normal["bic"],
                    "nu": float("inf")},
         "t": {"persistence": state_t["persistence"],
               "loglikelihood": state_t["loglikelihood"],
               "aic": state_t["aic"], "bic": state_t["bic"], "nu": state_t["nu"]}}))

    frame, _ = build_regime_frame(returns_df)
    saved.append(plot_regime_panels(
        frame, manifest["regime"]["cross_tab_with_breach_rates"],
        manifest["regime"]["agreement"],
        manifest["regime"]["stressed_but_calm"]["sector_contribution"]))

    register = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(manifest_path)),
                                        os.path.basename(
                                            manifest["economic"]["full_register_path"])),
                           index_col=0, parse_dates=True)
    saved.append(plot_breach_magnitudes(
        register,
        manifest["economic"]["by_recursion"]["corrected"]["reserve_adequacy"],
        returns_df["VIX"]))

    paths = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(manifest_path)),
                                     "m6_optimisation_paths.csv"), parse_dates=["Date"])
    table = _to_frame(manifest["optimisation"]["table"]).set_index("Strategy")
    saved.append(plot_dynamic_books(paths, table))

    saved.append(plot_cost_vs_accuracy(
        manifest["runtime"]["model_costs"],
        manifest["headline"]["module4_performance_summary"]))

    saved.append(plot_es_frontier(
        manifest["optimisation"]["forecast_es_reduction_records"], table))
    return saved


if __name__ == "__main__":
    written = generate_module6_figures()
    print(f"\n{len(written)} figures written to {FIGURES_DIR}")
