"""AUTH-003 S3: predeclared evaluation of the CEY20 selection at the frozen pilot points.

Implements docs/research/auth003-tmy/03-study-protocol.md against the inputs recorded in
03-freeze.json.  Before any outcome is computed it verifies that

* the production builder file is byte-identical to the frozen code commit,
* the study code (this file and auth003_study.py) matches the SHA-256 pin committed before the run,
* every input file matches the frozen inventory (path, size, mtime) and its pre-outcome SHA-256,
* the freeze holds exactly the 14 protocol points, distinct and eligible, and each has 100 %
  valid hours in every candidate month.

Any mismatch aborts; nothing is computed on unverified inputs.

Outputs (all in --output): targets_annual.csv, targets_monthly.csv, loyo.csv,
sensitivity.csv, summary.json, manifest.json.  Held-out hourly diagnostics (joint T/RH
distributions, spells, month-boundary jumps) are a separate step and are NOT produced here.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auth003_study as S  # noqa: E402

BUILDER_REL = "backend/scripts/build_global_cey20_landpoint_dataset.py"
PROTOCOL_POINTS = ("Singapore", "Mumbai", "Dubai", "Houston", "Frankfurt", "London", "Seattle", "San Francisco",
                   "Helsinki", "Fairbanks", "Chicago", "Phoenix", "Denver", "Quito")
PINNED_FILES = {"auth003_study.py": Path(S.__file__).resolve(), "auth003_s3.py": Path(__file__).resolve()}
ANNUAL_REL_TOL = 0.05          # protocol target 1
MONTHLY_T_TOL_C = 0.5          # protocol target 2
MONTHLY_RH_TOL_PCT = 2.0       # protocol target 2
COUNT_KEYS = S.EXPOSURE_FEATURES
BASE_THRESHOLDS = (80.0, 90.0, 2.0)
THRESHOLD_BRACKETS = {
    "rh80": [(78.0, 90.0, 2.0), (82.0, 90.0, 2.0)],
    "rh90": [(80.0, 88.0, 2.0), (80.0, 92.0, 2.0)],
    "dpd2": [(80.0, 90.0, 1.0), (80.0, 90.0, 3.0)],
}
MOISTURE = ("relative_humidity_mean_pct", "relative_humidity_p90_pct", "absolute_humidity_mean_g_m3",
            "dewpoint_depression_p10_c", "hours_rh_ge_80", "hours_rh_ge_90", "hours_dewpoint_depression_le_2c")
THERMAL = ("temperature_mean_c", "temperature_p95_c", "daily_temperature_range_mean_c")


# ----------------------------------------------------------------------------
# verification (before any outcome)
# ----------------------------------------------------------------------------

def verify_code(repo: Path, freeze: dict) -> None:
    frozen = subprocess.run(["git", "show", f"{freeze['code_sha']}:{BUILDER_REL}"], cwd=repo,
                            capture_output=True, check=True).stdout
    current = (repo / BUILDER_REL).read_bytes().replace(b"\r\n", b"\n")
    if frozen.replace(b"\r\n", b"\n") != current:
        raise SystemExit(f"builder differs from frozen commit {freeze['code_sha']}")


def _lf(data: bytes) -> bytes:
    """Line-ending normalisation, so a Windows checkout (autocrlf) hashes like the committed blob."""
    return data.replace(b"\r\n", b"\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_study_code(pin: dict) -> None:
    """auth003_study.py and this runner must match the pin (LF-normalised SHA-256)."""
    for name, path in PINNED_FILES.items():
        digest = hashlib.sha256(_lf(path.read_bytes())).hexdigest()
        if pin.get(name) != digest:
            raise SystemExit(f"{name} does not match the pinned SHA-256")


def verify_input_hashes(sources: dict, hashes: dict, freeze: dict) -> None:
    if hashes.get("freeze_input_inventory_sha256") != freeze["input_inventory_sha256"]:
        raise SystemExit("input hash file belongs to a different freeze")
    by_key = {(r["year"], r["month"]): r["sha256"] for r in hashes["files"]}
    if set(by_key) != set(sources):
        raise SystemExit("input hash file does not cover the frozen inputs")
    for key, src in sorted(sources.items()):
        if sha256_file(src.path) != by_key[key]:
            raise SystemExit(f"input {key} content differs from its pre-outcome SHA-256")


def verify_inputs(sources: dict, freeze: dict) -> None:
    frozen = {(r["year"], r["month"]): r for r in freeze["input_inventory"]}
    if set(frozen) != set(sources):
        raise SystemExit("input set differs from frozen inventory")
    for key, src in sources.items():
        r, st = frozen[key], src.path.stat()
        mtime = dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).isoformat(timespec="seconds")
        if (str(src.path), st.st_size, mtime) != (r["path"], r["bytes"], r["mtime_utc"]) or not r["time_ok"]:
            raise SystemExit(f"input {key} differs from frozen inventory or failed the timestamp check")


def frozen_points(freeze: dict) -> list[dict]:
    names = [p["name"] for p in freeze["points"]]
    if sorted(names) != sorted(PROTOCOL_POINTS) or len(names) != len(PROTOCOL_POINTS):
        raise SystemExit(f"freeze points {names} differ from the 14 protocol points")
    indices = [p["point_index"] for p in freeze["points"]]
    if len(set(indices)) != len(indices):
        raise SystemExit("duplicate point index in freeze")
    bad = [p["name"] for p in freeze["points"] if not p["eligible"]]
    if bad:
        raise SystemExit(f"ineligible points in freeze: {bad}")
    return [{"name": p["name"], "index": p["point_index"]} for p in freeze["points"]]


def require_complete(month: int, res: dict, points: list[dict]) -> None:
    cov = res["coverage"]
    if not np.all(cov >= 1.0):
        p = int(np.argmin(cov.min(axis=0)))
        raise SystemExit(f"month {month}: {points[p]['name']} has valid-hour coverage {cov[:, p].min():.4f} < 1")


# ----------------------------------------------------------------------------
# pure computations on per-month results (unit-tested with synthetic data)
# ----------------------------------------------------------------------------

def counts(t: np.ndarray, td: np.ndarray, thresholds=BASE_THRESHOLDS) -> dict[str, np.ndarray]:
    """Monthly exposure counts (years, points) with the builder's humidity formula."""
    rh80, rh90, dpd = thresholds
    rh = S._relative_humidity_from_dewpoint(t, td).astype(np.float32)
    spread = t - td
    return {"hours_rh_ge_80": np.count_nonzero(rh >= rh80, axis=1).astype(np.float64),
            "hours_rh_ge_90": np.count_nonzero(rh >= rh90, axis=1).astype(np.float64),
            "hours_dewpoint_depression_le_2c": np.count_nonzero(spread <= dpd, axis=1).astype(np.float64)}


