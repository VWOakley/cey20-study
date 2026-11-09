"""Build the global CEY20 representative year from packed ERA5-Land months.

The 2006-2025 source period is split across two archives: the CEY20 extension
contains 2006-2014 and 2025, while the established CEY10 archive supplies
2015-2024.  This builder resolves that split explicitly and never treats the
incomplete extension/2015 directory as authoritative.
"""

from __future__ import annotations

import argparse
import calendar
from contextlib import ExitStack
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import netCDF4
import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))


DATASET_ID = "cey_2006_2025"
REFERENCE_YEAR = 2001
YEARS = tuple(range(2006, 2026))
EXTENSION_YEARS = frozenset((*range(2006, 2015), 2025))
LEGACY_YEARS = frozenset(range(2015, 2025))
DEFAULT_EXTENSION_ROOT = Path(
    r"E:\ERA_DATA\era5_land_hourly_monthly_2006_2025\monthly_packed_0p25_landpoints"
)
DEFAULT_LEGACY_ROOT = Path(
    r"E:\ERA_DATA\era5_land_hourly_monthly_2015_2024\monthly_packed_0p25_landpoints"
)
DEFAULT_OUTPUT_ROOT = Path(r"E:\ERA_DATA\cey_2006_2025\hourly")
DEFAULT_SELECTION_PATH = Path(r"E:\ERA_DATA\cey_2006_2025\cey20_landpoint_selection.nc")
DEFAULT_MANIFEST_PATH = Path(r"E:\ERA_DATA\cey_2006_2025\hourly_manifest.json")

FEATURE_WEIGHTS = {
    "temperature_mean_c": 1.5,
    "temperature_p95_c": 0.8,
    "relative_humidity_mean_pct": 1.5,
    "relative_humidity_p90_pct": 1.0,
    "absolute_humidity_mean_g_m3": 1.0,
    "dewpoint_depression_p10_c": 0.8,
    "hours_rh_ge_80": 1.2,
    "hours_rh_ge_90": 1.0,
    "hours_dewpoint_depression_le_2c": 1.0,
    "daily_temperature_range_mean_c": 0.7,
}

FEATURE_SCALES = {
    "temperature_mean_c": 8.0,
    "temperature_p95_c": 10.0,
    "relative_humidity_mean_pct": 20.0,
    "relative_humidity_p90_pct": 20.0,
    "absolute_humidity_mean_g_m3": 8.0,
    "dewpoint_depression_p10_c": 8.0,
    "hours_rh_ge_80": 180.0,
    "hours_rh_ge_90": 120.0,
    "hours_dewpoint_depression_le_2c": 120.0,
    "daily_temperature_range_mean_c": 8.0,
}


@dataclass(frozen=True)
class SourceMonth:
    year: int
    month: int
    path: Path
    archive: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Build global CEY20 hourly landpoint product.")
    parser.add_argument("--extension-root", type=Path, default=DEFAULT_EXTENSION_ROOT)
    parser.add_argument("--legacy-root", type=Path, default=DEFAULT_LEGACY_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--selection-path", type=Path, default=DEFAULT_SELECTION_PATH)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--months", default="1-12")
    parser.add_argument("--point-chunk-size", type=int, default=1024)
    parser.add_argument("--max-points", type=int)
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    months = _parse_range(args.months)
    sources = discover_sources(args.extension_root, args.legacy_root, months)
    latitude, longitude = _load_coordinates(sources[(YEARS[0], months[0])].path, args.max_points)
    inventory = validate_inventory(sources, latitude, longitude, months, args.max_points)
    if args.inventory_only:
        print(json.dumps(inventory, indent=2))
        return

    args.output_root.mkdir(parents=True, exist_ok=True)
    args.selection_path.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    point_count = len(latitude)
    selected_year = np.zeros((len(months), point_count), dtype=np.int16)
    selection_score = np.full((len(months), point_count), np.nan, dtype=np.float32)
    output_files: list[dict[str, object]] = []
    started = time.perf_counter()

    for month_index, month in enumerate(months):
        out_path = args.output_root / f"cey20_landpoints_month{month:02d}.nc"
        if out_path.exists() and not args.force:
            resumed_year, resumed_score = _resume_month(out_path, point_count, month)
            selected_year[month_index, :] = resumed_year
            selection_score[month_index, :] = resumed_score
            output_files.append(_file_record(out_path, month))
            print(f"Resumed verified CEY20 month {month:02d} from {out_path}", flush=True)
            continue
        hour_count = _standard_month_hours(month)
        print(f"Building CEY20 month {month:02d}: {point_count} points x {hour_count} hours", flush=True)
        part_path = out_path.with_suffix(out_path.suffix + ".part")
        part_path.unlink(missing_ok=True)
        with ExitStack() as stack:
            datasets = {
                year: stack.enter_context(netCDF4.Dataset(sources[(year, month)].path))
                for year in YEARS
            }
            output = stack.enter_context(_create_month_output(part_path, latitude, longitude, month, hour_count))
            for start in range(0, point_count, args.point_chunk_size):
                end = min(start + args.point_chunk_size, point_count)
                month_data = _load_month_chunk(sources, month, start, end, datasets=datasets)
                selected_index, score = _select_representative_year(month_data)
                selected_year[month_index, start:end] = np.asarray(
                    [YEARS[index] for index in selected_index], dtype=np.int16
                )
                selection_score[month_index, start:end] = score
                _write_selected_chunk(output, month_data, selected_index, score, start, end)
                print(f"  month {month:02d}: points {end}/{point_count}", flush=True)
        part_path.replace(out_path)
        output_files.append(_file_record(out_path, month))

    _write_selection_file(
        args.selection_path, latitude, longitude, months, selected_year, selection_score
    )
    manifest = _write_manifest(
        args.manifest_path,
        args.extension_root,
        args.legacy_root,
        args.output_root,
        args.selection_path,
        months,
        point_count,
        output_files,
        inventory,
        time.perf_counter() - started,
    )
    print(json.dumps(manifest, indent=2))


