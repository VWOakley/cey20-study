"""Read-only: effective CEY20 feature influence w_k * sigma_k(p) / s_k at the 8 city points, using the builder's own code."""
import json
import sys
from pathlib import Path

import netCDF4
import numpy as np

REPO = Path(sys.argv[1]); OUT = Path(sys.argv[2])
sys.path.insert(0, str(REPO / 'backend'))
sys.path.insert(0, str(REPO / 'backend/scripts'))
import build_global_cey20_landpoint_dataset as B  # noqa: E402
import build_city_cey10_from_era5_land_hourly as C  # noqa: E402

sources = B.discover_sources(B.DEFAULT_EXTENSION_ROOT, B.DEFAULT_LEGACY_ROOT, list(range(1, 13)))
sample = sources[(B.YEARS[0], 1)].path
report = {}
for slug, (name, lat, lon) in C.CITY_POINTS.items():
    idx = C._resolve_city_point(sample, slug, name, lat, lon).point_index
    per_month = []
    for month in range(1, 13):
        data = B._load_month_chunk(sources, month, idx, idx + 1)
        t, td = data['temperature_c'], data['dewpoint_c']
        rh = B._relative_humidity_from_dewpoint(t, td); ah = B._absolute_humidity_from_dewpoint(t, td); d = t - td
        f = {'temperature_mean_c': np.nanmean(t, 1), 'temperature_p95_c': np.nanpercentile(t, 95, 1),
             'relative_humidity_mean_pct': np.nanmean(rh, 1), 'relative_humidity_p90_pct': np.nanpercentile(rh, 90, 1),
             'absolute_humidity_mean_g_m3': np.nanmean(ah, 1), 'dewpoint_depression_p10_c': np.nanpercentile(d, 10, 1),
             'hours_rh_ge_80': np.count_nonzero(rh >= 80, 1).astype(float), 'hours_rh_ge_90': np.count_nonzero(rh >= 90, 1).astype(float),
             'hours_dewpoint_depression_le_2c': np.count_nonzero(d <= 2, 1).astype(float),
             'daily_temperature_range_mean_c': B._daily_temperature_range_mean(t)}
        sel, _ = B._select_representative_year(data)
        per_month.append({k: float(B.FEATURE_WEIGHTS[k] * np.nanstd(v[:, 0]) / B.FEATURE_SCALES[k]) for k, v in f.items()})
    eff = {k: float(np.mean([m[k] for m in per_month])) for k in B.FEATURE_WEIGHTS}
    tot = sum(eff.values())
    report[slug] = {k: round(100 * v / tot, 1) for k, v in eff.items()}
    print(slug, json.dumps(report[slug]), flush=True)
nominal = {k: round(100 * w / sum(B.FEATURE_WEIGHTS.values()), 1) for k, w in B.FEATURE_WEIGHTS.items()}
print('nominal', json.dumps(nominal))
(OUT / 'cey20_effective_weights.json').write_text(json.dumps(dict(nominal_share_pct=nominal, effective_share_pct=report), indent=1))