def annual_target(sel_counts: dict, all_counts: dict) -> list[dict]:
    """sel_counts[k]: (months, points) counts of the selected years; all_counts[k]: (months, years, points).

    Href = mean of the annual counts over all years; pass = |Hsel-Href|/Href <= 5 %, or Hsel == 0 if Href == 0.
    """
    rows = []
    for k in COUNT_KEYS:
        h_sel = sel_counts[k].sum(axis=0)
        annual = all_counts[k].sum(axis=0)          # (years, points)
        h_ref = annual.mean(axis=0)
        for p in range(h_sel.shape[0]):
            signed = float(h_sel[p] - h_ref[p])
            if h_ref[p] > 0:
                rel = abs(signed) / float(h_ref[p]); ok = rel <= ANNUAL_REL_TOL
            else:
                rel = None; ok = bool(h_sel[p] == 0)
            rows.append({"point": p, "metric": k, "h_selected": float(h_sel[p]), "h_ref": float(h_ref[p]),
                         "signed_h": signed, "abs_h": abs(signed), "rel_error": rel, "pass": ok})
    return rows


def monthly_target(month: int, feats: dict, idx: np.ndarray) -> list[dict]:
    rows = []
    for p in range(idx.shape[0]):
        y = int(idx[p])
        d_t = float(feats["temperature_mean_c"][y, p] - feats["temperature_mean_c"][:, p].mean())
        d_rh = float(feats["relative_humidity_mean_pct"][y, p] - feats["relative_humidity_mean_pct"][:, p].mean())
        rows.append({"point": p, "month": month, "selected_year": S.YEARS[y], "d_temperature_c": d_t,
                     "d_rh_pct": d_rh, "pass_t": abs(d_t) <= MONTHLY_T_TOL_C,
                     "pass_rh": abs(d_rh) <= MONTHLY_RH_TOL_PCT})
    return rows


