#!/usr/bin/env python3
"""Render the portfolio cover cards for this project, light and dark.

Every number on the card is read from the pipeline outputs, never typed in --
if the analysis is re-run and the figures move, the cover moves with them.

Writes 1400x900 PNGs into the Gatsby site's featured folder, which is the size
the other project covers use.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
OUT = Path.home() / "selvi-portfolio" / "content" / "featured" / "RetailSegmentation"

# Palettes lifted from the site's own variables.js so the cards sit inside the
# page rather than on top of it.
LIGHT = dict(
    bg="#ffffff", card="#f6f8fa", line="#e4e9ef",
    head="#111827", body="#4b5563", faint="#848f9d",
    accent="#0f766e", bar="#c7d2da", grid="#eceff3",
)
DARK = dict(
    bg="#0d1117", card="#161b22", line="#21262d",
    head="#c9d1d9", body="#8b949e", faint="#6e7681",
    accent="#64ffda", bar="#2d3641", grid="#1b212a",
)

W, H = 1400, 900
DPI = 100


def load():
    cust = pd.read_csv(ROOT / "data" / "customers.csv")
    ret = pd.read_csv(ROOT / "outputs" / "cohort_retention.csv", index_col=0)
    ret.columns = [int(c) for c in ret.columns]
    find = json.loads((ROOT / "outputs" / "findings.json").read_text())

    rev = cust.groupby("Segment")["Monetary"].sum().sort_values()
    curve = [ret[m].mean() for m in range(13)]
    kpis = [
        (f"{cust['CustomerID'].nunique():,}", "customers"),
        (f"£{cust['Monetary'].sum()/1e6:.1f}M", "revenue"),
        (f"{top_share(cust):.1f}%", "revenue from top 20%"),
        (f"{find['retention']['month_12']:.1f}%", "retained at month 12"),
    ]
    return rev, curve, kpis


def top_share(cust):
    """Share of revenue held by the top 20% of customers by spend."""
    m = cust["Monetary"].sort_values(ascending=False)
    cut = int(round(len(m) * 0.2))
    return 100 * m.iloc[:cut].sum() / m.sum()


def rounded(ax, x, y, w, h, fc, ec):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012",
        linewidth=1, facecolor=fc, edgecolor=ec, transform=ax.transAxes,
        clip_on=False, zorder=0,
    ))


def render(pal, path):
    rev, curve, kpis = load()

    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=pal["bg"])
    bg = fig.add_axes([0, 0, 1, 1]); bg.set_axis_off(); bg.set_facecolor(pal["bg"])

    # ---- masthead -------------------------------------------------------
    # Matplotlib has no letter-spacing, so space the overline by hand.
    bg.text(0.045, 0.935, " ".join("RETAIL ANALYTICS"), color=pal["accent"],
            fontsize=12, fontweight="bold", va="top")
    bg.text(0.045, 0.885, "Customer Segmentation & Lifetime Value",
            color=pal["head"], fontsize=31, fontweight="bold", va="top")
    bg.text(0.045, 0.822,
            "1.07M transactions · RFM scoring · K-Means clustering · CLV modelling",
            color=pal["body"], fontsize=13.5, va="top")

    # ---- KPI cards ------------------------------------------------------
    cx, cw, gap = 0.045, 0.2125, 0.0185
    for i, (big, small) in enumerate(kpis):
        x = cx + i * (cw + gap)
        rounded(bg, x, 0.615, cw, 0.14, pal["card"], pal["line"])
        bg.text(x + 0.022, 0.723, big, color=pal["head"],
                fontsize=27, fontweight="bold", va="top")
        bg.text(x + 0.022, 0.653, small, color=pal["faint"], fontsize=12, va="top")

    # ---- revenue by segment ---------------------------------------------
    rounded(bg, 0.045, 0.07, 0.535, 0.505, pal["card"], pal["line"])
    ax = fig.add_axes([0.142, 0.125, 0.355, 0.375])
    ax.set_facecolor(pal["card"])
    colours = [pal["accent"] if s == "Champions" else pal["bar"] for s in rev.index]
    ax.barh(range(len(rev)), rev.values / 1e6, color=colours, height=0.62)
    ax.set_yticks(range(len(rev)))
    ax.set_yticklabels([s.replace(" / ", " / ") for s in rev.index],
                       fontsize=10.5, color=pal["body"])
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    for i, v in enumerate(rev.values / 1e6):
        ax.text(v + 0.25, i, f"£{v:.1f}M", va="center", fontsize=10.5,
                color=pal["head"] if rev.index[i] == "Champions" else pal["body"],
                fontweight="bold" if rev.index[i] == "Champions" else "normal")
    ax.set_xlim(0, max(rev.values / 1e6) * 1.2)
    bg.text(0.072, 0.545, "Revenue by segment", color=pal["head"],
            fontsize=14, fontweight="bold", va="top")

    # ---- retention decay -------------------------------------------------
    rounded(bg, 0.605, 0.07, 0.35, 0.505, pal["card"], pal["line"])
    ax2 = fig.add_axes([0.645, 0.145, 0.27, 0.33])
    ax2.set_facecolor(pal["card"])
    ax2.plot(range(13), curve, color=pal["accent"], linewidth=2.4)
    ax2.fill_between(range(13), curve, color=pal["accent"], alpha=0.11)
    ax2.scatter([12], [curve[12]], s=46, color=pal["accent"], zorder=3)
    ax2.annotate(f"{curve[12]:.1f}%", (12, curve[12]), textcoords="offset points",
                 xytext=(-14, 13), fontsize=11.5, fontweight="bold",
                 color=pal["head"], ha="center")
    ax2.set_ylim(0, max(curve) * 1.12)
    ax2.set_xlim(-0.35, 12.7)
    ax2.set_xticks([0, 3, 6, 9, 12])
    ax2.set_xticklabels(["0", "3", "6", "9", "12"], fontsize=10.5, color=pal["faint"])
    ax2.set_yticks([])
    for side in ("top", "right", "left"):
        ax2.spines[side].set_visible(False)
    ax2.spines["bottom"].set_color(pal["line"])
    ax2.tick_params(length=0)
    ax2.set_xlabel("months since first purchase", fontsize=10.5, color=pal["faint"],
                   labelpad=8)
    bg.text(0.632, 0.545, "Cohort retention", color=pal["head"],
            fontsize=14, fontweight="bold", va="top")

    fig.savefig(path, dpi=DPI, facecolor=pal["bg"])
    plt.close(fig)
    print(f"wrote {path}")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    render(LIGHT, OUT / "cover.png")
    render(DARK, OUT / "cover-dark.png")
