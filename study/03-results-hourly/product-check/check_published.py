"""Read-only check of month-boundary jumps in the published CEY20 hourly product (E:/ERA_DATA/cey_2006_2025/hourly).

For every land point and the 11 inner boundaries plus the Dec->Jan wrap: |dT| and |dTd| between the last hour
of month m and the first hour of month m+1. Natural comparison inside the same file (same source year):
the 22->23 UTC step of the last day and the 00->01 UTC step of the first day.
Also compares the 14 AUTH-003 points with the study's d4_boundaries.csv."""
import csv, json, sys
from pathlib import Path
import netCDF4, numpy as np

ROOT = Path(r"E:/ERA_DATA/cey_2006_2025/hourly")
STUDY = Path(sys.argv[1]); FREEZE = Path(sys.argv[2]); OUT = Path(sys.argv[3])
first, second, last, prev = {}, {}, {}, {}
for m in range(1, 13):
    with netCDF4.Dataset(ROOT / f"cey20_landpoints_month{m:02d}.nc") as d:
        for v in ("temperature_c", "dewpoint_c"):
            x = d.variables[v]
            first[m, v], second[m, v] = np.asarray(x[0, :], np.float64), np.asarray(x[1, :], np.float64)
            prev[m, v], last[m, v] = np.asarray(x[-2, :], np.float64), np.asarray(x[-1, :], np.float64)
res = {}
for v in ("temperature_c", "dewpoint_c"):
    join = np.stack([np.abs(first[m % 12 + 1, v] - last[m, v]) for m in range(1, 12)])
    wrap = np.abs(first[1, v] - last[12, v])
    natural = np.concatenate([np.abs(last[m, v] - prev[m, v]) for m in range(1, 13)] +
                             [np.abs(second[m, v] - first[m, v]) for m in range(1, 13)])
    p99 = float(np.nanpercentile(natural, 99))
    res[v] = {"inner_joins": int(np.isfinite(join).sum()), "natural_steps": int(np.isfinite(natural).sum()),
              "natural_p99": p99, "natural_p999": float(np.nanpercentile(natural, 99.9)),
              "join_median": float(np.nanmedian(join)), "natural_median": float(np.nanmedian(natural)),
              "join_share_above_natural_p99": float(np.nanmean(join > p99)),
              "join_share_above_5c": float(np.nanmean(join > 5)), "natural_share_above_5c": float(np.nanmean(natural > 5)),
              "join_share_above_10c": float(np.nanmean(join > 10)), "natural_share_above_10c": float(np.nanmean(natural > 10)),
              "join_max": float(np.nanmax(join)), "wrap_share_above_natural_p99": float(np.nanmean(wrap > p99))}
# 14 study points: published product vs study recomputation
freeze = json.loads(FREEZE.read_text())
idx = {p["name"]: p["point_index"] for p in freeze["points"]}
study = list(csv.DictReader(open(STUDY, encoding="utf-8")))
diffs = []
for r in study:
    if r["variable"] not in ("temperature_c", "dewpoint_c"):
        continue
    m = int(r["boundary"][:2]); i = idx[r["point"]]; v = r["variable"]
    pub = abs(first[m % 12 + 1, v][i] - last[m, v][i])
    diffs.append(abs(pub - float(r["jump"])))
res["study_points_match"] = {"compared": len(diffs), "max_abs_diff": float(max(diffs))}
OUT.write_text(json.dumps(res, indent=2)); print(json.dumps(res, indent=2))
