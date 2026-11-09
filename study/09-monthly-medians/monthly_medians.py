"""Exploratory, post hoc: selected annual exposure counts against the sum of the 12 monthly medians (14 S3 points).

Not part of the frozen S3 protocol; changes no result. Uses the S3 study code (research/AUTH-003-S10-california,
auth003_study / auth003_s3) on the frozen inputs of 03-freeze.json: the same feature definitions, the same selection
(analyse_month, with its builder parity check) and the frozen 14 points. For each point, metric and month it takes
the 20 per-year monthly counts and reports, summed over the 12 months: the selected-year count (must equal
h_selected of 03-results/targets_annual.csv), the 20-year mean (must equal h_ref) and the sum of the monthly medians.

Usage: python -B monthly_medians.py <path to climetry-auth003-s10/backend/scripts/research>
Writes monthly_medians.csv next to this script; reads E: only.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parent
sys.path.insert(0, sys.argv[1])
import auth003_s3 as R  # noqa: E402
import auth003_study as S  # noqa: E402

METRICS = S.EXPOSURE_FEATURES


def main():
    freeze = json.loads((D.parent / "03-freeze.json").read_text(encoding="utf-8"))
    points = R.frozen_points(freeze)
    sources = S.discover_sources(S.builder.DEFAULT_EXTENSION_ROOT, S.builder.DEFAULT_LEGACY_ROOT, list(range(1, 13)))
    R.verify_inputs(sources, freeze)
    n = len(points)
    selected, mean, med_sum = ({k: np.zeros(n) for k in METRICS} for _ in range(3))
    monthly = []
    for m in range(1, 13):
        res = S.analyse_month(S.load_points_month(sources, m, [p["index"] for p in points]))
        if (res["idx"] < 0).any():
            raise SystemExit(f"month {m}: a point has no selected year")
        for k in METRICS:
            f = np.asarray(res["features"][k], np.float64)        # (years, points)
            if not np.isfinite(f).all():
                raise SystemExit(f"month {m} {k}: non-finite counts")
            sel = f[res["idx"], np.arange(n)]
            selected[k] += sel
            mean[k] += f.mean(axis=0)
            med_sum[k] += np.median(f, axis=0)
            monthly += [{"point": p["name"], "metric": k, "month": m, "selected": sel[i], "mean": f[:, i].mean(),
                         "median": float(np.median(f[:, i])), "zero_years": int((f[:, i] == 0).sum())}
                        for i, p in enumerate(points)]
        print(f"month {m:02d} done", flush=True)
    targets = {(r["point"], r["metric"]): r for r in csv.DictReader(open(D.parent / "03-results/targets_annual.csv", encoding="utf-8"))}
    rows = []
    for k in METRICS:
        for i, p in enumerate(points):
            t = targets[(p["name"], k)]
            if abs(selected[k][i] - float(t["h_selected"])) > 1e-6 or abs(mean[k][i] - float(t["h_ref"])) > 0.051:
                raise SystemExit(f"{p['name']} {k}: recomputed counts differ from targets_annual.csv")
            rows.append({"point": p["name"], "metric": k, "pass_s3": t["pass"], "h_selected": selected[k][i],
                         "h_mean": round(mean[k][i], 2), "sum_monthly_medians": med_sum[k][i],
                         "rel_selected_vs_mean": round(selected[k][i] / mean[k][i] - 1, 4),
                         "rel_selected_vs_sum_medians": round(selected[k][i] / med_sum[k][i] - 1, 4) if med_sum[k][i] else "",
                         "rel_sum_medians_vs_mean": round(med_sum[k][i] / mean[k][i] - 1, 4)})
    for name, data in (("monthly_medians.csv", rows), ("monthly_medians_by_month.csv", monthly)):
        with open(D / name, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, list(data[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(data)


if __name__ == "__main__":
    main()
