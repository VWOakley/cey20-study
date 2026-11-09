from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import netCDF4
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from scripts.research import auth003_study as study  # noqa: E402

YEARS = study.YEARS
LATS = [48.75, 49.0, -33.5]
LONS = [9.75, 10.0, 151.0]


def _write_source(path: Path, year: int, month: int, rng, nan_points=()) -> None:
    # nan_points: float32 variables with NaN (the builder cannot fill masked int16 with NaN)
    path.parent.mkdir(parents=True, exist_ok=True)
    hours = study.builder._standard_month_hours(month)
    with netCDF4.Dataset(path, "w") as ds:
        ds.createDimension("time", hours)
        ds.createDimension("point", len(LATS))
        ds.createVariable("time", "i8", ("time",))[:] = np.arange(hours)
        ds.createVariable("latitude", "f4", ("point",))[:] = LATS
        ds.createVariable("longitude", "f4", ("point",))[:] = LONS
        kind = "f4" if nan_points else "i2"
        t = ds.createVariable("temperature_c_x100", kind, ("time", "point"))
        d = ds.createVariable("dewpoint_c_x100", kind, ("time", "point"))
        p = ds.createVariable("surface_pressure_hpa_x10", "i2", ("time", "point"))
        hour = np.arange(hours)[:, None]
        base = rng.normal(0, 2, size=(1, len(LATS))) + (year - 2015) * 0.1
        temp = 5 + base + 6 * np.sin(2 * np.pi * (hour % 24) / 24) + rng.normal(0, 1, (hours, len(LATS)))
        dew = temp - np.abs(rng.normal(3, 2, (hours, len(LATS))))
        t[:], d[:], p[:] = np.round(temp * 100), np.round(dew * 100), 10132
        for q in nan_points:
            t[:, q] = np.nan
            d[:, q] = np.nan


def _populate(ext: Path, leg: Path, months=(1,), nan_points=()) -> None:
    rng = np.random.default_rng(7)
    for year in YEARS:
        root = ext if year in study.builder.EXTENSION_YEARS else leg
        for m in months:
            _write_source(root / str(year) / f"era5_land_hourly_0p25_landpoints_{year}_{m:02d}.nc",
                          year, m, rng, nan_points)


def _synthetic(points=3, hours=240, seed=1):
    rng = np.random.default_rng(seed)
    t = (rng.normal(8, 3, (20, 1, points)) + rng.normal(0, 2, (20, hours, points))).astype(np.float32)
    td = (t - np.abs(rng.normal(3, 1.5, t.shape))).astype(np.float32)
    return {"temperature_c": t, "dewpoint_c": td, "surface_pressure_pa": np.full_like(t, 101320.0)}


class SelectionTests(unittest.TestCase):
    def test_parity_with_builder(self):
        data = _synthetic()
        res = study.analyse_month(data)  # raises on mismatch
        ref_idx, ref_score = study._select_representative_year(data)
        np.testing.assert_array_equal(res["idx"], ref_idx)
        np.testing.assert_allclose(res["best"], ref_score, rtol=1e-5)

    def test_parity_check_detects_mismatch(self):
        data = _synthetic()
        res = study.analyse_month(data)
        with self.assertRaises(RuntimeError):
            study.assert_parity(data, (res["idx"] + 1) % 20, res["best"])

    def test_all_nan_point_guarded_and_builder_behaviour_reported(self):
        data = _synthetic()
        data["temperature_c"][:, :, 1] = np.nan
        res = study.analyse_month(data)
        self.assertEqual(list(res["all_nan"]), [False, True, False])
        self.assertEqual(res["idx"][1], -1)
        self.assertTrue(study._builder_raises(data, 1))
        self.assertFalse(study._builder_raises(data, 0))
        probe = study.all_nan_guard_probe()
        self.assertTrue(probe["raises"])

    def test_nan_hours_do_not_break_selection(self):
        data = _synthetic()
        data["temperature_c"][3, :20, 0] = np.nan
        res = study.analyse_month(data)
        self.assertTrue(np.isfinite(res["best"]).all())

    def test_tie_goes_to_earliest_year(self):
        data = _synthetic(points=1)
        data["temperature_c"][:] = data["temperature_c"][0]  # all years identical
        data["dewpoint_c"][:] = data["dewpoint_c"][0]
        res = study.analyse_month(data)
        self.assertEqual(res["idx"][0], 0)
        part = study.checks_month(1, data, [{"name": "a", "lon": 0.0}], res)
        self.assertEqual(part["ties"][0]["n_tied"], 20)
        self.assertEqual(part["ties"][0]["selected_year"], 2006)
        self.assertEqual(part["ties"][0]["latest_tied_year"], 2025)