def source_path(extension_root: Path, legacy_root: Path, year: int, month: int) -> SourceMonth:
    if year in EXTENSION_YEARS:
        root, archive = extension_root, "cey20_extension"
    elif year in LEGACY_YEARS:
        root, archive = legacy_root, "cey10_existing"
    else:
        raise ValueError(f"Year {year} is outside the locked 2006-2025 period")
    path = root / str(year) / f"era5_land_hourly_0p25_landpoints_{year}_{month:02d}.nc"
    return SourceMonth(year, month, path, archive)


def discover_sources(
    extension_root: Path, legacy_root: Path, months: list[int]
) -> dict[tuple[int, int], SourceMonth]:
    result = {
        (year, month): source_path(extension_root, legacy_root, year, month)
        for year in YEARS
        for month in months
    }
    missing = [str(item.path) for item in result.values() if not item.path.exists()]
    if missing:
        raise SystemExit(f"Missing {len(missing)} source files. First missing: {missing[0]}")
    return result


def validate_inventory(
    sources: dict[tuple[int, int], SourceMonth],
    latitude: np.ndarray,
    longitude: np.ndarray,
    months: list[int],
    max_points: int | None,
) -> dict[str, object]:
    expected_vars = ("temperature_c_x100", "dewpoint_c_x100", "surface_pressure_hpa_x10")
    point_count = len(latitude)
    records = []
    for year in YEARS:
        for month in months:
            item = sources[(year, month)]
            with netCDF4.Dataset(item.path) as dataset:
                missing = [name for name in expected_vars if name not in dataset.variables]
                if missing:
                    raise ValueError(f"{item.path} missing variables: {missing}")
                source_points = len(dataset.dimensions["point"])
                expected_points = point_count if max_points is None else max(point_count, source_points)
                if max_points is None and source_points != expected_points:
                    raise ValueError(f"{item.path}: point count {source_points} != {expected_points}")
                source_lat = np.asarray(dataset.variables["latitude"][:point_count], dtype=np.float32)
                source_lon = np.asarray(dataset.variables["longitude"][:point_count], dtype=np.float32)
                if not np.array_equal(source_lat, latitude) or not np.array_equal(source_lon, longitude):
                    raise ValueError(f"{item.path}: landpoint coordinates/order differ from canonical grid")
                hours = len(dataset.dimensions["time"])
                if hours < _standard_month_hours(month):
                    raise ValueError(f"{item.path}: only {hours} hours")
            records.append({
                "year": year,
                "month": month,
                "archive": item.archive,
                "path": str(item.path),
                "bytes": item.path.stat().st_size,
                "hours": hours,
            })
    return {
        "dataset_id": DATASET_ID,
        "reference_period": "2006-2025",
        "years": list(YEARS),
        "months": months,
        "source_file_count": len(records),
        "point_count": point_count,
        "coordinate_order_validated": True,
        "archive_year_assignment": {
            "cey20_extension": sorted(EXTENSION_YEARS),
            "cey10_existing": sorted(LEGACY_YEARS),
        },
        "total_source_bytes": sum(int(record["bytes"]) for record in records),
        "records": records,
    }