def select_excluding(feats: dict, held_out: int, weights=None) -> np.ndarray:
    """Selection with one year removed from candidates AND climatology; indices into the full year axis."""
    reduced = {k: np.delete(v, held_out, axis=0) for k, v in feats.items()}
    idx, _, _ = S.select_year(S.score_candidates(reduced, weights))
    return np.where(idx >= held_out, idx + 1, idx)


def take(values: np.ndarray, idx: np.ndarray) -> np.ndarray:
    return values[idx, np.arange(values.shape[1])]


def weight_variants() -> list[tuple[str, dict]]:
    base = dict(S.FEATURE_WEIGHTS)
    out = [(n, w) for n, w in S.weight_variants()]
    for label, f in (("moisture_joint+25%", 1.25), ("moisture_joint-25%", 0.75)):
        out.append((label, {k: v * (f if k in MOISTURE else 1.0) for k, v in base.items()}))
    for label, f in (("thermal_joint+25%", 1.25), ("thermal_joint-25%", 0.75)):
        out.append((label, {k: v * (f if k in THERMAL else 1.0) for k, v in base.items()}))
    out.append(("count_block_ablated", {k: (0.0 if k in COUNT_KEYS else v) for k, v in base.items()}))
    out.append(("count_block_x0.5", {k: (v * 0.5 if k in COUNT_KEYS else v) for k, v in base.items()}))
    return out


# ----------------------------------------------------------------------------
# run
# ----------------------------------------------------------------------------