class CorrectionTests(unittest.TestCase):
    """Copilot review findings AUTH-003-S2-001..003."""

    PT = [{"name": "a", "lon": 0.0}]

    def test_001_nan_hours_make_exposure_unknown_not_zero(self):
        data = _synthetic(points=1)
        data["temperature_c"][3, :24, 0] = np.nan
        res = study.analyse_month(data)
        self.assertAlmostEqual(float(res["coverage"][3, 0]), 1 - 24 / 240)
        self.assertEqual(float(res["coverage"][4, 0]), 1.0)
        rows = study.rows_features(1, self.PT, res)
        bad = [r for r in rows if r["year"] == YEARS[3]][0]
        for k in study.EXPOSURE_FEATURES:
            self.assertEqual(bad[k], "UNKNOWN")
        self.assertEqual(bad["exposure_complete"], 0)
        good = [r for r in rows if r["year"] == YEARS[4]][0]
        self.assertIsInstance(good["hours_rh_ge_80"], float)

    def test_001_annual_totals_unknown_or_incomplete(self):
        data = _synthetic(points=1)
        data["dewpoint_c"][5, :10, 0] = np.nan
        res = study.analyse_month(data)
        annual = study.summarise_annual({1: res}, self.PT, [1])
        for r in annual:
            self.assertEqual(r["n_complete_years"], 19)
            self.assertEqual(r["stats_status"], "INCOMPLETE")
            self.assertLess(r["min_valid_hour_coverage"], 1.0)
            self.assertIsInstance(r["long_term_mean_hours"], float)
            if res["idx"][0] == 5:
                self.assertEqual(r["assembled_hours"], "UNKNOWN")
        # force the selected year to be the incomplete one
        res2 = dict(res, idx=np.array([5], dtype=np.int16))
        for r in study.summarise_annual({1: res2}, self.PT, [1]):
            self.assertEqual(r["assembled_hours"], "UNKNOWN")
            self.assertEqual(r["abs_deviation_h"], "UNKNOWN")
            self.assertEqual(r["assembled_complete"], 0)
        reps = [r for r in study.rows_representativeness(1, self.PT, res2)
                if r["feature"] == "hours_rh_ge_80"]
        self.assertEqual(reps[0]["selected_value"], "UNKNOWN")
        self.assertEqual(reps[0]["exposure_complete"], 0)

    def test_001_complete_data_stays_numeric(self):
        res = study.analyse_month(_synthetic(points=1))
        for r in study.summarise_annual({1: res}, self.PT, [1]):
            self.assertEqual(r["stats_status"], "COMPLETE")
            self.assertIsInstance(r["assembled_hours"], float)

    def test_002_deviation_nonnegative(self):
        res = study.analyse_month(_synthetic(points=1))
        rows = study.rows_representativeness(1, self.PT, res)
        for r in rows:
            self.assertGreaterEqual(r["abs_deviation"], 0.0)
            c = r["climatology"]
            if c != 0 and np.isfinite(c):
                self.assertAlmostEqual(r["rel_deviation"], r["abs_deviation"] / abs(c))
        # constructed below-climatology case
        res["features"]["temperature_mean_c"][:, 0] = np.arange(20, dtype=float)
        res["idx"] = np.array([0], dtype=np.int16)
        row = [r for r in study.rows_representativeness(1, self.PT, res)
               if r["feature"] == "temperature_mean_c"][0]
        self.assertAlmostEqual(row["abs_deviation"], 9.5)
        self.assertAlmostEqual(row["rel_deviation"], 9.5 / 9.5)

    def test_003_tie_selected_year_is_actual_selection(self):
        data = _synthetic(points=1)
        res = study.analyse_month(data)
        scores = res["scores"].copy()
        scores[:, 0] = 5.0
        scores[2, 0] = 1.0 + 5e-7   # earlier, within tolerance, but not the minimum
        scores[7, 0] = 1.0          # actual minimum
        res = dict(res, scores=scores, idx=np.array([7], dtype=np.int16),
                   all_nan=np.array([False]))
        part = study.checks_month(1, data, self.PT, res)
        row = part["ties"][0]
        self.assertEqual(row["selected_year"], YEARS[7])
        self.assertEqual(row["earliest_tied_year"], YEARS[2])
        self.assertEqual(row["n_tied"], 2)

    def test_manifest_git_lookup_optional(self):
        from unittest import mock
        for exc in (FileNotFoundError("git"), PermissionError("git")):
            with mock.patch.object(study.subprocess, "run", side_effect=exc):
                self.assertIsNone(study.git_sha())
        with mock.patch.object(study.subprocess, "run",
                               side_effect=study.subprocess.TimeoutExpired("git", 10)):
            self.assertIsNone(study.git_sha())


