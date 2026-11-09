# Amendment A2 to 08-external-comparison-spec.md (r3): frozen stage-B products

Date: 2026-11-07, after the outcome-blind feasibility (41 eligible stations) and before any typical-year time series
was retrieved for the comparison. Resolved per spec section 4 ("Product resolution and freeze").

## C3 PVGIS-TMY
- Endpoint `https://re.jrc.ec.europa.eu/api/v5_3/tmy`, parameters `lat`, `lon` (station coordinates of the used
  segment), `raddatabase=PVGIS-ERA5`, `startyear=2006`, `endyear=2023`, `outputformat=json`.
- Discovery (one request at 34.2, −118.36 without years; `raw/discovery/`): database PVGIS-ERA5, meteorological
  variables from **ERA5** (not ERA5-Land), `year_min` 2005, `year_max` 2023; hourly `time(UTC)` stamps; variables
  `T2m` (°C) and `RH` (%), plus `months_selected` (source year per month, recorded as provenance). The request
  period 2006–2023 is the overlap with the study period; 2024–2025 are not available in this database.
- RH supplied, Td derived by Magnus inversion for the dew-point-depression diagnostic only (spec section 4).

## C4 NSRDB GOES TMY v4.0.0
- NREL is now served under the host `developer.nlr.gov` (`developer.nrel.gov` no longer resolves).
- Endpoint `https://developer.nlr.gov/api/nsrdb/v2/solar/nsrdb-GOES-tmy-v4-0-0-download.csv` (single point, single
  name per request), parameters `wkt=POINT(lon lat)` (nearest site), `names=tmy-2024` (explicit; latest listed),
  `attributes=air_temperature,dew_point,relative_humidity,tmy_year`, `utc=true`, `leap_day=false`, `interval=60`,
  `email` and `api_key` from the operator's secrets file (never logged or stored; the inventory records the
  endpoint and non-sensitive parameters only).
- Documentation: GOES-based, 4 km, hourly, from 1998; timestamps in UTC with `utc=true`; rate limit 1 CSV request per
  second. The returned header metadata (site location, elevation, time zone) and `tmy_year` are recorded.
- The returned time step is verified to be 60 min and 8,760 rows; anything else is reported, not repaired.

No other change to the specification.

## A2.1 (same day, before any NSRDB file was retrieved)

The NSRDB API rejects the attribute `tmy_year` (HTTP 400: not in its list of accepted attributes, although the
documentation page lists it). The request uses `attributes=air_temperature,dew_point,relative_humidity`; the source
year of each month is taken from the `Year` column of the returned rows. No other change.
