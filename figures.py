"""Draw the static charts from the tables in output/."""
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT = Path("output")
FIGURES = Path("figures")
INK, MUTED, GREY, GRID = "#0b0b0b", "#52514e", "#a8a7a2", "#e6e5e1"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                     "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "legend.frameon": False,
                     "axes.titlelocation": "left", "axes.titlecolor": INK, "axes.titlesize": 12})
SOURCE = "Sources: Kendall and Rekkas's 1867-2008 data; Elections Canada official voting results, 2011-2025."


def save(fig, name, title, subtitle, caption):
    fig.text(0.015, 0.985, title, fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.925, subtitle, color=MUTED, va="top")
    fig.text(0.015, 0.012, "\n".join(textwrap.wrap(caption, 138)), color=MUTED, fontsize=9, va="bottom")
    fig.savefig(FIGURES / name, dpi=200, facecolor="white")
    plt.close(fig)


def percent_points(ax):
    ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:+.0f}" if v else "0")


def rd_plot():
    bins = pd.read_csv(OUTPUT / "rd_bins.csv")
    main = pd.read_csv(OUTPUT / "main.csv")
    fit = main[(main["sample"] == "1872-2025") & (main["spec"] == "rdrobust, MSE-optimal")].iloc[0]
    d = bins[bins["sample"] == "1872-2025"]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.84, bottom=0.17)
    centres = d["bin_left"] + 0.005
    ax.scatter(centres * 100, d["win_rate"], s=d["n"] / 4, color=BLUE, alpha=0.85, edgecolor="white", linewidth=0.8, zorder=3)
    for side in (centres < 0, centres >= 0):
        # Same triangular kernel and bandwidth as the estimate, applied to the bins.
        inside = side & (centres.abs() <= fit["h"])
        weights = d["n"][inside] * (1 - centres[inside].abs() / fit["h"])
        slope, intercept = np.polyfit(centres[inside], d["win_rate"][inside], 1, w=np.sqrt(weights))
        xs = np.array([0, fit["h"] * np.sign(centres[inside].mean())])
        ax.plot(xs * 100, intercept + slope * xs, color=INK, lw=2, zorder=4)
    ax.axvline(0, color=MUTED, lw=1)
    ax.set_xlabel("Party's margin in the riding at the last election, points of votes cast")
    ax.set_ylabel("Share of these candidates who won")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")
    ax.annotate(f"Jump at zero: {fit['coef']:.3f}\n95% range {fit['ci_low']:.3f} to {fit['ci_high']:.3f}", (1, 0.32), color=INK, fontsize=11)
    save(fig, "rd_plot.png", "A party that narrowly won a riding is more likely to win it next time",
         "Liberal and Conservative candidates, 1872 to 2025. Each dot is a one-point bin, sized by the number of candidates.",
         f"The jump comes from rdrobust at a bandwidth of {fit['h'] * 100:.1f} points, with a robust bias-corrected range. The lines show that fit, redrawn from the bins. " + SOURCE)


def bandwidth():
    t = pd.read_csv(OUTPUT / "bandwidth.csv")
    r, o = t[t["method"] == "rdrobust"], t[t["method"] == "OLS with effects"]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.085, right=0.88, top=0.84, bottom=0.2)
    ax.fill_between(r["h"] * 100, r["ci_low"], r["ci_high"], color=BLUE, alpha=0.14, lw=0, label="95% robust range, rdrobust")
    ax.plot(r["h"] * 100, r["coef"], color=BLUE, lw=2, marker="o", ms=5, label="rdrobust, triangular kernel")
    ax.plot(o["h"] * 100, o["coef"], color=ORANGE, lw=2, marker="o", ms=5, label="OLS, province and parliament effects")
    ax.axhline(0, color=MUTED, lw=1)
    ax.set_xscale("log")
    ticks = [2, 3, 5, 7.5, 10, 15, 20, 30, 50, 70]
    ax.set_xticks(ticks, [f"{v:g}" for v in ticks])
    ax.minorticks_off()
    ax.set_xlabel("Bandwidth, points either side of zero (log scale)")
    ax.set_ylabel("Change in chance of winning")
    ax.legend(loc="upper center", bbox_to_anchor=(0.55, 1.03))
    ax.annotate("rdrobust", (70, r["coef"].iloc[-1]), xytext=(8, 0), textcoords="offset points", color=INK, va="center", fontsize=10)
    ax.annotate("OLS", (70, o["coef"].iloc[-1]), xytext=(8, 0), textcoords="offset points", color=INK, va="center", fontsize=10)
    save(fig, "bandwidth.png", "Estimates hold from about 5 to 15 points, then climb with the bandwidth",
         "Local linear estimates of the jump at each bandwidth, Liberals and Conservatives, 1872 to 2025.",
         "A straight line over a wide window picks up the slope in the data, so the estimate rises. The robust range is centred on the bias-corrected estimate, so at wide bandwidths the plain estimate falls above it. " + SOURCE)