def _load_coordinates(path: Path, max_points: int | None) -> tuple[np.ndarray, np.ndarray]:
    with netCDF4.Dataset(path) as dataset:
        latitude = np.asarray(dataset.variables["latitude"][:], dtype=np.float32)
        longitude = np.asarray(dataset.variables["longitude"][:], dtype=np.float32)
    if max_points is not None:
        latitude, longitude = latitude[:max_points], longitude[:max_points]
    return latitude, longitude


def _read_scaled(variable: netCDF4.Variable, start: int, end: int, scale: float) -> np.ndarray:
    values = variable[:, start:end]
    if np.ma.isMaskedArray(values):
        values = values.filled(np.nan)
    return np.asarray(values, dtype=np.float32) * scale


def _load_month_chunk(
    sources: dict[tuple[int, int], SourceMonth],
    month: int,
    start: int,
    end: int,
    *,
    datasets: dict[int, netCDF4.Dataset] | None = None,
) -> dict[str, np.ndarray]:
    expected_hours = _standard_month_hours(month)
    temperature, dewpoint, pressure = [], [], []
    for year in YEARS:
        dataset = datasets[year] if datasets is not None else netCDF4.Dataset(sources[(year, month)].path)
        try:
            temperature.append(
                _read_scaled(dataset.variables["temperature_c_x100"], start, end, 0.01)[:expected_hours]
            )
            dewpoint.append(
                _read_scaled(dataset.variables["dewpoint_c_x100"], start, end, 0.01)[:expected_hours]
            )
            pressure.append(
                _read_scaled(dataset.variables["surface_pressure_hpa_x10"], start, end, 10.0)[:expected_hours]
            )
        finally:
            if datasets is None:
                dataset.close()
    return {
        "temperature_c": np.stack(temperature),
        "dewpoint_c": np.stack(dewpoint),
        "surface_pressure_pa": np.stack(pressure),
    }


