"""Reporting tables for 08-results (spec section 5/6) computed only from the accepted run3 CSV files."""
import csv
import statistics as st
from collections import defaultdict
from pathlib import Path

D = Path(__file__).resolve().parent
C = ("C1_cey20", "C2_full", "C2_matched", "C3_pvgis", "C4_nsrdb")
M = ("hours_rh_ge_80", "hours_rh_ge_90", "hours_dewpoint_depression_le_2c")
rd = lambda n: list(csv.DictReader(open(D / n, encoding="utf-8")))
S, A, Mo, Dc = rd("stations.csv"), rd("annual.csv"), rd("monthly.csv"), rd("decomposition.csv")
ref = {r["station_id"]: r for r in S}
ok = [r for r in A if r["status"] == "ok"]
avail = {c: {r["station_id"] for r in ok if r["candidate"] == c} for c in C}
common = set.intersection(*avail.values())
point = {r["station_id"]: r["s10_point"] for r in S}
out = []


def table(title, stations, weight_points=False):
    out.append(f"\n## {title}\n")
    out.append("| Candidate | Exposure | n | within 5 % | 10 % | 20 % | under | median signed rel | median abs rel | mean abs rel |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for c in C:
        for k in M:
            rr = [r for r in ok if r["candidate"] == c and r["metric"] == k and r["station_id"] in stations]
            if weight_points:   # one value per distinct S10 point: mean signed relative difference of its stations, then thresholded
                g = defaultdict(list)
                for r in rr:
                    g[point[r["station_id"]]].append(float(r["rel_error"]))
                rel = [st.mean(v) for v in g.values()]
            else:
                rel = [float(r["rel_error"]) for r in rr]
            a = [abs(x) for x in rel]
            out.append(f"| {c} | {k} | {len(rel)} | {sum(x <= .05 for x in a)} | {sum(x <= .10 for x in a)} | {sum(x <= .20 for x in a)} | "
                       f"{sum(x < 0 for x in rel)} | {st.median(rel):+.3f} | {st.median(a):.3f} | {st.mean(a):.3f} |")


table(f"Annual exposure hours, all available stations (C1/C2: {len(avail['C1_cey20'])}, C3/C4: {len(avail['C3_pvgis'])})", set(ref))
table(f"Annual exposure hours, common subset ({len(common)} stations)", common)
table(f"Annual exposure hours, equal weight per distinct matched S10 point ({len({point[s] for s in common})} points, common subset)", common, True)

out.append(f"\n## Monthly means, common subset ({len(common)} stations, {12 * len(common)} station-months)\n")
out.append("| Candidate | T pass | RH pass | median dT | mean abs dT | median dRH | mean abs dRH | stations all 12 T / RH | worst dT | worst dRH |")
out.append("|---|---|---|---|---|---|---|---|---|---|")
for c in C:
    m = [r for r in Mo if r["candidate"] == c and r["station_id"] in common]
    dt, dr = [float(r["d_t"]) for r in m], [float(r["d_rh"]) for r in m]
    wt, wr = max(m, key=lambda r: abs(float(r["d_t"]))), max(m, key=lambda r: abs(float(r["d_rh"])))
    a12 = lambda q: sum(all(r[q] == "True" for r in m if r["station_id"] == s) for s in common)
    out.append(f"| {c} | {sum(r['pass_t'] == 'True' for r in m)}/{len(m)} | {sum(r['pass_rh'] == 'True' for r in m)}/{len(m)} | {st.median(dt):+.2f} | "
               f"{st.mean(map(abs, dt)):.2f} | {st.median(dr):+.2f} | {st.mean(map(abs, dr)):.2f} | {a12('pass_t')} / {a12('pass_rh')} | "
               f"{float(wt['d_t']):+.2f} ({ref[wt['station_id']]['name']}, m{int(wt['month']):02d}) | {float(wr['d_rh']):+.2f} ({ref[wr['station_id']]['name']}, m{int(wr['month']):02d}) |")

out.append("\n## Monthly failures by direction and median absolute differences, all available stations\n")
out.append("| Candidate | station-months | T fail (too cold / too warm) | RH fail (too dry / too humid) | median abs dT / dRH |")
out.append("|---|---|---|---|---|")
for c in C:
    m = [r for r in Mo if r["candidate"] == c]
    tf = [float(r["d_t"]) for r in m if r["pass_t"] != "True"]
    rf = [float(r["d_rh"]) for r in m if r["pass_rh"] != "True"]
    out.append(f"| {c} | {len(m)} | {len(tf)} ({sum(x < 0 for x in tf)} / {sum(x > 0 for x in tf)}) | {len(rf)} ({sum(x < 0 for x in rf)} / {sum(x > 0 for x in rf)}) | "
               f"{st.median(abs(float(r['d_t'])) for r in m):.2f} / {st.median(abs(float(r['d_rh'])) for r in m):.2f} |")

out.append("\n## Monthly checks, equal weight per distinct S10 point (common subset; mean signed difference of the point's stations, then thresholded)\n")
out.append("| Candidate | point-months | T pass | RH pass |")
out.append("|---|---|---|---|")
for c in C:
    g = defaultdict(list)
    for r in Mo:
        if r["candidate"] == c and r["station_id"] in common:
            g[(point[r["station_id"]], r["month"])].append((float(r["d_t"]), float(r["d_rh"])))
    out.append(f"| {c} | {len(g)} | {sum(abs(st.mean(v[0] for v in x)) <= 0.5 for x in g.values())} | "
               f"{sum(abs(st.mean(v[1] for v in x)) <= 2.0 for x in g.values())} |")

out.append("\n## Annual worst cases (largest absolute relative difference per candidate and exposure)\n")
out.append("| Candidate | Exposure | station | reference h | candidate h | relative |")
out.append("|---|---|---|---|---|---|")
for c in C:
    for k in M:
        w = max((r for r in ok if r["candidate"] == c and r["metric"] == k), key=lambda r: abs(float(r["rel_error"])))
        out.append(f"| {c} | {k} | {ref[w['station_id']]['name']} | {float(w['reference']):.0f} | {float(w['value']):.0f} | {float(w['rel_error']):+.3f} |")

out.append("\n## Annual checks against the missing-data bounds of the station reference (stations within 5 % of the low / primary / high reference)\n")
out.append("| Candidate | RH >= 80 % | RH >= 90 % | T - Td <= 2 °C |")
out.append("|---|---|---|---|")
for c in C:
    cells = []
    for k in M:
        rr = [r for r in ok if r["candidate"] == c and r["metric"] == k]
        n = [sum(abs(float(r["value"]) - float(ref[r["station_id"]][f"ref_{k}{b}"])) <= 0.05 * float(ref[r["station_id"]][f"ref_{k}{b}"]) for r in rr)
             for b in ("_low", "", "_high")]
        cells.append(" / ".join(map(str, n)) + f" (n {len(rr)})")
    out.append(f"| {c} | " + " | ".join(cells) + " |")

out.append("\n## Decomposition C1 - station = (C1 - C2_full) + (C2_full - station), annual hours relative to the station reference\n")
out.append("| Exposure | n | median signed: C1-st / C1-C2 / C2-st | median abs: C1-st / C1-C2 / C2-st | stations with abs(C1-C2) < abs(C2-st) |")
out.append("|---|---|---|---|---|")
for k in M:
    rr = [r for r in Dc if r["statistic"] == k]
    f = lambda col: [float(r[col]) / float(ref[r["station_id"]]["ref_" + k]) for r in rr]
    cols = ("c1_minus_station", "c1_minus_c2full", "c2full_minus_station")
    n = sum(abs(float(r["c1_minus_c2full"])) < abs(float(r["c2full_minus_station"])) for r in rr)
    out.append(f"| {k} | {len(rr)} | " + " / ".join(f"{st.median(f(c)):+.3f}" for c in cols) + " | "
               + " / ".join(f"{st.median(map(abs, f(c))):.3f}" for c in cols) + f" | {n} |")
for q, u in (("mean_t", "°C"), ("mean_rh", "pp")):
    rr = [r for r in Dc if r["statistic"].startswith(q)]
    out.append(f"| monthly {q} ({u}, absolute) | {len(rr)} | " + " / ".join(f"{st.median(float(r[c]) for r in rr):+.2f}" for c in cols) + " | "
               + " / ".join(f"{st.median(abs(float(r[c])) for r in rr):.2f}" for c in cols) + f" | {sum(abs(float(r['c1_minus_c2full'])) < abs(float(r['c2full_minus_station'])) for r in rr)} |")

out.append("\n## Station reference: missing-data bounds and hour-of-day sensitivity (relative to the primary estimate)\n")
out.append("| Exposure | median reference hours (min-max) | bound width median / max | hour-of-day sensitivity median / max |")
out.append("|---|---|---|---|")
for k in M:
    v = [float(ref[s]["ref_" + k]) for s in ref]
    w = [(float(ref[s][f"ref_{k}_high"]) - float(ref[s][f"ref_{k}_low"])) / float(ref[s]["ref_" + k]) for s in ref]
    h = [abs(float(ref[s][f"ref_{k}_sens_hod"]) - float(ref[s]["ref_" + k])) / float(ref[s]["ref_" + k]) for s in ref]
    out.append(f"| {k} | {st.median(v):.0f} ({min(v):.0f}-{max(v):.0f}) | {st.median(w):.3f} / {max(w):.3f} | {st.median(h):.4f} / {max(h):.4f} |")

(D / "report_tables.md").write_text("# 08-results: reporting tables (generated by report_tables.py from run3 CSV files)\n" + "\n".join(out) + "\n", encoding="utf-8")
