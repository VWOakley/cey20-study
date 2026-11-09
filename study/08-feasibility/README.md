# S4 part 2, stage A feasibility (outcome-blind), 2026-11-07

Input: 68 NOAA ISD candidate stations inside California (`raw/candidates_isd.csv`), Global Hourly 2006–2025 from the
NOAA Open Data bucket (amendment A1): 1,275 station-year files downloaded, 85 not available (8.29 GB). Processing:
`tools/auth003_ext_isd_prepare.py` (commit f90b5101), rules of spec r3 section 2. No candidate (CEY20, ERA5-Land,
PVGIS, NSRDB) was read and no comparison metric was computed.

## Funnel

| Step | Stations |
|---|---:|
| Candidates | 68 |
| No paired T/Td hour (no usable file) | 5 |
| A calendar month with < 15 usable years (completeness ≥ 0.80) | 22 |
| **Eligible** | **41** |

The maximum number of usable years per calendar month is 19 at every station (one of the 20 years is incomplete or
missing everywhere); 34 of the 41 eligible stations have ≥ 16 usable years in every month.

## Location changes (spec 2.2)

Three stations change coordinates in the data at 2021-01-01, all on the same date:

| Station | 2006–2020 | 2021– | Shift |
|---|---|---|---|
| Chino Airport (722899-03179) | 33.97528, −117.63611, 198.1 m | 33.97563, −117.62487, 193.9 m | ≈ 1.0 km |
| Ontario Intl (747040-03102) | 34.05611, −117.60028, 289.3 m | 34.05314, −117.57689, 281.6 m | ≈ 2.2 km |
| North Island NAS (722906-93112) | 32.7, −117.2, 7.9 m | 32.69219, −117.20983, 4.4 m | ≈ 1.3 km |

The common date and the change from rounded to precise coordinates (North Island) suggest a metadata revision rather
than physical relocations, but this is unresolved. The frozen rule is applied unchanged: records are split at the
change, the longest segment (2006–2020) is used, and the station is kept only if that segment is eligible on its own.
Result: Chino eligible (15 usable years in the weakest month); Ontario and North Island excluded (14). This treatment
is fixed now, before any candidate metric.

## Coverage

The 41 eligible stations are mostly airports and military fields in southern California, the Central Valley and the
Mojave; a few are mountain sites (Alturas, Lake Tahoe, Mammoth Yosemite, Bishop, Sandberg). The candidate list
(`weather_station_validation/station_metadata.csv`) contains no station in the San Francisco Bay Area, Sacramento or
the north coast, so these regions are not represented. Results describe this station sample only.