class EffectiveWeightTests(unittest.TestCase):
    def test_constructed_case(self):
        feats = {k: np.zeros((20, 1)) for k in study.FEATURES}
        feats["temperature_mean_c"] = np.arange(20, dtype=float)[:, None] * 2.0
        feats["hours_rh_ge_80"] = np.arange(20, dtype=float)[:, None]
        res = {"features": feats}
        rows = study.rows_effective_weights(1, [{"name": "p"}], res)
        share = {r["feature"]: r["effective_share"] for r in rows}
        s = np.std(np.arange(20), ddof=1)
        a = 1.5 * 2 * s / 8.0
        b = 1.2 * s / 180.0
        self.assertAlmostEqual(share["temperature_mean_c"], a / (a + b))
        self.assertAlmostEqual(share["hours_rh_ge_80"], b / (a + b))
        self.assertAlmostEqual(sum(share.values()), 1.0)
        nominal = {r["feature"]: r["nominal_share"] for r in rows}
        self.assertAlmostEqual(sum(nominal.values()), 1.0)
        self.assertAlmostEqual(nominal["temperature_mean_c"], 1.5 / 10.5)


class SensitivityTests(unittest.TestCase):
    def test_variant_set_and_bookkeeping(self):
        names = [n for n, _ in study.weight_variants()]
        self.assertEqual(len(names), 1 + 2 * len(study.FEATURES))
        self.assertIn("equal_weights", names)
        data = _synthetic()
        res = study.analyse_month(data)
        sens = {1: study.sensitivity_month(data, res)}
        self.assertIn("local_interannual_std_scales", sens[1])
        summary, per_point = study.sensitivity_tables(sens, {1: res}, [{"name": str(i)} for i in range(3)], [1])
        self.assertEqual(len(summary), len(names) + 1)
        for row in summary:
            self.assertEqual(row["point_months"], 3)
            self.assertTrue(0.0 <= row["fraction_changed"] <= 1.0)
        # baseline-equal variant: unchanged weights give zero change
        res_same = {1: {"idx": res["idx"], "hours": {k: study._take(res["features"][k], res["idx"])
                                                     for k in study.EXPOSURE_FEATURES}}}
        s2, _ = study.sensitivity_tables({1: {"same": res_same[1]}}, {1: res}, [{"name": str(i)} for i in range(3)], [1])
        self.assertEqual(s2[0]["changed"], 0)
        self.assertEqual(s2[0]["mean_abs_delta_hours_rh_ge_80"], 0.0)

    def test_zero_variance_local_scale_is_safe(self):
        feats = study.compute_features(*(_synthetic(points=1)[k] for k in ("temperature_c", "dewpoint_c")))
        std = {k: np.zeros(1) for k in study.FEATURES}
        scores = study.score_candidates(feats, scales=std)
        self.assertTrue(np.isfinite(scores).all())


