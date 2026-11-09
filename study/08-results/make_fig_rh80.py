"""Figure for spec section 11: signed annual RH >= 80 % hour differences (candidate - station) per station and candidate.

Reads the accepted run3 CSV files next to this script; writes fig_s4ext_rh80.{pdf,png}.
"""
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

D = Path(__file__).resolve().parent
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SERIES = [("C1_cey20", "CEY20 v2 (C1)", "#2a78d6", "o"), ("C2_full", "ERA5-Land 20-year climatology (C2)", "#eb6834", "s"),
          ("C3_pvgis", "PVGIS-TMY 5.3 (C3)", "#1baf7a", "^"), ("C4_nsrdb", "NSRDB GOES TMY v4 (C4)", "#eda100", "D")]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "savefig.dpi": 300})
stations = list(csv.DictReader(open(D / "stations.csv", encoding="utf-8")))
stations.sort(key=lambda r: float(r["ref_hours_rh_ge_80"]))
rows = {(r["station_id"], r["candidate"]): float(r["signed"]) for r in csv.DictReader(open(D / "annual.csv", encoding="utf-8"))
        if r["status"] == "ok" and r["metric"] == "hours_rh_ge_80"}
fig, ax = plt.subplots(figsize=(7.2, 7.4))
ax.grid(axis="x", color=GRID, linewidth=0.5)
ax.axvline(0, color=INK2, linewidth=0.8)
for i, st in enumerate(stations):
    ref = float(st["ref_hours_rh_ge_80"])
    ax.axvspan(-0.05 * ref, 0.05 * ref, ymin=(i + 0.1) / len(stations), ymax=(i + 0.9) / len(stations), color=GRID, linewidth=0)
for j, (key, label, color, marker) in enumerate(SERIES):
    ys = [i + (j - 1.5) * 0.17 for i, st in enumerate(stations) if (st["station_id"], key) in rows]
    xs = [rows[(st["station_id"], key)] for st in stations if (st["station_id"], key) in rows]
    ax.scatter(xs, ys, s=14, color=color, marker=marker, edgecolors="white", linewidths=0.4, label=label, zorder=3)
ax.set_yticks(range(len(stations)))
ax.set_yticklabels([f"{s['name'].replace(' Airport', '').replace(' Municipal', '')} ({float(s['ref_hours_rh_ge_80']):.0f} h)" for s in stations])
ax.set_ylim(-0.7, len(stations) - 0.3)
ax.set_xlabel("Annual hours with RH ≥ 80 %: candidate − station reference (h)")
ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.02), ncol=2, frameon=False, fontsize=7)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(D / f"fig_s4ext_rh80.{ext}", bbox_inches="tight")
