"""BUG-018: month-interface smoothing of the CEY20 hourly landpoint product (new product version).

Implements docs/qa/cey/BUG-018-smoothing-spec.md (revision 4, Codex approve). The 12 monthly files of the
existing product are copied byte-for-byte to a new output root; then only the last 6 hours of each month
and the first 6 hours of the following month (Dec->Jan included) are rewritten where a boundary is eligible.
All corrections are computed from the immutable input windows.

  python scripts/smooth_cey20_month_interfaces.py --input-root E:/ERA_DATA/cey_2006_2025/hourly \
      --input-manifest E:/ERA_DATA/cey_2006_2025/hourly_manifest.json \
      --output-root E:/ERA_DATA/cey_2006_2025_v2/hourly --manifest E:/ERA_DATA/cey_2006_2025_v2/hourly_manifest.json
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import netCDF4
import numpy as np

N = 6                                   # hours on each side (NREL TMY3, Wilcox & Marion 2008, sec. 2.6)
W = 2 * N + 2                           # window x[b-7] .. x[b+6]
B = N + 1                               # window index of x[b]
VARS = ("temperature_c", "dewpoint_c", "surface_pressure_pa")
METHOD = "CEY excess-step linear ramp (NREL-inspired)"
SOURCE = "Wilcox & Marion 2008, NREL/TP-581-43156, sec. 2.6"


def weights(n: int = N) -> np.ndarray:
    """w_k = (n + 1 - k) / n for k = 1..n (w_1 = 1, w_n = 1/n)."""
    return (n + 1 - np.arange(1, n + 1)) / n


def excess(window: np.ndarray, expected_step: bool = True) -> np.ndarray:
    """E = J - s per point; window (W, points), s = mean of the two adjacent within-month steps (or 0)."""
    jump = window[B] - window[B - 1]
    if not expected_step:
        return jump
    return jump - 0.5 * ((window[B - 1] - window[B - 2]) + (window[B + 1] - window[B]))


def ramp(window: np.ndarray, expected_step: bool = True) -> np.ndarray:
    """Delivered method; returns a new float64 window, rows B-N .. B+N-1 modified, rows 0 and W-1 unchanged."""
    x = np.asarray(window, dtype=np.float64)
    e = excess(x, expected_step)
    out = x.copy()
    for k, w in enumerate(weights(), start=1):
        out[B - k] += 0.5 * e * w
        out[B - 1 + k] -= 0.5 * e * w
    return out


def straight_line(window: np.ndarray) -> np.ndarray:
    """Comparator (not delivered): rows 1..W-2 replaced by the line between rows 0 and W-1."""
    x = np.asarray(window, dtype=np.float64)
    frac = (np.arange(W) / (W - 1))[:, None]
    out = x[0] + (x[-1] - x[0]) * frac
    out[0], out[-1] = x[0], x[-1]
    return out


def consecutive(month: int, year_before: np.ndarray, year_after: np.ndarray) -> np.ndarray:
    """True where the last hour of `month` and the first hour of the next month are consecutive source hours."""
    year_before = np.asarray(year_before)
    if month == 12:
        return np.zeros(year_before.shape, dtype=bool)          # Dec -> Jan is never consecutive
    same = year_before == np.asarray(year_after)
    if month == 2:
        leap = np.vectorize(calendar.isleap)(year_before) if year_before.size else np.zeros(0, bool)
        same &= ~leap                                           # 29 Feb removed from the product
    return same


def eligibility(windows: dict[str, np.ndarray], month: int, year_before, year_after, method=ramp) -> dict:
    """Per-point masks for one boundary: consecutive, T/Td-eligible, pressure finite, pressure positivity skip,
    pressure eligible. T and Td share one mask; pressure must stay finite and > 0 after smoothing."""
    t, td, p = (np.asarray(windows[v], dtype=np.float32) for v in VARS)
    cons = consecutive(month, year_before, year_after)
    ok_th = ~cons & np.all(np.isfinite(t), axis=0) & np.all(np.isfinite(td), axis=0)
    p_finite = ~cons & np.all(np.isfinite(p), axis=0)
    p_bad = np.zeros_like(p_finite)
    if p_finite.any():
        sm = method(p[:, p_finite]).astype(np.float32)[1: W - 1]
        p_bad[p_finite] = ~np.all(np.isfinite(sm) & (sm > 0), axis=0)
    return {"consecutive": cons, "t_td": ok_th, "pressure_finite": p_finite, "pressure_positivity_skip": p_bad,
            "pressure": p_finite & ~p_bad}


def smooth_boundary(windows: dict[str, np.ndarray], month: int, year_before, year_after,
                    method=ramp) -> tuple[dict[str, np.ndarray], dict]:
    """Smoothed windows (float32, same shape) and counts for one boundary over all points.

    T and Td share one eligibility mask (all window values finite in both, boundary not consecutive);
    pressure is eligible on its own. Td is clipped to T only in modified, T/Td-eligible hours.
    """
    e = eligibility(windows, month, year_before, year_after, method)
    cons, ok_th, ok_p, p_bad = e["consecutive"], e["t_td"], e["pressure"], e["pressure_positivity_skip"]
    ok_p_finite = e["pressure_finite"]
    t = np.asarray(windows["temperature_c"])
    out = {v: np.asarray(windows[v], dtype=np.float32).copy() for v in VARS}
    rows = slice(1, W - 1)
    for v, ok in (("temperature_c", ok_th), ("dewpoint_c", ok_th), ("surface_pressure_pa", ok_p)):
        if ok.any():
            sm = method(np.asarray(windows[v])[:, ok]).astype(np.float32)
            out[v][rows, ok] = sm[rows]
    clip_mask = np.zeros_like(out["dewpoint_c"], dtype=bool)
    clip_mask[rows] = ok_th & (out["dewpoint_c"][rows] > out["temperature_c"][rows])
    clip_mag = np.where(clip_mask, out["dewpoint_c"] - out["temperature_c"], 0.0)
    out["dewpoint_c"] = np.where(clip_mask, out["temperature_c"], out["dewpoint_c"])
    counts = {
        "points": int(t.shape[1]),
        "consecutive_skipped": int(cons.sum()),
        "nonfinite_skipped_t_td": int((~cons & ~ok_th).sum()),
        "nonfinite_skipped_pressure": int((~cons & ~ok_p_finite).sum()),
        "smoothed_t_td": int(ok_th.sum()),
        "smoothed_pressure": int(ok_p.sum()),
        "clipped_hours": int(clip_mask.sum()),
        "clipped_points": int(clip_mask.any(axis=0).sum()),
        "clip_max_c": float(clip_mag.max()) if clip_mask.any() else 0.0,
        "pressure_positivity_skipped": int(p_bad.sum()),
    }
    return out, counts


# ----------------------------------------------------------------------------
# product I/O
# ----------------------------------------------------------------------------

def month_file(root: Path, month: int) -> Path:
    return root / f"cey20_landpoints_month{month:02d}.nc"


def read_edges(path: Path) -> tuple[dict, dict, np.ndarray]:
    """First and last N+1 hours of every variable, plus selected_source_year."""
    with netCDF4.Dataset(path) as ds:
        head = {v: np.asarray(ds.variables[v][: N + 1, :], dtype=np.float32) for v in VARS}
        tail = {v: np.asarray(ds.variables[v][-(N + 1):, :], dtype=np.float32) for v in VARS}
        years = np.asarray(ds.variables["selected_source_year"][:], dtype=np.int32)
    return head, tail, years


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent,
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def git_clean() -> bool | None:
    try:
        return not subprocess.run(["git", "status", "--porcelain"], cwd=Path(__file__).resolve().parent,
                                  capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build(input_root: Path, output_root: Path, input_manifest: Path, manifest: Path, require_clean: bool = False) -> dict:
    started = dt.datetime.now(dt.timezone.utc)
    commit, clean = git_sha(), git_clean()             # recorded at start: the code that actually runs
    if require_clean and not clean:
        raise SystemExit("working tree is not clean; the generating commit would not describe the running code")
    if output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(f"{output_root} is not empty")
    output_root.mkdir(parents=True, exist_ok=True)
    edges = {m: read_edges(month_file(input_root, m)) for m in range(1, 13)}   # immutable input
    new_head = {m: {v: edges[m][0][v].copy() for v in VARS} for m in range(1, 13)}
    new_tail = {m: {v: edges[m][1][v].copy() for v in VARS} for m in range(1, 13)}
    boundaries = []
    for m in range(1, 13):
        nxt = m % 12 + 1
        windows = {v: np.concatenate([edges[m][1][v], edges[nxt][0][v]]) for v in VARS}
        out, counts = smooth_boundary(windows, m, edges[m][2], edges[nxt][2])
        for v in VARS:
            new_tail[m][v] = out[v][: N + 1]
            new_head[nxt][v] = out[v][N + 1:]
        boundaries.append(dict(boundary=f"{m:02d}->{nxt:02d}", wrap=m == 12, **counts))
        print(f"boundary {m:02d}->{nxt:02d}: {counts}", flush=True)
    files = []
    for m in range(1, 13):
        src, dst = month_file(input_root, m), month_file(output_root, m)
        shutil.copyfile(src, dst)
        with netCDF4.Dataset(dst, "a") as ds:
            for v in VARS:
                # head = window rows B..W-1 (hours b..b+N); modified: b..b+N-1 = file rows 0..N-1
                ds.variables[v][:N, :] = new_head[m][v][:N]
                # tail = window rows 0..B-1 (hours b-N-1..b-1); modified: b-N..b-1 = last N file rows
                ds.variables[v][-N:, :] = new_tail[m][v][1:]
            ds.setncattr("month_interface_smoothing", json.dumps({"method": METHOD, "hours_each_side": N,
                                                                  "variables": list(VARS), "wrap": True, "source": SOURCE}))
        files.append({"month": m, "path": str(dst), "bytes": dst.stat().st_size, "sha256": sha256(dst)})
        print(f"month {m:02d} written", flush=True)
    payload = {
        "dataset_id": "cey_2006_2025", "version": "v2-month-interface-smoothing",
        "derived_from": {"manifest": str(input_manifest), "manifest_sha256": sha256(input_manifest),
                         "input_root": str(input_root)},
        "month_interface_smoothing": {
            "method": METHOD, "hours_each_side": N, "variables": list(VARS), "wrap": True, "source": SOURCE,
            "expected_step": "mean of the two adjacent within-month steps",
            "skip_rules": "consecutive source hours (same year, not leap Feb->Mar); non-finite window "
                          "(T/Td jointly, pressure separately)",
            "clipping_rule": "Td = min(Td, T) only in modified, T/Td-eligible hours",
            "pressure_rule": "pressure window left unchanged (and counted) if smoothing would give a non-finite or non-positive value",
            "note": "Adjusted hours are synthetic; selected_source_year documents provenance, not exact values.",
            "spec": "docs/qa/cey/BUG-018-smoothing-spec.md (revision 4)",
            "boundaries": boundaries},
        "generating_commit": commit, "working_tree_clean_at_start": clean,
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "files": files,
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input-root", type=Path, required=True)
    p.add_argument("--input-manifest", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    a = p.parse_args(argv)
    build(a.input_root, a.output_root, a.input_manifest, a.manifest, require_clean=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