def run(args) -> int:
    started = dt.datetime.now(dt.timezone.utc)
    repo = Path(args.repo).resolve()
    freeze = json.loads(Path(args.freeze).read_text(encoding="utf-8"))
    verify_study_code(json.loads(Path(args.pin).read_text(encoding="utf-8")))
    verify_code(repo, freeze)
    points = frozen_points(freeze)
    months = list(range(1, 13))
    sources = S.discover_sources(args.extension_root, args.legacy_root, months)
    verify_inputs(sources, freeze)
    verify_input_hashes(sources, json.loads(Path(args.input_hashes).read_text(encoding="utf-8")), freeze)
    if args.verify_only:
        print(json.dumps({"verified": True, "points": len(points), "inputs": len(sources)}))
        return 0
    indices = [p["index"] for p in points]
    n_y, n_p = len(S.YEARS), len(points)

    per_month, monthly_rows = {}, []
    variants = weight_variants() + [("local_interannual_std_scales", None)]
    brackets = [(f"{g}:{th}", th) for g, ths in THRESHOLD_BRACKETS.items() for th in ths]
    for m in months:
        md = S.load_points_month(sources, m, indices)
        res = S.analyse_month(md)                       # asserts production parity
        require_complete(m, res, points)
        t, td = md["temperature_c"], md["dewpoint_c"]
        feats = res["features"]
        entry = {"feats": feats, "idx": res["idx"], "counts": counts(t, td),
                 "loyo": [select_excluding(feats, y) for y in range(n_y)], "variants": {}, "brackets": {}}
        for name, w in variants:
            scales = S.interannual_std(feats) if w is None else None
            idx, _, _ = S.select_year(S.score_candidates(feats, w or S.FEATURE_WEIGHTS, scales))
            entry["variants"][name] = idx
        for name, th in brackets:
            c = counts(t, td, th)
            f2 = dict(feats, **{k: c[k].astype(np.float32) for k in COUNT_KEYS})
            idx, _, _ = S.select_year(S.score_candidates(f2))
            entry["brackets"][name] = (idx, c)
        per_month[m] = entry
        monthly_rows += monthly_target(m, feats, res["idx"])
        print(f"month {m:02d} done", flush=True)

    def stack(key_fn):
        return {k: np.stack([key_fn(per_month[m], k) for m in months]) for k in COUNT_KEYS}

    all_counts = stack(lambda e, k: e["counts"][k])
    annual_rows = annual_target(stack(lambda e, k: take(e["counts"][k], e["idx"])), all_counts)

    loyo_rows = []
    for y in range(n_y):
        sel = stack(lambda e, k: take(e["counts"][k], e["loyo"][y]))
        held = {k: all_counts[k][:, y, :].sum(axis=0) for k in COUNT_KEYS}
        ref19 = {k: np.delete(all_counts[k].sum(axis=0), y, axis=0).mean(axis=0) for k in COUNT_KEYS}
        for p in range(n_p):
            same = sum(int(per_month[m]["loyo"][y][p] == per_month[m]["idx"][p]) for m in months
                       if per_month[m]["idx"][p] != y)
            eligible = sum(1 for m in months if per_month[m]["idx"][p] != y)
            for k in COUNT_KEYS:
                h = float(sel[k].sum(axis=0)[p])
                loyo_rows.append({"held_out_year": S.YEARS[y], "point": points[p]["name"], "metric": k,
                                  "h_selected_19": h, "h_held_out_year": float(held[k][p]),
                                  "h_ref_19": float(ref19[k][p]),
                                  "rel_vs_ref_19": (h - ref19[k][p]) / ref19[k][p] if ref19[k][p] > 0 else None,
                                  "rel_vs_held_out": (h - held[k][p]) / held[k][p] if held[k][p] > 0 else None,
                                  "months_selection_unchanged": same, "months_comparable": eligible})

    sens_rows = []
    for name, _ in variants:
        rows = annual_target(stack(lambda e, k: take(e["counts"][k], e["variants"][name])), all_counts)
        changed = sum(int(np.sum(per_month[m]["variants"][name] != per_month[m]["idx"])) for m in months)
        sens_rows += [dict(r, variant=name, point=points[r["point"]]["name"], point_months_changed=changed) for r in rows]
    for name, _ in brackets:
        bc = {k: np.stack([per_month[m]["brackets"][name][1][k] for m in months]) for k in COUNT_KEYS}
        sel = {k: np.stack([take(per_month[m]["brackets"][name][1][k], per_month[m]["brackets"][name][0])
                            for m in months]) for k in COUNT_KEYS}
        changed = sum(int(np.sum(per_month[m]["brackets"][name][0] != per_month[m]["idx"])) for m in months)
        sens_rows += [dict(r, variant=f"threshold {name}", point=points[r["point"]]["name"], point_months_changed=changed)
                      for r in annual_target(sel, bc)]

    for r in annual_rows:
        r["point"] = points[r["point"]]["name"]
    for r in monthly_rows:
        r["point"] = points[r["point"]]["name"]

    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    S.write_csv(out / "targets_annual.csv", annual_rows)
    S.write_csv(out / "targets_monthly.csv", monthly_rows)
    S.write_csv(out / "loyo.csv", loyo_rows)
    S.write_csv(out / "sensitivity.csv", sens_rows)
    fails_a = [r for r in annual_rows if not r["pass"]]
    fails_t = [r for r in monthly_rows if not r["pass_t"]]
    fails_rh = [r for r in monthly_rows if not r["pass_rh"]]
    summary = {
        "target1_annual": {"checked": len(annual_rows), "failed": len(fails_a),
                           "worst": max(annual_rows, key=lambda r: r["rel_error"] if r["rel_error"] is not None else -1)},
        "target2_monthly_t": {"checked": len(monthly_rows), "failed": len(fails_t),
                              "worst": max(monthly_rows, key=lambda r: abs(r["d_temperature_c"]))},
        "target2_monthly_rh": {"checked": len(monthly_rows), "failed": len(fails_rh),
                               "worst": max(monthly_rows, key=lambda r: abs(r["d_rh_pct"]))},
        "not_produced": "held-out hourly diagnostics (joint T/RH, spells, drying gaps, month-boundary jumps)",
    }
    S.write_json(out / "summary.json", summary)
    S.write_json(out / "manifest.json", {
        "command": "auth003_s3", "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "code_sha": S.git_sha(), "freeze": str(args.freeze), "freeze_code_sha": freeze["code_sha"],
        "freeze_input_inventory_sha256": freeze["input_inventory_sha256"], "points": points,
        "input_hashes": str(args.input_hashes), "pin": str(args.pin),
        "files": ["targets_annual.csv", "targets_monthly.csv", "loyo.csv", "sensitivity.csv", "summary.json"]})
    print(json.dumps({k: {"checked": v["checked"], "failed": v["failed"]} for k, v in summary.items() if isinstance(v, dict)}))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="AUTH-003 S3 predeclared evaluation (frozen protocol).")
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--input-hashes", type=Path, required=True, help="pre-outcome SHA-256 of every input (freeze addendum)")
    p.add_argument("--pin", type=Path, required=True, help="JSON {auth003_study.py: sha256, auth003_s3.py: sha256} committed before the run")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    p.add_argument("--extension-root", type=Path, default=S.builder.DEFAULT_EXTENSION_ROOT)
    p.add_argument("--legacy-root", type=Path, default=S.builder.DEFAULT_LEGACY_ROOT)
    p.add_argument("--verify-only", action="store_true", help="run the pre-outcome checks only")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
