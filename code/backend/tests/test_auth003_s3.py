from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
import auth003_s3 as R  # noqa: E402
import auth003_study as S  # noqa: E402


def _counts(values):
    """(months, years, points) from a nested list."""
    return np.asarray(values, dtype=np.float64)


def test_annual_target_relative_rule_and_zero_reference() -> None:
    # 1 month, 2 years, 2 points; metric values identical for all three count keys.
    all_c = {k: _counts([[[100.0, 0.0], [110.0, 0.0]]]) for k in R.COUNT_KEYS}
    sel = {k: np.asarray([[104.0, 0.0]]) for k in R.COUNT_KEYS}
    rows = R.annual_target(sel, all_c)
    p0 = [r for r in rows if r["point"] == 0][0]
    p1 = [r for r in rows if r["point"] == 1][0]
    assert p0["h_ref"] == 105.0 and p0["signed_h"] == -1.0
    assert p0["rel_error"] == pytest.approx(1 / 105) and p0["pass"]
    assert p1["rel_error"] is None and p1["pass"]          # Href = 0 and Hsel = 0


def test_annual_target_fails_beyond_five_percent_and_nonzero_at_zero_reference() -> None:
    all_c = {k: _counts([[[100.0, 0.0], [100.0, 0.0]]]) for k in R.COUNT_KEYS}
    sel = {k: np.asarray([[106.0, 1.0]]) for k in R.COUNT_KEYS}
    rows = R.annual_target(sel, all_c)
    assert not [r for r in rows if r["point"] == 0][0]["pass"]
    assert not [r for r in rows if r["point"] == 1][0]["pass"]


def test_annual_target_boundary_exactly_five_percent_passes() -> None:
    all_c = {k: _counts([[[100.0], [100.0]]]) for k in R.COUNT_KEYS}
    sel = {k: np.asarray([[105.0]]) for k in R.COUNT_KEYS}
    assert all(r["pass"] for r in R.annual_target(sel, all_c))


def test_monthly_target_uses_mean_over_all_years() -> None:
    feats = {"temperature_mean_c": np.asarray([[10.0], [11.0], [12.4]]),
             "relative_humidity_mean_pct": np.asarray([[70.0], [72.0], [77.0]])}
    rows = R.monthly_target(3, feats, np.asarray([0]))
    assert rows[0]["d_temperature_c"] == pytest.approx(10.0 - 11.133333333)
    assert not rows[0]["pass_t"]                               # |dT| = 1.13 > 0.5
    assert rows[0]["d_rh_pct"] == pytest.approx(-3.0) and not rows[0]["pass_rh"]
    assert rows[0]["selected_year"] == S.YEARS[0]


def test_select_excluding_removes_year_from_candidates_and_climatology() -> None:
    n = len(S.YEARS)
    feats = {k: np.full((n, 1), 1.0, dtype=np.float32) for k in S.FEATURES}
    feats["temperature_mean_c"][:, 0] = np.arange(n, dtype=np.float32)
    full, _, _ = S.select_year(S.score_candidates(feats))
    mid = int(full[0])
    idx = R.select_excluding(feats, mid)
    assert int(idx[0]) != mid
    assert 0 <= int(idx[0]) < n
    # Index mapping: excluding year 0 must never return 0 and stays on the full axis.
    assert int(R.select_excluding(feats, 0)[0]) >= 1


def test_counts_respect_thresholds() -> None:
    t = np.full((1, 4, 1), 20.0, dtype=np.float32)
    td = np.asarray([20.0, 19.0, 18.5, 10.0], dtype=np.float32).reshape(1, 4, 1)
    base = R.counts(t, td)
    wide = R.counts(t, td, (80.0, 90.0, 3.0))
    assert base["hours_dewpoint_depression_le_2c"][0, 0] == 3.0
    assert wide["hours_dewpoint_depression_le_2c"][0, 0] == 3.0
    assert R.counts(t, td, (80.0, 90.0, 1.0))["hours_dewpoint_depression_le_2c"][0, 0] == 2.0


