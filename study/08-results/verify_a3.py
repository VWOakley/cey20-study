"""Amendment A3 acceptance check: run2 vs run1 (see 08-amendment-A3.md)."""
import csv, json, statistics as st, sys
from pathlib import Path
B = Path("E:/40_work/AUTH-003_external-comparison/results")
r1, r2 = B / "run1", B / (sys.argv[1] if len(sys.argv) > 1 else "run3")
C = ("C1_cey20", "C2_full", "C2_matched", "C3_pvgis", "C4_nsrdb")
M = ("hours_rh_ge_80", "hours_rh_ge_90", "hours_dewpoint_depression_le_2c")
ok = True
def check(cond, msg):
    global ok
    print(("PASS " if cond else "FAIL ") + msg); ok &= bool(cond)
for n in ("stations.csv", "monthly.csv", "decomposition.csv", "conventions.csv"):
    check((r1 / n).read_bytes() == (r2 / n).read_bytes(), f"{n} byte-identical")
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))
a1, a2 = rd(r1 / "annual.csv"), rd(r2 / "annual.csv")
stations = [r["station_id"] for r in rd(r1 / "stations.csv")]
labels, i = [], 0
for s in stations:
    for c in C:
        if a1[i]["status"] == "unavailable":
            labels.append(c); i += 1
        else:
            labels += [c] * 3; i += 3
check(i == len(a1) == len(a2), f"annual row count {len(a1)} / {len(a2)}")
same = all(x["station_id"] == y["station_id"] and l == y["candidate"] and x["status"] == y["status"]
           and all(x.get(k, "") == y.get(k, "") for k in ("metric", "reference", "signed", "rel_error", "pass"))
           and (x["status"] == "unavailable" or x["candidate"] == y["value"]) for x, y, l in zip(a1, a2, labels))
check(same, "annual.csv: values identical to run1, labels equal reconstructed order, run1 candidate == run2 value")
s1, s2 = json.loads((r1 / "summary.json").read_text()), json.loads((r2 / "summary.json").read_text())
mon = ("monthly_t_pass", "monthly_rh_pass", "monthly_median_abs_d_t", "monthly_median_abs_d_rh")
for c in C:
    check(all(s1[c][k] == s2[c][k] for k in mon), f"{c} monthly summary equals run1")
    rows = [r for r in a2 if r["candidate"] == c and r["status"] == "ok"]
    sok = {r["station_id"] for r in rows}
    exp = {"stations_available": len(sok),
           "annual_pass": {k: [sum(r["pass"] == "True" for r in rows if r["metric"] == k), sum(r["metric"] == k for r in rows)] for k in M},
           "annual_under": {k: sum(float(r["signed"]) < 0 for r in rows if r["metric"] == k) for k in M},
           "annual_median_rel_error": {k: st.median(float(r["rel_error"]) for r in rows if r["metric"] == k and r["rel_error"] != "") for k in M}}
    got = {k: s2[c][k] for k in exp}
    close = all(abs(got["annual_median_rel_error"][k] - exp["annual_median_rel_error"][k]) < 1e-12 for k in M)
    check({k: v for k, v in got.items() if k != "annual_median_rel_error"} == {k: v for k, v in exp.items() if k != "annual_median_rel_error"} and close,
          f"{c} annual summary recomputed from annual.csv ({exp['stations_available']} stations)")
print("ACCEPT" if ok else "REJECT"); sys.exit(0 if ok else 1)