def _select_representative_year(month_data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    temperature = month_data["temperature_c"]
    dewpoint = month_data["dewpoint_c"]
    rh = _relative_humidity_from_dewpoint(temperature, dewpoint).astype(np.float32)
    ah = _absolute_humidity_from_dewpoint(temperature, dewpoint).astype(np.float32)
    spread = temperature - dewpoint
    features = {
        "temperature_mean_c": np.nanmean(temperature, axis=1),
        "temperature_p95_c": np.nanpercentile(temperature, 95, axis=1),
        "relative_humidity_mean_pct": np.nanmean(rh, axis=1),
        "relative_humidity_p90_pct": np.nanpercentile(rh, 90, axis=1),
        "absolute_humidity_mean_g_m3": np.nanmean(ah, axis=1),
        "dewpoint_depression_p10_c": np.nanpercentile(spread, 10, axis=1),
        "hours_rh_ge_80": np.count_nonzero(rh >= 80.0, axis=1).astype(np.float32),
        "hours_rh_ge_90": np.count_nonzero(rh >= 90.0, axis=1).astype(np.float32),
        "hours_dewpoint_depression_le_2c": np.count_nonzero(spread <= 2.0, axis=1).astype(np.float32),
        "daily_temperature_range_mean_c": _daily_temperature_range_mean(temperature),
    }
    scores = np.zeros_like(features["temperature_mean_c"], dtype=np.float32)
    for name, values in features.items():
        scores += FEATURE_WEIGHTS[name] * np.abs(values - np.nanmean(values, axis=0, keepdims=True)) / FEATURE_SCALES[name]
    selected = np.nanargmin(scores, axis=0)
    point_index = np.arange(scores.shape[1])
    return selected.astype(np.int16), scores[selected, point_index].astype(np.float32)


def _saturation_vapor_pressure_hpa(temperature_c: np.ndarray) -> np.ndarray:
    """Same Magnus expression as hourly_cey_statistics, kept lightweight here.

    The offline builder reads hundreds of large NetCDF files and must not pull
    xarray/pandas/plotting into the process merely for these three NumPy lines.
    A regression test pins parity with the production implementation.
    """
    return 6.112 * np.exp((17.67 * temperature_c) / (temperature_c + 243.5))


def _relative_humidity_from_dewpoint(
    temperature_c: np.ndarray, dewpoint_c: np.ndarray
) -> np.ndarray:
    saturation = _saturation_vapor_pressure_hpa(temperature_c)
    vapor = _saturation_vapor_pressure_hpa(dewpoint_c)
    return np.clip(vapor / saturation * 100.0, 0.0, 100.0)


def _absolute_humidity_from_dewpoint(
    temperature_c: np.ndarray, dewpoint_c: np.ndarray
) -> np.ndarray:
    return 216.7 * _saturation_vapor_pressure_hpa(dewpoint_c) / (temperature_c + 273.15)


def _daily_temperature_range_mean(temperature: np.ndarray) -> np.ndarray:
    years, hours, points = temperature.shape
    daily = temperature[:, : (hours // 24) * 24].reshape(years, hours // 24, 24, points)
    return np.nanmean(np.nanmax(daily, axis=2) - np.nanmin(daily, axis=2), axis=1).astype(np.float32)


def _write_selected_chunk(
    output: netCDF4.Dataset,
    month_data: dict[str, np.ndarray],
    selected: np.ndarray,
    score: np.ndarray,
    start: int,
    end: int,
) -> None:
    local_points = np.arange(end - start)
    for name in ("temperature_c", "dewpoint_c", "surface_pressure_pa"):
        output.variables[name][:, start:end] = month_data[name][selected, :, local_points].T
    output.variables["selected_source_year"][start:end] = np.asarray(
        [YEARS[index] for index in selected], dtype=np.int16
    )
    output.variables["selection_score"][start:end] = score


def _create_month_output(
    path: Path, latitude: np.ndarray, longitude: np.ndarray, month: int, hour_count: int
) -> netCDF4.Dataset:
    dataset = netCDF4.Dataset(path, "w", format="NETCDF4")
    dataset.createDimension("time", hour_count)
    dataset.createDimension("point", len(latitude))
    time_var = dataset.createVariable("time", "i4", ("time",))
    lat_var = dataset.createVariable("latitude", "f4", ("point",), zlib=True, complevel=4)
    lon_var = dataset.createVariable("longitude", "f4", ("point",), zlib=True, complevel=4)
    kwargs = {"zlib": True, "complevel": 4, "shuffle": True, "chunksizes": (24, min(2048, len(latitude)))}
    temperature = dataset.createVariable("temperature_c", "f4", ("time", "point"), **kwargs)
    dewpoint = dataset.createVariable("dewpoint_c", "f4", ("time", "point"), **kwargs)
    pressure = dataset.createVariable("surface_pressure_pa", "f4", ("time", "point"), **kwargs)
    selected_year = dataset.createVariable("selected_source_year", "i2", ("point",), zlib=True, complevel=4)
    selection_score = dataset.createVariable("selection_score", "f4", ("point",), zlib=True, complevel=4)
    time_var[:] = np.arange(_month_start_hour(month), _month_start_hour(month) + hour_count, dtype=np.int32)
    lat_var[:], lon_var[:] = latitude, longitude
    time_var.units = f"hours since {REFERENCE_YEAR}-01-01 00:00:00"
    lat_var.units, lon_var.units = "degrees_north", "degrees_east"
    temperature.units, dewpoint.units, pressure.units = "degree_Celsius", "degree_Celsius", "Pa"
    selected_year.long_name = "Source year selected for this point and calendar month"
    selection_score.long_name = "Weighted normalized monthly feature distance"
    dataset.dataset_id = DATASET_ID
    dataset.reference_period = "2006-2025"
    dataset.month = month
    dataset.methodology = "Representative CEY20 month selected independently per landpoint using weighted thermodynamic features."
    dataset.feature_weights = json.dumps(FEATURE_WEIGHTS, sort_keys=True)
    dataset.feature_scales = json.dumps(FEATURE_SCALES, sort_keys=True)
    return dataset


def _resume_month(path: Path, expected_point_count: int, expected_month: int) -> tuple[np.ndarray, np.ndarray]:
    with netCDF4.Dataset(path) as dataset:
        if getattr(dataset, "dataset_id", None) != DATASET_ID:
            raise ValueError(f"{path}: dataset_id is not {DATASET_ID}")
        if int(getattr(dataset, "month", -1)) != expected_month:
            raise ValueError(f"{path}: month metadata mismatch")
        if len(dataset.dimensions["point"]) != expected_point_count:
            raise ValueError(f"{path}: point count mismatch")
        for name in (
            "temperature_c", "dewpoint_c", "surface_pressure_pa",
            "selected_source_year", "selection_score",
        ):
            if name not in dataset.variables:
                raise ValueError(f"{path}: cannot resume; missing {name}")
        selected_year = np.asarray(dataset.variables["selected_source_year"][:], dtype=np.int16)
        selection_score = np.asarray(dataset.variables["selection_score"][:], dtype=np.float32)
    if not np.all(np.isin(selected_year, YEARS)) or not np.all(np.isfinite(selection_score)):
        raise ValueError(f"{path}: incomplete selection provenance; refusing resume")
    return selected_year, selection_score


def _write_selection_file(
    path: Path,
    latitude: np.ndarray,
    longitude: np.ndarray,
    months: list[int],
    selected_year: np.ndarray,
    selection_score: np.ndarray,
) -> None:
    with netCDF4.Dataset(path, "w", format="NETCDF4") as dataset:
        dataset.createDimension("month", len(months))
        dataset.createDimension("point", len(latitude))
        dataset.createVariable("month", "i2", ("month",))[:] = months
        dataset.createVariable("latitude", "f4", ("point",), zlib=True, complevel=4)[:] = latitude
        dataset.createVariable("longitude", "f4", ("point",), zlib=True, complevel=4)[:] = longitude
        dataset.createVariable("selected_year", "i2", ("month", "point"), zlib=True, complevel=4)[:] = selected_year
        dataset.createVariable("selection_score", "f4", ("month", "point"), zlib=True, complevel=4)[:] = selection_score
        dataset.dataset_id = DATASET_ID
        dataset.reference_period = "2006-2025"
        dataset.methodology = "Representative CEY20 source year selected independently for each month and landpoint."
        dataset.feature_weights = json.dumps(FEATURE_WEIGHTS, sort_keys=True)
        dataset.feature_scales = json.dumps(FEATURE_SCALES, sort_keys=True)


def _file_record(path: Path, month: int) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b""):
            digest.update(chunk)
    return {"month": month, "path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def _write_manifest(
    path: Path,
    extension_root: Path,
    legacy_root: Path,
    output_root: Path,
    selection_path: Path,
    months: list[int],
    point_count: int,
    output_files: list[dict[str, object]],
    inventory: dict[str, object],
    build_seconds: float,
) -> dict[str, object]:
    manifest = {
        "dataset_id": DATASET_ID,
        "label": "Climetry CEY20 hourly landpoint product",
        "reference_period": "2006-2025",
        "source_roots": {"extension": str(extension_root), "legacy": str(legacy_root)},
        "output_root": str(output_root),
        "selection_file": str(selection_path),
        "point_count": point_count,
        "months": months,
        "nominal_annual_hours": 8760,
        "variables": ["temperature_c", "dewpoint_c", "surface_pressure_pa"],
        "derived_on_query": ["relative_humidity_pct", "absolute_humidity_g_m3", "dewpoint_depression_c"],
        "selection_method": "Weighted monthly thermodynamic feature matching against the 2006-2025 distribution per landpoint.",
        "feature_weights": FEATURE_WEIGHTS,
        "feature_scales": FEATURE_SCALES,
        "inventory": {key: value for key, value in inventory.items() if key != "records"},
        "files": output_files,
        "total_bytes": sum(int(item["bytes"]) for item in output_files) + selection_path.stat().st_size,
        "build_seconds": round(build_seconds, 3),
        "r2_prefix": "private/cey/cey_2006_2025/hourly_landpoints_v2/",
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _standard_month_hours(month: int) -> int:
    return calendar.monthrange(REFERENCE_YEAR, month)[1] * 24


def _month_start_hour(month: int) -> int:
    return sum(_standard_month_hours(item) for item in range(1, month))


def _parse_range(value: str) -> list[int]:
    result: list[int] = []
    for part in value.split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            result.extend(range(int(start), int(end) + 1))
        elif part.strip():
            result.append(int(part))
    result = sorted(set(result))
    if not result or any(month < 1 or month > 12 for month in result):
        raise ValueError(f"Invalid month selection: {value}")
    return result


if __name__ == "__main__":
    main()
