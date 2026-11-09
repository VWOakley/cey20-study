"""AUTH-003 S3 freeze (read-only): resolve the 14 points once, inventory inputs, check eligibility.
Writes 03-freeze.json. Uses the production builder's source discovery; computes no outcomes."""
import calendar
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import netCDF4
import numpy as np

REPO = Path(sys.argv[1]); OUT = Path(sys.argv[2])
sys.path.insert(0, str(REPO / 'backend')); sys.path.insert(0, str(REPO / 'backend/scripts'))
import build_global_cey20_landpoint_dataset as B  # noqa: E402
import build_city_cey10_from_era5_land_hourly as C  # noqa: E402

POINTS = [('Singapore', 1.3521, 103.8198), ('Mumbai', 19.0760, 72.8777), ('Dubai', 25.2048, 55.2708),
          ('Houston', 29.7604, -95.3698), ('Frankfurt', 50.1109, 8.6821), ('London', 51.5074, -0.1278),
          ('Seattle', 47.6062, -122.3321), ('San Francisco', 37.7749, -122.4194), ('Helsinki', 60.1699, 24.9384),
          ('Fairbanks', 64.8378, -147.7164), ('Chicago', 41.8781, -87.6298), ('Phoenix', 33.4484, -112.0740),
          ('Denver', 39.7392, -104.9903), ('Quito', -0.1807, -78.4678)]
sha = lambda b: hashlib.sha256(b).hexdigest()
proto = REPO / 'docs/research/auth003-tmy/03-study-protocol.md'
code_sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip()
sources = B.discover_sources(B.DEFAULT_EXTENSION_ROOT, B.DEFAULT_LEGACY_ROOT, list(range(1, 13)))
sample = sources[(B.YEARS[0], 1)].path
resolved = []
for name, lat, lon in POINTS:
    cp = C._resolve_city_point(sample, name, name, lat, lon)
    resolved.append(dict(name=name, requested_lat=lat, requested_lon=lon, point_index=cp.point_index,
                         grid_lat=round(cp.grid_lat, 4), grid_lon=round(cp.grid_lon, 4), distance_km=round(cp.distance_km, 2)))
idx = sorted({r['point_index'] for r in resolved})
inventory, problems = [], {r['name']: [] for r in resolved}
pos = {i: k for k, i in enumerate(idx)}
for (year, month), src in sorted(sources.items()):
    st = src.path.stat()
    with netCDF4.Dataset(src.path) as d:
        need = calendar.monthrange(B.REFERENCE_YEAR, month)[1] * 24
        tv = np.asarray(d.variables['time'][:need], dtype=np.int64)
        start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp())
        time_ok = tv.size == need and tv[0] == start and bool(np.all(np.diff(tv) == 3600))
        t = d.variables['temperature_c_x100'][:need, idx]; td = d.variables['dewpoint_c_x100'][:need, idx]
        tm = np.ma.getmaskarray(t) | np.ma.getmaskarray(td)
    inventory.append(dict(year=year, month=month, archive=src.archive, path=str(src.path), bytes=st.st_size,
                          mtime_utc=datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec='seconds'), time_ok=time_ok))
    for r in resolved:
        k = pos[r['point_index']]
        bad = int(tm[:, k].sum())
        if bad or not time_ok:
            problems[r['name']].append(dict(year=year, month=month, masked_hours=bad, time_ok=time_ok))
for r in resolved:
    r['eligible'] = not problems[r['name']]
    r['problems'] = problems[r['name']][:20]
manifests = {}
for root in (B.DEFAULT_EXTENSION_ROOT.parent, B.DEFAULT_LEGACY_ROOT.parent):
    m = root / 'manifest.json'
    if m.exists():
        manifests[str(m)] = sha(m.read_bytes())
inv_digest = sha(json.dumps(inventory, sort_keys=True).encode())
freeze = dict(schema='auth003-s3-freeze-v1', frozen_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
              code_sha=code_sha, builder='backend/scripts/build_global_cey20_landpoint_dataset.py',
              selection_identity=dict(years=[B.YEARS[0], B.YEARS[-1]], feature_weights=B.FEATURE_WEIGHTS, feature_scales=B.FEATURE_SCALES,
                                      reference_year=B.REFERENCE_YEAR, grid='0.25 degree packed ERA5-Land land points'),
              protocol_file='docs/research/auth003-tmy/03-study-protocol.md', protocol_sha256=sha(proto.read_bytes()),
              source_manifests_sha256=manifests, input_inventory_sha256=inv_digest, input_files=len(inventory),
              inputs_time_ok=sum(i['time_ok'] for i in inventory), points=resolved, input_inventory=inventory,
              note='Read-only freeze. No outcome (selection, deviation, exposure) was computed.')
OUT.write_text(json.dumps(freeze, indent=1), encoding='utf-8')
print(json.dumps(dict(code_sha=code_sha, files=len(inventory), time_ok=freeze['inputs_time_ok'],
                      points=[(r['name'], r['point_index'], r['distance_km'], r['eligible']) for r in resolved]), indent=1))
