"""AUTH-003 S6 figures from the amendment V2 run-1 outputs (descriptive; no recomputation of results).

Usage: python -B make_v2_figures.py <run1 dir with a1_curves.csv> <12-results-v2 dir> <outdir>
Writes fig_v2_duration_curves, fig_v2_regional_<quantity> (same layout as make_s5_figures.py, version-2 rows) and
fig_v2_month_interfaces ({pdf,png}).
"""
import csv
import random
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_s5_figures as S5  # noqa: E402

V1 = S5.INK2                # unsmoothed version 1 in recessive grey
V2 = S5.CEY20               # released version 2 in categorical slot 1
VARIABLES = {"temperature_c": "T", "dewpoint_c": "Td", "rh_pct": "RH", "surface_pressure_pa": "Surface pressure"}


def rename(src: Path, dst: Path, stem_old: str, stem_new: str) -> None:
    for ext in ("pdf", "png"):
        (src / f"{stem_old}.{ext}").replace(dst / f"{stem_new}.{ext}")


def v2_duration_curves(run_dir: Path, out: Path) -> None:
    """Version-2 rows of a1_curves.csv through the unchanged S5 plotting function."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        sub = tmp / "a1_curves_v2.csv"
        n = 0
        with (run_dir / "a1_curves.csv").open(encoding="utf-8") as f, sub.open("w", encoding="utf-8", newline="") as g:
            r = csv.DictReader(f)
            w = csv.DictWriter(g, fieldnames=r.fieldnames)
            w.writeheader()
            for row in r:
                if row["version"] == "v2":
                    w.writerow(row)
                    n += 1
        if n != 14 * 8760:
            raise SystemExit(f"a1_curves.csv: {n} version-2 rows, expected {14 * 8760}")
        S5.duration_curves(sub, tmp)
        rename(tmp, out, "fig_s5_duration_curves", "fig_v2_duration_curves")


def v2_regional(results: Path, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        S5.regional(results / "regional_envelopes_v2.csv", tmp)
        for q in S5.QUANTITIES:
            rename(tmp, out, f"fig_s5_regional_{q}", f"fig_v2_regional_{q}")


def month_interfaces(results: Path, out: Path) -> None:
    """Paired J_b and M_b at all evaluated boundaries, as ratio to the boundary's reference p99 (log scale)."""
    rows = []
    with (results / "d4_boundaries.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["same_year"] == "True" and r["wrap"] == "False":
                continue                                  # same-source-year inner boundaries: unchanged by construction
            rows.append(r)
    groups = [("J_b", "v1", "Step\nv1", V1), ("J_b", "v2", "Step\nv2", V2),
              ("M_b", "v1", "Max\nv1", V1), ("M_b", "v2", "Max\nv2", V2)]
    fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.9), sharey=True)
    rng = random.Random(0)                                # fixed jitter, reproducible figure
    for ax, (var, label) in zip(axes, VARIABLES.items()):
        sel = [r for r in rows if r["variable"] == var]
        ticks = []
        for i, (stat, ver, name, colour) in enumerate(groups):
            vals = [max(float(r[stat]) / float(r["ref_p99"]), 1e-3) for r in sel if r["version"] == ver]
            xs = [i + rng.uniform(-0.28, 0.28) for _ in vals]
            ax.scatter(xs, vals, s=4, color=colour, alpha=0.55, linewidths=0)
            above = sum(v > 1 for v in vals)
            ticks.append(f"{name}\n{above}/{len(vals)}")
        ax.axhline(1.0, color=S5.INK, linewidth=0.8, linestyle="--")
        ax.set_yscale("log")
        ax.set_ylim(1e-3, 50)
        ax.set_xlim(-0.6, 3.6)
        ax.set_xticks(range(4), ticks, fontsize=6)
        ax.set_title(label, fontsize=8, color=S5.INK, loc="left")
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Change / reference 99th percentile")
    fig.text(0.01, -0.06, "Step: change at the boundary hour (J_b). Max: largest change within the 12-hour window "
             "(M_b). v1 unsmoothed, v2 released. Dashed line: reference 99th percentile.\nCounts below the labels: "
             "boundaries above it, of 150 cross-year inner boundaries and 14 December–January wraps. Values below "
             "0.001 are drawn at 0.001.", fontsize=6, color=S5.INK2)
    fig.tight_layout()
    S5.save(fig, out, "fig_v2_month_interfaces")


if __name__ == "__main__":
    run_dir, results, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    v2_duration_curves(run_dir, out)
    v2_regional(results, out)
    month_interfaces(results, out)