def dots(ax, labels, coef, low, high, colour=BLUE, offset=0.0, label=None):
    y = np.arange(len(labels))[::-1] + offset
    ax.hlines(y, low, high, color=colour, lw=2)
    ax.scatter(coef, y, color=colour, s=64, zorder=3, edgecolor="white", linewidth=1.2, label=label)
    return y


def eras():
    t = pd.read_csv(OUTPUT / "eras.csv")
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.12, right=0.97, top=0.84, bottom=0.18)
    dots(ax, t["era"], t["coef"], t["ci_low"], t["ci_high"])
    ax.set_yticks(np.arange(len(t))[::-1], t["era"])
    ax.axvline(0, color=MUTED, lw=1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Change in chance of winning from a narrow win last time")
    save(fig, "eras.png", "No clear trend across 150 years",
         "Local linear estimates in each era, Liberals and Conservatives, with 95% robust ranges.",
         "Each era has its own data-driven bandwidth. Most ranges include zero and overlap each other. " + SOURCE)


def party_period():
    t = pd.read_csv(OUTPUT / "period_party.csv")
    periods = ["1872-1949", "1953-2008", "2011-2025"]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.12, right=0.97, top=0.84, bottom=0.18)
    for party, colour, offset in (("Liberal", BLUE, 0.14), ("Conservative", ORANGE, -0.14)):
        d = t[t["group"] == party].set_index("period").reindex(periods)
        dots(ax, periods, d["coef"], d["ci_low"], d["ci_high"], colour, offset, party)
    ax.set_yticks(np.arange(3)[::-1], periods)
    ax.axvline(0, color=MUTED, lw=1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Change in chance of winning from a narrow win last time")
    ax.legend(loc="lower right")
    save(fig, "party_period.png", "The party ranges overlap in every period",
         "Local linear estimates with 95% robust ranges.",
         "Each estimate has its own data-driven bandwidth. Since 2011 the Liberal estimate is above the Conservative one, but the two ranges overlap. " + SOURCE)


def placebo():
    t = pd.read_csv(OUTPUT / "placebo.csv")
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.085, right=0.97, top=0.84, bottom=0.18)
    real = t["cutoff"] == 0
    ax.vlines(t["cutoff"] * 100, t["ci_low"], t["ci_high"], color=[BLUE if r else GREY for r in real], lw=2)
    ax.scatter(t["cutoff"][~real] * 100, t["coef"][~real], color=GREY, s=56, zorder=3, edgecolor="white", linewidth=1.2)
    ax.scatter(t["cutoff"][real] * 100, t["coef"][real], color=BLUE, s=72, zorder=3, edgecolor="white", linewidth=1.2)
    ax.annotate("True cutoff", (0, t["ci_high"][real].iloc[0]), xytext=(6, 4), textcoords="offset points", color=INK, fontsize=10)
    ax.axhline(0, color=MUTED, lw=1)
    ax.set_xlabel("Cutoff, points of margin")
    ax.set_ylabel("Estimated jump")
    save(fig, "placebo.png", "No false cutoff shows a jump",
         "Local linear estimates at made-up cutoffs, each using only candidates on its side of zero, with 95% robust ranges.",
         "Twelve false cutoffs from -20 to +20 points. All ranges include zero. " + SOURCE)


def link_rules():
    t = pd.read_csv(OUTPUT / "link_rules.csv")
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.38, right=0.97, top=0.84, bottom=0.21)
    dots(ax, t["rule"], t["coef"], t["ci_low"], t["ci_high"])
    ax.set_yticks(np.arange(len(t))[::-1], [f"{r}, n = {n:,}" for r, n in zip(t["rule"], t["n"])])
    ax.axvline(0, color=MUTED, lw=1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Change in chance of winning from a narrow win last time")
    save(fig, "link_rules.png", "Since 2011 the estimate depends on how redistributions are handled",
         "Liberals and Conservatives, 2011 to 2025, under each linking rule, with 95% robust ranges.",
         "Overlap is the smaller of the new riding's voters from the old riding and the old riding's voters moved to the new one. Transposed margins use Elections Canada's votes recast on the new map. " + SOURCE)


if __name__ == "__main__":
    FIGURES.mkdir(exist_ok=True)
    rd_plot()
    bandwidth()
    eras()
    party_period()
    placebo()
    link_rules()
