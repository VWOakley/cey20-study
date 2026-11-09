"""AUTH-003 S3 supplementary D4s: month-boundary jumps against an hour-matched 23->00 UTC reference.

Implements section "D4s Supplementary" of docs/research/auth003-tmy/03-diagnostics-spec.md (Codex
review R5). Descriptive only; it does not replace the prespecified D4 of auth003_s3_hourly.py.

Same pre-outcome gates as the hourly runner (code pin incl. this file, builder identity, 14 frozen
points, inventory, content SHA-256, coverage 1.0, selection equal to the S3 run).

Outputs (all in --output): d4s_boundaries.csv, summary.json, manifest.json.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auth003_s3 as R  # noqa: E402
import auth003_s3_hourly as H  # noqa: E402
import auth003_study as S  # noqa: E402

PINNED_FILES = dict(H.PINNED_FILES, **{"auth003_s3_d4s.py": Path(__file__).resolve()})
MIDNIGHTS_EACH_SIDE = 15


def verify_pin(pin: dict) -> None:
    for name, path in PINNED_FILES.items():
        if pin.get(name) != hashlib.sha256(R._lf(path.read_bytes())).hexdigest():
            raise SystemExit(f"{name} does not match the pinned SHA-256")


def _offsets() -> np.ndarray:
    return 24 * np.arange(-MIDNIGHTS_EACH_SIDE, MIDNIGHTS_EACH_SIDE + 1)


def midnight_reference(years_series: np.ndarray, month: int, years) -> np.ndarray:
    """|23->00 UTC changes| on the 31 midnights centred on the boundary after `month` (1..11), all years.

    The Feb->Mar boundary transition of a leap year joins 28 Feb 23:00 to 1 Mar 00:00 because
    29 February was removed; it is not a natural transition and is excluded.
    """
    b = int(np.sum(H.MONTH_HOURS[:month]))
    idx = b + _offsets()
    diffs = np.abs(years_series[:, idx] - years_series[:, idx - 1])
    keep = np.ones(diffs.shape, dtype=bool)
    if month == 2:
        keep[[calendar.isleap(y) for y in years], MIDNIGHTS_EACH_SIDE] = False
    values = diffs[keep]
    return values[np.isfinite(values)]


def midnight_wrap_reference(years_series: np.ndarray) -> np.ndarray:
    """Same 31 midnights across 31 Dec Y -> 1 Jan Y+1 for consecutive year pairs."""
    n_hours = years_series.shape[1]
    idx = n_hours + _offsets()
    out = []
    for y in range(years_series.shape[0] - 1):
        joined = np.concatenate([years_series[y], years_series[y + 1]])
        out.append(np.abs(joined[idx] - joined[idx - 1]))
    values = np.concatenate(out)
    return values[np.isfinite(values)]


def run(args) -> int:
    started = dt.datetime.now(dt.timezone.utc)
    repo = Path(args.repo).resolve()
    freeze = json.loads(Path(args.freeze).read_text(encoding="utf-8"))
    pin = json.loads(Path(args.pin).read_text(encoding="utf-8"))
    verify_pin(pin)
    H.verify_s3_selection_file(Path(args.s3_monthly), pin)
    R.verify_code(repo, freeze)
    points = R.frozen_points(freeze)
    months = list(range(1, 13))
    sources = S.discover_sources(args.extension_root, args.legacy_root, months)
    R.verify_inputs(sources, freeze)
    R.verify_input_hashes(sources, json.loads(Path(args.input_hashes).read_text(encoding="utf-8")), freeze)
    s3_idx = H.read_s3_selection(Path(args.s3_monthly), points)
    if args.verify_only:
        print(json.dumps({"verified_without_selection_check": True, "points": len(points), "inputs": len(sources)}))
        return 0
    indices = [p["index"] for p in points]

    t_months, td_months, idx = [], [], np.zeros((12, len(points)), dtype=np.int16)
    for m in months:
        md = S.load_points_month(sources, m, indices)
        res = S.analyse_month(md)                       # asserts production parity
        R.require_complete(m, res, points)
        if not np.array_equal(res["idx"], s3_idx[m - 1]):
            raise SystemExit(f"month {m}: selection differs from the S3 run")
        idx[m - 1] = res["idx"]
        t_months.append(md["temperature_c"]); td_months.append(md["dewpoint_c"])
        print(f"month {m:02d} loaded", flush=True)

    years_t = np.concatenate(t_months, axis=1)          # (years, 8760, points)
    years_td = np.concatenate(td_months, axis=1)
    years_rh = H.rh_of(years_t, years_td)
    cey_t, cey_td = H.assemble(t_months, idx), H.assemble(td_months, idx)
    cey_rh = H.rh_of(cey_t, cey_td)
    if years_t.shape[0] != len(S.YEARS):
        raise SystemExit("year axis does not match S.YEARS")

    rows = []
    for p, pt in enumerate(points):
        series = {"temperature_c": (cey_t[:, p], years_t[:, :, p]),
                  "dewpoint_c": (cey_td[:, p], years_td[:, :, p]),
                  "rh_pct": (cey_rh[:, p], years_rh[:, :, p])}
        for m in months:
            same = bool(idx[m - 1, p] == idx[m % 12, p]) and m < 12
            for var, (cs_, ys_) in series.items():
                if m < 12:
                    jump, ref = H.boundary_jump(cs_, m), midnight_reference(ys_, m, S.YEARS)
                else:
                    jump, ref = float(abs(cs_[0] - cs_[-1])), midnight_wrap_reference(ys_)
                p99 = float(np.percentile(ref, 99))
                rows.append({"point": pt["name"], "boundary": f"{m:02d}->{m % 12 + 1:02d}", "wrap": m == 12,
                             "variable": var, "jump": jump, "percentile": H.percentile_of(jump, ref),
                             "ref_p99": p99, "ref_n": int(ref.size), "above_ref_p99": jump > p99,
                             "same_year": same, "year_before": S.YEARS[idx[m - 1, p]],
                             "year_after": S.YEARS[idx[m % 12, p]]})

    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    S.write_csv(out / "d4s_boundaries.csv", rows)
    variables = ("temperature_c", "dewpoint_c", "rh_pct")
    inner = [r for r in rows if not r["wrap"]]
    summary = {
        "label": "supplementary to D4 (Codex R5); descriptive, no null model",
        "d4s_inner_above_ref_p99": {v: sum(r["above_ref_p99"] for r in inner if r["variable"] == v) for v in variables},
        "d4s_inner_checked_per_variable": len(inner) // len(variables),
        "d4s_wrap_above_ref_p99": {v: sum(r["above_ref_p99"] for r in rows if r["wrap"] and r["variable"] == v)
                                   for v in variables},
        "ref_n_min": min(r["ref_n"] for r in rows), "ref_n_max": max(r["ref_n"] for r in rows),
    }
    S.write_json(out / "summary.json", summary)
    S.write_json(out / "manifest.json", {
        "command": "auth003_s3_d4s", "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "code_sha": S.git_sha(), "freeze": str(args.freeze), "freeze_code_sha": freeze["code_sha"],
        "freeze_input_inventory_sha256": freeze["input_inventory_sha256"], "points": points,
        "input_hashes": str(args.input_hashes), "pin": str(args.pin), "s3_monthly": str(args.s3_monthly),
        "files": ["d4s_boundaries.csv", "summary.json"]})
    print(json.dumps(summary))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="AUTH-003 S3 supplementary D4s (03-diagnostics-spec.md).")
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--input-hashes", type=Path, required=True)
    p.add_argument("--pin", type=Path, required=True,
                   help="JSON with SHA-256 of the study/S3/hourly/D4s scripts and s3_targets_monthly.csv")
    p.add_argument("--s3-monthly", type=Path, required=True, help="targets_monthly.csv of the S3 run (selection cross-check)")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    p.add_argument("--extension-root", type=Path, default=S.builder.DEFAULT_EXTENSION_ROOT)
    p.add_argument("--legacy-root", type=Path, default=S.builder.DEFAULT_LEGACY_ROOT)
    p.add_argument("--verify-only", action="store_true")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