def test_weight_variants_cover_protocol_set() -> None:
    names = [n for n, _ in R.weight_variants()]
    assert "equal_weights" in names
    for extra in ("moisture_joint+25%", "thermal_joint-25%", "count_block_ablated", "count_block_x0.5"):
        assert extra in names
    ablated = dict(R.weight_variants())["count_block_ablated"]
    assert all(ablated[k] == 0.0 for k in R.COUNT_KEYS)


def test_frozen_points_rejects_ineligible() -> None:
    with pytest.raises(SystemExit):
        R.frozen_points({"points": [{"name": "x", "point_index": 1, "eligible": False}]})


def test_require_complete_aborts_on_partial_coverage() -> None:
    res = {"coverage": np.asarray([[1.0, 1.0], [1.0, 0.99]])}
    with pytest.raises(SystemExit):
        R.require_complete(1, res, [{"name": "a"}, {"name": "b"}])


def test_verify_inputs_detects_changed_file(tmp_path) -> None:
    f = tmp_path / "a.nc"; f.write_bytes(b"x")
    import datetime as dt
    mtime = dt.datetime.fromtimestamp(f.stat().st_mtime, dt.timezone.utc).isoformat(timespec="seconds")
    src = type("Src", (), {"path": f})()
    freeze = {"input_inventory": [{"year": 2006, "month": 1, "path": str(f), "bytes": 1, "mtime_utc": mtime, "time_ok": True}]}
    R.verify_inputs({(2006, 1): src}, freeze)
    f.write_bytes(b"xy")
    with pytest.raises(SystemExit):
        R.verify_inputs({(2006, 1): src}, freeze)


def _freeze_points(names, indices=None, eligible=True):
    indices = indices or list(range(len(names)))
    return {"points": [{"name": n, "point_index": i, "eligible": eligible} for n, i in zip(names, indices)]}


def test_frozen_points_require_exactly_the_protocol_points() -> None:
    names = list(R.PROTOCOL_POINTS)
    assert len(R.frozen_points(_freeze_points(names))) == 14
    for bad in (names[:-1], names + ["Extra"], names[:-1] + ["Singapore"]):
        with pytest.raises(SystemExit):
            R.frozen_points(_freeze_points(bad))


def test_frozen_points_reject_duplicate_index() -> None:
    names = list(R.PROTOCOL_POINTS)
    with pytest.raises(SystemExit):
        R.frozen_points(_freeze_points(names, [0] * 14))


def test_verify_input_hashes_detects_same_size_content_change(tmp_path) -> None:
    f = tmp_path / "a.nc"; f.write_bytes(b"ab")
    src = type("Src", (), {"path": f})()
    freeze = {"input_inventory_sha256": "inv"}
    hashes = {"freeze_input_inventory_sha256": "inv", "files": [{"year": 2006, "month": 1, "sha256": R.sha256_file(f)}]}
    R.verify_input_hashes({(2006, 1): src}, hashes, freeze)
    f.write_bytes(b"ba")                                   # same size, different content
    with pytest.raises(SystemExit):
        R.verify_input_hashes({(2006, 1): src}, hashes, freeze)
    with pytest.raises(SystemExit):
        R.verify_input_hashes({(2006, 1): src}, dict(hashes, freeze_input_inventory_sha256="other"), freeze)


def test_verify_study_code_rejects_changed_package(tmp_path, monkeypatch) -> None:
    a, b = tmp_path / "auth003_study.py", tmp_path / "auth003_s3.py"
    a.write_bytes(b"x = 1\r\n"); b.write_bytes(b"y = 2\n")
    monkeypatch.setattr(R, "PINNED_FILES", {"auth003_study.py": a, "auth003_s3.py": b})
    import hashlib
    pin = {"auth003_study.py": hashlib.sha256(b"x = 1\n").hexdigest(), "auth003_s3.py": hashlib.sha256(b"y = 2\n").hexdigest()}
    R.verify_study_code(pin)                               # CRLF normalised
    a.write_bytes(b"x = 2\n")
    with pytest.raises(SystemExit):
        R.verify_study_code(pin)