class CoverageProtectionTests(unittest.TestCase):
    """R4: sensitivity aggregates and Magnus diagnostics carry coverage; no NaN -> 0.0."""

    PTS = [{"name": "a", "lat": 48.0, "lon": 10.0}]
    K = "hours_rh_ge_80"

    def _sens(self, data, months=(1,)):
        res = {m: study.analyse_month(data) for m in months}
        sens = {m: study.sensitivity_month(data, res[m]) for m in months}
        return study.sensitivity_tables(sens, res, self.PTS, list(months)), res

    def test_reproduction_all_nan_unknown_not_zero(self):
        n = np.full((20, 48, 1), np.nan, dtype=np.float32)
        data = {"temperature_c": n, "dewpoint_c": n.copy(), "surface_pressure_pa": n.copy()}
        (summary, per_point), res = self._sens(data)
        self.assertEqual(res[1]["idx"][0], -1)
        for r in per_point:
            self.assertEqual(r["status"], study.UNKNOWN)
            self.assertEqual(r["n_complete_months"], 0)
            for k in study.EXPOSURE_FEATURES:
                self.assertEqual(r[f"delta_{k}_sum_over_months"], study.UNKNOWN)
        for r in summary:
            self.assertEqual(r["status"], study.UNKNOWN)
            self.assertEqual(r["n_complete_point_months"], 0)
            for k in study.EXPOSURE_FEATURES:
                self.assertEqual(r[f"mean_delta_{k}"], study.UNKNOWN)
                self.assertEqual(r[f"mean_abs_delta_{k}"], study.UNKNOWN)
        mg = study.checks_month(1, data, self.PTS, res[1])["magnus"][0]
        self.assertEqual(mg["status"], study.UNKNOWN)
        self.assertEqual(mg["n_complete_years"], 0)
        for k in ("hours_rh_ge_80", "hours_rh_ge_90"):
            for suffix in ("water_mean", "mixed_mean", "mean_diff"):
                self.assertEqual(mg[f"{k}_{suffix}"], study.UNKNOWN)
        self.assertEqual(mg["hours_below_0c_mean_per_year"], study.UNKNOWN)

    def test_partial_missing_year_labelled_incomplete(self):
        data = _synthetic(points=1, hours=48)
        data["temperature_c"][3, 5, 0] = np.nan  # one candidate year loses one hour
        res = study.analyse_month(data)
        mg = study.checks_month(1, data, self.PTS, res)["magnus"][0]
        self.assertEqual(mg["status"], "INCOMPLETE")
        self.assertEqual(mg["n_complete_years"], 19)
        self.assertIsInstance(mg[f"{self.K}_water_mean"], float)

    def test_selected_year_incomplete_makes_deltas_unknown(self):
        data = _synthetic(points=1, hours=48)
        res = study.analyse_month(data)
        sel = int(res["idx"][0])
        data["temperature_c"][sel, 7, 0] = np.nan  # baseline selection loses coverage
        (summary, per_point), _ = self._sens(data)
        for r in per_point:
            self.assertNotEqual(r["status"], "COMPLETE")
            self.assertEqual(r[f"delta_{self.K}_sum_over_months"], study.UNKNOWN)

    def test_missing_month_in_multi_month_aggregate_is_unknown(self):
        good, bad = _synthetic(points=1, hours=48, seed=1), _synthetic(points=1, hours=48, seed=2)
        n = np.full_like(bad["temperature_c"], np.nan)
        bad["temperature_c"], bad["dewpoint_c"] = n, n.copy()
        res = {1: study.analyse_month(good), 2: study.analyse_month(bad)}
        sens = {1: study.sensitivity_month(good, res[1]), 2: study.sensitivity_month(bad, res[2])}
        summary, per_point = study.sensitivity_tables(sens, res, self.PTS, [1, 2])
        for r in per_point:
            self.assertEqual(r["n_requested_months"], 2)
            self.assertEqual(r["n_complete_months"], 1)
            self.assertEqual(r["status"], "INCOMPLETE")
            self.assertEqual(r[f"delta_{self.K}_sum_over_months"], study.UNKNOWN)  # not a partial sum
        for r in summary:
            self.assertEqual(r["status"], "INCOMPLETE")
            self.assertEqual(r["n_complete_point_months"], 1)
            self.assertEqual(r[f"mean_delta_{self.K}"], study.UNKNOWN)
            self.assertIsInstance(r[f"partial_mean_delta_{self.K}"], float)  # labelled, denominator exposed

    def test_baseline_variant_coverage_difference(self):
        data = _synthetic(points=1, hours=48)
        res = study.analyse_month(data)
        sens = {1: study.sensitivity_month(data, res)}
        name = next(n for n, v in sens[1].items() if v["idx"][0] != res["idx"][0])
        # variant's selected year loses coverage; baseline stays complete
        data["temperature_c"][int(sens[1][name]["idx"][0]), 0, 0] = np.nan
        res2 = dict(res, coverage=study.valid_hour_coverage(data["temperature_c"], data["dewpoint_c"]))
        summary, per_point = study.sensitivity_tables({1: {name: sens[1][name]}}, {1: res2}, self.PTS, [1])
        self.assertEqual(per_point[0]["status"], study.UNKNOWN)
        self.assertEqual(per_point[0][f"delta_{self.K}_sum_over_months"], study.UNKNOWN)
        self.assertEqual(summary[0]["point_months"], 1)  # selection change still counted

    def test_complete_data_true_zero_control(self):
        data = _synthetic(points=1, hours=48)
        res = study.analyse_month(data)
        same = {"idx": res["idx"], "hours": {k: study._take(res["features"][k], res["idx"])
                                              for k in study.EXPOSURE_FEATURES}}
        summary, per_point = study.sensitivity_tables({1: {"same": same}}, {1: res}, self.PTS, [1])
        self.assertEqual(per_point[0]["status"], "COMPLETE")
        self.assertEqual(per_point[0][f"delta_{self.K}_sum_over_months"], 0.0)
        self.assertEqual(summary[0]["status"], "COMPLETE")
        self.assertEqual(summary[0][f"mean_delta_{self.K}"], 0.0)
        mg = study.checks_month(1, data, self.PTS, res)["magnus"][0]
        self.assertEqual(mg["status"], "COMPLETE")
        self.assertEqual(mg["n_complete_years"], 20)
        self.assertIsInstance(mg[f"{self.K}_water_mean"], float)


