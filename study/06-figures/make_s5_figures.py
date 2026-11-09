"""AUTH-003 S6 figures from the S5 run-1 outputs (descriptive; no recomputation of results).

Usage: python -B make_s5_figures.py <a1_curves.csv> <regional_envelopes.csv> <outdir>
Writes fig_s5_duration_curves.{pdf,png} and fig_s5_regional_<quantity>.{pdf,png}.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
CEY20 = "#2a78d6"          # categorical slot 1
BAND = "#c9daf0"           # light step of the same hue, actual-year band
POINTS = ["Singapore", "Mumbai", "Dubai", "Houston", "Frankfurt", "London", "Seattle", "San Francisco",
          "Helsinki", "Fairbanks", "Chicago", "Phoenix", "Denver", "Quito"]
REGIONS = ["Singapore", "Dubai", "Houston", "Frankfurt", "Helsinki", "Fairbanks", "Iqaluit"]
QUANTITIES = {"mean_t_c": "Monthly mean T (°C)", "mean_rh_pct": "Monthly mean RH (%)",
              "hours_rh_ge_80": "Hours with RH ≥ 80 % per month"}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "savefig.dpi": 300})


def save(fig, out: Path, name: str) -> None:
    for ext in ("pdf", "png"):
        fig.savefig(out / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)


def duration_curves(path: Path, out: Path) -> None:
    curves = defaultdict(lambda: defaultdict(list))
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            c = curves[r["point"]]
            for k in ("exceedance", "cey20_c", "pooled_c", "years_min_c", "years_max_c"):
                c[k].append(float(r[k]))
    fig, axes = plt.subplots(4, 4, figsize=(7.2, 7.6), sharex=True)
    for ax, name in zip(axes.flat, POINTS):
        c = curves[name]
        x = [100 * e for e in c["exceedance"]]
        ax.fill_between(x, c["years_min_c"], c["years_max_c"], color=BAND, linewidth=0, label="Range of 20 actual years")
        ax.plot(x, c["pooled_c"], color=INK2, linewidth=1.0, label="Pooled 2006–2025")
        ax.plot(x, c["cey20_c"], color=CEY20, linewidth=1.2, label="CEY20")
        ax.set_title(name, fontsize=8, color=INK, loc="left")
        ax.set_xlim(0, 100)
    for ax in axes.flat[len(POINTS):]:
        ax.axis("off")
    for ax in axes[-1]:
        ax.set_xlabel("Exceedance (% of hours)")
    for ax in axes[:, 0]:
        ax.set_ylabel("T (°C)")
    for ax in (axes[2, 2], axes[2, 3]):                 # bottom panels of the two short columns
        ax.tick_params(labelbottom=True)
        ax.set_xlabel("Exceedance (% of hours)")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower right", bbox_to_anchor=(0.97, 0.08), frameon=False)
    fig.tight_layout()
    save(fig, out, "fig_s5_duration_curves")


def regional(path: Path, out: Path) -> None:
    rows = defaultdict(dict)
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[(r["region"], r["quantity"])][int(r["month"])] = r
    months = list(range(1, 13))
    for q, label in QUANTITIES.items():
        fig, axes = plt.subplots(2, 4, figsize=(7.2, 3.8), sharex=True)
        for ax, region in zip(axes.flat, REGIONS):
            m = rows[(region, q)]
            g = lambda key: [float(m[i][key]) for i in months]  # noqa: E731
            ax.fill_between(months, g("p10"), g("p90"), color=BAND, linewidth=0, label="Box points, 10th–90th pct.")
            ax.plot(months, g("p50"), color=CEY20, linewidth=1.2, marker="o", markersize=2.5, label="Box points, median")
            lo, med, hi = g("centre_years_min"), g("centre_years_median"), g("centre_years_max")
            ax.errorbar([x + 0.25 for x in months], med, yerr=[[a - b for a, b in zip(med, lo)], [b - a for a, b in zip(med, hi)]],
                        fmt="none", ecolor=INK2, elinewidth=0.8, capsize=0, label="Centre, range of 20 actual years")
            ax.set_title(f"{region} ({m[1]['n_points']} points)", fontsize=8, color=INK, loc="left")
            ax.set_xticks([1, 4, 7, 10], ["Jan", "Apr", "Jul", "Oct"])
        axes.flat[-1].axis("off")
        for ax in axes[:, 0]:
            ax.set_ylabel(label, fontsize=7)
        handles, labels = axes.flat[0].get_legend_handles_labels()
        axes.flat[-1].legend(handles, labels, loc="center", frameon=False, fontsize=7)
        fig.tight_layout()
        save(fig, out, f"fig_s5_regional_{q}")


if __name__ == "__main__":
    out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
    duration_curves(Path(sys.argv[1]), out)
    regional(Path(sys.argv[2]), out)
