"""Spec 2.4: pressure-derived height proxy of the matched S10 points, compared with the ISD station elevations.

Provenance: the S10 points are packed ERA5-Land landpoints (product_point_index = landpoint index of the packed monthly
files); their surface pressure is the ERA5-Land variable "sp" packed as hPa x 10 (int16), the same frozen 2006-2025
inputs as C2. ERA5-Land has no height variable in these inputs, so the height is a proxy, not terrain elevation:

  hypsometric: z = A * mean(Tv_surface) * L / (1 - A * GAMMA * L / 2), A = Rd / g, L = ln(p0) - mean ln(sp), from the layer temperature
               Tv_layer = mean surface virtual temperature + GAMMA * z / 2
  isa:         z = 44330.77 m * (1 - (mean sp / p0) ** 0.190263)   (ICAO standard atmosphere; sensitivity, not validation)

with p0 = 1013.25 hPa at sea level (about 8-9 m per hPa near sea level). The proxy is not terrain elevation, so the
section 2.4 terrain-elevation flag stays "not assessed"; proxy_abs_difference_gt_300m is an auxiliary column only.
Checks per source file: packing attributes, coordinates at every point, complete hourly UTC time axis, positive
pressure. Reads E: only, writes elevation_proxy.csv next to this script.
"""
import calendar
import csv
import datetime as dt
import hashlib
import math
from pathlib import Path

import netCDF4
import numpy as np

D = Path(__file__).resolve().parent
S10 = Path(r"E:\ERA_DATA\auth003_s10_california_v1_build8\cey20_v2_california_points.nc")
S10_SHA256 = "2c3bd91f33b0ff048edd52a59b504b6c113c93d1ecb6c97981c122ffd29da3bb"     # manifest.json of run3
EXT = Path(r"E:\ERA_DATA\era5_land_hourly_monthly_2006_2025\monthly_packed_0p25_landpoints")
LEG = Path(r"E:\ERA_DATA\era5_land_hourly_monthly_2015_2024\monthly_packed_0p25_landpoints")
YEARS, BLOCK = range(2006, 2026), 8192          # BLOCK = point chunk length of the packed files
RD, G, GAMMA, P0, FLAG_M = 287.05, 9.80665, 0.0065, 1013.25, 300.0


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def source(y, m):
    root = LEG if 2015 <= y <= 2024 else EXT
    return root / str(y) / f"era5_land_hourly_0p25_landpoints_{y}_{m:02d}.nc"


PACKING = ("surface_pressure_hpa_x10", "temperature_c_x100", "dewpoint_c_x100")


def check_file(d, path, y, m, cols, pidx, plat, plon):
    for name in PACKING:
        v = d[name]
        if v.dtype != np.int16 or int(v._FillValue) != -32768 or {"scale_factor", "add_offset"} & set(v.ncattrs()):
            raise SystemExit(f"{path}: unexpected packing of {name}")
    time = np.asarray(d["time"][:], np.int64)
    start = int(dt.datetime(y, m, 1, tzinfo=dt.timezone.utc).timestamp())
    if d["time"].units != "seconds since 1970-01-01" or len(time) != 24 * calendar.monthrange(y, m)[1]             or time[0] != start or np.any(np.diff(time) != 3600):
        raise SystemExit(f"{path}: time axis is not the complete hourly UTC month")
    for p in cols:
        j = pidx.index(p)
        if abs(float(d["latitude"][p]) - plat[j]) > 1e-4 or abs((float(d["longitude"][p]) - plon[j] + 180) % 360 - 180) > 1e-4:
            raise SystemExit(f"{path} point {p}: packed coordinates differ from S10")


def unpack(v, cols):
    a = v[:, cols[0]:cols[-1] + 1]
    a = np.ma.filled(a, -32768).astype(np.float64)[:, [c - cols[0] for c in cols]]
    a[a == -32768] = np.nan
    return a


def main():
    if sha256(S10) != S10_SHA256:
        raise SystemExit("S10 dataset differs from the run3 manifest")
    stations = list(csv.DictReader(open(D / "stations.csv", encoding="utf-8")))
    with netCDF4.Dataset(S10) as d:
        pidx = np.asarray(d["product_point_index"][:]).tolist()
        plat, plon = np.asarray(d["latitude"][:], np.float64), np.asarray(d["longitude"][:], np.float64)
    points = sorted({int(s["s10_point"]) for s in stations if s["s10_point"]})
    n = len(points)
    sum_lnp, sum_tv, sum_p, count = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    blocks = {}
    for i, p in enumerate(points):
        blocks.setdefault(p // BLOCK, []).append((i, p))
    for y in YEARS:
        for m in range(1, 13):
            with netCDF4.Dataset(source(y, m)) as d:
                check_file(d, source(y, m), y, m, points, pidx, plat, plon)
                for members in blocks.values():
                    cols = [p for _, p in members]
                    sp = unpack(d["surface_pressure_hpa_x10"], cols) / 10.0
                    t = unpack(d["temperature_c_x100"], cols) / 100.0
                    td = unpack(d["dewpoint_c_x100"], cols) / 100.0
                    e = 6.112 * np.exp(17.67 * td / (td + 243.5))
                    q = 0.622 * e / (sp - 0.378 * e)                 # specific humidity
                    tv = (t + 273.15) * (1 + 0.608 * q)
                    if np.any(sp <= 0) or np.any((q < 0) | (q > 0.05)):
                        raise SystemExit(f"{source(y, m)}: non-physical pressure or humidity")
                    ok = np.isfinite(sp) & np.isfinite(tv)
                    for k, (i, _) in enumerate(members):
                        o = ok[:, k]
                        sum_lnp[i] += np.log(sp[o, k]).sum()
                        sum_tv[i] += tv[o, k].sum()
                        sum_p[i] += sp[o, k].sum()
                        count[i] += o.sum()
        print(f"{y} read", flush=True)
    expected = sum(24 * (366 if calendar.isleap(y) else 365) for y in YEARS)
    if np.any(count != expected):
        raise SystemExit(f"incomplete hours: {count.tolist()} != {expected}")
    proxy = {}
    for i, p in enumerate(points):
        lnp, tv, pm = sum_lnp[i] / count[i], sum_tv[i] / count[i], sum_p[i] / count[i]
        a, lg = RD / G, math.log(P0) - lnp
        z = a * tv * lg / (1 - a * GAMMA * lg / 2)
        proxy[p] = {"hours": int(count[i]), "mean_sp_hpa": pm, "mean_tv_c": tv - 273.15, "z_hyps": z,
                    "z_isa": 44330.77 * (1 - (pm / P0) ** 0.190263)}
    rows = []
    for s in stations:
        r = {"station_id": s["station_id"], "name": s["name"], "station_elevation_m": s["elevation_m"],
             "s10_point": s["s10_point"], "s10_distance_km": s["s10_distance_km"], "height_label": "unknown",
             "terrain_elevation_flag": "not assessed: comparable source terrain elevation unavailable"}
        if s["s10_point"]:
            q = proxy[int(s["s10_point"])]
            dz = float(s["elevation_m"]) - q["z_hyps"]
            r.update(height_label="pressure-derived proxy", proxy_hours=q["hours"], mean_sp_hpa=round(q["mean_sp_hpa"], 2),
                     mean_tv_c=round(q["mean_tv_c"], 2), proxy_height_hypsometric_m=round(q["z_hyps"], 1),
                     proxy_height_isa_m=round(q["z_isa"], 1), station_minus_proxy_m=round(dz, 1), proxy_abs_difference_gt_300m=abs(dz) > FLAG_M)
        rows.append(r)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(D / "elevation_proxy.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