class VariantTests(unittest.TestCase):
    def test_local_day_shift(self):
        self.assertEqual(study.local_day_shift_hours(151.0), 10)
        self.assertEqual(study.local_day_shift_hours(-74.0), -5)
        self.assertEqual(study.local_day_shift_hours(7.4), 0)

    def test_local_day_zero_shift_equals_utc_and_shift_differs(self):
        t = _synthetic(points=1, hours=24 * 30)["temperature_c"]
        utc = study._daily_temperature_range_mean(t)[:, 0]
        np.testing.assert_allclose(study.dtr_local_day(t, np.array([0.0]))[:, 0], utc)
        shifted = study.dtr_local_day(t, np.array([150.0]))[:, 0]  # +10 h
        self.assertFalse(np.allclose(shifted, utc))

    def test_local_day_block_alignment(self):
        # local midnight at UTC hour 14 for +10 h; a spike pattern per local day
        hours = 24 * 5
        t = np.zeros((20, hours, 1), dtype=np.float32)
        for h in range(hours):
            t[:, h, 0] = 10.0 if (h - 14) % 24 == 5 else 0.0
        out = study.dtr_local_day(t, np.array([150.0]))
        np.testing.assert_allclose(out[:, 0], 10.0)  # every local day holds exactly one spike
        utc = study._daily_temperature_range_mean(t)[:, 0]
        np.testing.assert_allclose(utc, 10.0 * 4 / 5 + 0.0, atol=10.0)  # sanity only

    def test_mixed_equals_water_above_zero_and_differs_below(self):
        warm = np.array([5.0, 20.0]); dew = np.array([2.0, 10.0])
        np.testing.assert_allclose(study.rh_mixed(warm, dew),
                                   study._relative_humidity_from_dewpoint(warm, dew), rtol=1e-12)
        cold = np.array([-10.0]); cdew = np.array([-12.0])
        self.assertGreater(abs(study.rh_mixed(cold, cdew)[0]
                               - study._relative_humidity_from_dewpoint(cold, cdew)[0]), 0.1)
        self.assertIn("UNVERIFIED", study.ICE_CITATION_STATUS)

    def test_water_features_match_builder_helpers(self):
        t = _synthetic()["temperature_c"]
        np.testing.assert_allclose(study.saturation_hpa_water(t), study.builder._saturation_vapor_pressure_hpa(t))


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.ext, cls.leg = root / "ext", root / "leg"
        _populate(cls.ext, cls.leg, months=(1, 2))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _run(self, command, out, *extra):
        argv = [command, "--extension-root", str(self.ext), "--legacy-root", str(self.leg),
                "--output", str(out), "--months", "1-2", "--no-png", *extra]
        with contextlib.redirect_stdout(io.StringIO()):
            return study.main(argv)

    def test_all_subcommands_and_manifest(self):
        out = Path(self.tmp.name) / "out"
        pts = ("--point-index", "0", "--point-index", "1", "--point=-33.4,150.9")
        expected = {
            "features": "features.csv", "effective-weights": "effective_weights_summary.csv",
            "representativeness": "annual_exposure.csv", "sensitivity": "sensitivity_summary.csv",
            "checks": "checks_summary.json",
        }
        for command, artefact in expected.items():
            self.assertEqual(self._run(command, out, *pts), 0, command)
            self.assertTrue((out / artefact).exists(), artefact)
            manifest = json.loads((out / f"manifest_{command}.json").read_text())
            for key in ("commit_sha", "inputs", "parameters", "started_utc", "finished_utc", "points", "outputs"):
                self.assertIn(key, manifest)
            self.assertTrue(manifest["started_utc"].endswith("+00:00"))
            self.assertEqual(len(manifest["points"]), 3)
            self.assertEqual(manifest["points"][2]["index"], 2)  # nearest to -33.4,150.9

        rows = list(csv.DictReader(open(out / "features.csv")))
        selected = [r for r in rows if r["selected"] == "1" and r["point"] == "index0" and r["month"] == "1"]
        self.assertEqual(len(selected), 1)
        with netCDF4.Dataset(self.ext / "2006" / "era5_land_hourly_0p25_landpoints_2006_01.nc") as _:
            pass
        annual = list(csv.DictReader(open(out / "annual_exposure.csv")))
        self.assertEqual(annual[0]["complete_year"], "False")  # only 2 of 12 months
        sens = list(csv.DictReader(open(out / "sensitivity_summary.csv")))
        self.assertEqual(len(sens), 1 + 2 * 10 + 1)
        summary = json.loads((out / "checks_summary.json").read_text())
        self.assertEqual(summary["candidates_with_nan"], 0)
        self.assertIn("UNVERIFIED", summary["ice_citation"])

    def test_features_selected_year_matches_builder_on_files(self):
        sources = study.discover_sources(self.ext, self.leg, [1])
        data = study.load_points_month(sources, 1, [0, 1, 2])
        ref_idx, _ = study._select_representative_year(data)
        res = study.analyse_month(data)
        np.testing.assert_array_equal(res["idx"], ref_idx)

    def test_nan_input_reported_by_checks(self):
        root = Path(self.tmp.name) / "nan"
        _populate(root / "e", root / "l", months=(1,), nan_points=(1,))
        out = root / "out"
        argv = ["checks", "--extension-root", str(root / "e"), "--legacy-root", str(root / "l"),
                "--output", str(out), "--months", "1", "--point-index", "0", "--point-index", "1", "--no-png"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(study.main(argv), 0)
        summary = json.loads((out / "checks_summary.json").read_text())
        self.assertEqual(summary["point_months_all_nan"], 1)
        self.assertEqual(summary["candidates_with_nan"], 20)

    def test_argument_errors_exit_codes(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            study.main([])
        self.assertEqual(cm.exception.code, 2)
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            study.main(["features", "--extension-root", "x"])  # --output missing
        self.assertEqual(cm.exception.code, 2)
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            study.main(["nonsense"])
        self.assertEqual(cm.exception.code, 2)

    def test_runtime_errors_exit_nonzero(self):
        out = Path(self.tmp.name) / "err"
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:  # missing sources
                study.main(["features", "--extension-root", str(out / "no"), "--legacy-root", str(out / "no"),
                            "--output", str(out), "--point-index", "0"])
            self.assertNotEqual(cm.exception.code, 0)
            with self.assertRaises(SystemExit) as cm:  # no points
                self._run("features", out)
            self.assertNotEqual(cm.exception.code, 0)
            with self.assertRaises(SystemExit):  # index out of range
                self._run("features", out, "--point-index", "99")
            with self.assertRaises(SystemExit):  # bad --point
                self._run("features", out, "--point", "abc")
            with self.assertRaises(SystemExit):  # duplicate
                self._run("features", out, "--point-index", "0", "--point-index", "0")
            self.assertEqual(self._run("features", out, "--point-index", "0", "--months", "13"), 1)

    def test_points_file(self):
        pf = Path(self.tmp.name) / "pts.csv"
        pf.write_text("name,lat,lon,index\nA,,,1\nB,48.7,9.8,\n", encoding="utf-8")
        out = Path(self.tmp.name) / "pf"
        self.assertEqual(self._run("features", out, "--points-file", str(pf)), 0)
        manifest = json.loads((out / "manifest_features.json").read_text())
        self.assertEqual([p["name"] for p in manifest["points"]], ["A", "B"])
        self.assertEqual(manifest["points"][1]["index"], 0)


if __name__ == "__main__":
    unittest.main()


class SelectionChangeCoverageTests(unittest.TestCase):
    """Copilot AUTH-003-S2-R4-REVIEW: an absent selection must not silently shrink the change-rate denominator."""

    PTS = [{"name": "a", "lat": 48.0, "lon": 10.0}]

    def test_absent_selection_makes_change_rate_unknown_with_partial_denominator(self):
        good, bad = _synthetic(points=1, hours=48, seed=1), _synthetic(points=1, hours=48, seed=2)
        n = np.full_like(bad["temperature_c"], np.nan)
        bad["temperature_c"], bad["dewpoint_c"] = n, n.copy()
        res = {1: study.analyse_month(good), 2: study.analyse_month(bad)}
        self.assertEqual(res[2]["idx"][0], -1)
        other = (int(res[1]["idx"][0]) + 1) % len(study.YEARS)
        changed = {"idx": np.asarray([other], dtype=np.int16),
                   "hours": {k: study._take(res[1]["features"][k], np.asarray([other])) for k in study.EXPOSURE_FEATURES}}
        absent = {"idx": res[2]["idx"], "hours": {k: np.full(1, np.nan) for k in study.EXPOSURE_FEATURES}}
        summary, per_point = study.sensitivity_tables({1: {"v": changed}, 2: {"v": absent}}, res, self.PTS, [1, 2])
        row = summary[0]
        self.assertEqual(row["selection_status"], "INCOMPLETE")
        self.assertEqual(row["fraction_changed"], study.UNKNOWN)
        self.assertEqual(row["changed"], study.UNKNOWN)
        self.assertEqual(row["n_requested_point_months"], 2)
        self.assertEqual(row["n_selection_point_months"], 1)
        self.assertEqual(row["partial_fraction_changed"], 1.0)
        self.assertEqual(per_point[0]["point_months_changed"], study.UNKNOWN)
        self.assertEqual(per_point[0]["partial_point_months_changed"], 1)
        self.assertEqual(per_point[0]["n_selection_months"], 1)

    def test_complete_selections_keep_numeric_change_rate(self):
        data = _synthetic(points=1, hours=48)
        res = study.analyse_month(data)
        same = {"idx": res["idx"], "hours": {k: study._take(res["features"][k], res["idx"]) for k in study.EXPOSURE_FEATURES}}
        summary, per_point = study.sensitivity_tables({1: {"same": same}}, {1: res}, self.PTS, [1])
        self.assertEqual(summary[0]["selection_status"], "COMPLETE")
        self.assertEqual(summary[0]["fraction_changed"], 0.0)
        self.assertEqual(per_point[0]["point_months_changed"], 0)
