# S4 part 2 results: external comparison in California (run3)

Status: draft for review. Descriptive results under the frozen specification `08-external-comparison-spec.md` (r3)
with amendments A1, A2, A2.1, A3 and A3.1.

## What was run

`auth003_s4ext_compare.py` with pin `08-s4ext-pin-A3_1.json` (code `research/AUTH-003-S10-california @ 5369f2e4`),
input inventory `08-input-inventory-freeze.json`, S10 build 8, the frozen ERA5-Land inputs of `03-freeze.json`, on
2026-11-07 13:18–14:38 UTC. Output `E:/40_work/AUTH-003_external-comparison/results/run3`, copied here unchanged
(`manifest.json` records the SHA-256 of every output; `.gitattributes` keeps the bytes).

**Run history (amendment A3).** run1 (10:14–11:44 UTC) computed the same values but lost the candidate label in
`annual.csv` and produced an empty annual summary. run2 repaired the label and stopped while writing
`summary.json` (numpy integer). run3 completed. All three runs used the same inputs, gates and methods; run1 and run2
stay on E: unchanged. Acceptance check `verify_a3.py` (output `verify_a3_run3.txt`): the station, monthly,
decomposition and convention files are byte-identical to run1; every annual row equals run1, with labels equal to
the order reconstruction; the annual summary is recomputed from `annual.csv` and the monthly summary equals run1.
The operator was told the preliminary run1 numbers (reconstructed labels) before run3; they are identical.

## Sample

- 41 eligible NOAA ISD stations (feasibility funnel in `08-feasibility/`), 15–19 usable years per calendar month
  (minimum over months: 19 years at 19 stations, 18 at 9, 15–17 at 13).
- Köppen (Beck et al. 2023): BSh 18, BSk 6, Csa 5, BWh 5, Csb 4, Dsb 2, BWk 1.
- Grid match: 40 stations have an S10 point within 25 km (median 11.4 km, maximum 18.3 km; 28 distinct points).
  Catalina (island, 41.4 km) has no point: C1 and C2 are unavailable there; C3 and C4 are available at all 41.
- The common subset (all five candidates available) is these 40 stations.

## Candidate conventions (`conventions.csv`)

- All 82 typical years: 8,760 UTC hours, no duplicates, no gaps, no 29 February.
- C3 PVGIS-TMY 5.3 (PVGIS-ERA5): selected months from 2006–2023; RH supplied, no RH outside 0–100 %.
- C4 NSRDB GOES TMY v4.0.0 (`tmy-2024`): UTC, all rows at minute 30. Source years 1998–2024; 157 of 492
  station-months come from before 2006, i.e. outside the study period. Supplied RH and RH computed from T and Td
  agree within 0.36 percentage points at every station.

## Station reference

| Exposure | median reference hours (min–max) | missing-data bound width, median / max | hour-of-day sensitivity, median / max |
|---|---|---|---|
| RH ≥ 80 % | 2138 (312–4128) | 4.2 % / 51 % | 0.11 % / 0.60 % |
| RH ≥ 90 % | 501 (81–2176) | 15.9 % / 168 % | 0.11 % / 0.88 % |
| T − Td ≤ 2 °C | 895 (159–2605) | 9.5 % / 97 % | 0.11 % / 0.78 % |

Bound width = (all missing hours as events − all as non-events) / primary estimate. The hour-of-day sensitivity was
available at all 41 stations and changes the reference by less than 1 %. The bounds are wide at a few stations. For every candidate and exposure, the counts within 5 % differ by at most three across the lower-bound, primary and
upper-bound references; for C1 they are 5 / 4 / 3 (RH ≥ 80 %), 2 / 2 / 2 (RH ≥ 90 %) and 2 / 2 / 3 (T − Td ≤ 2 °C) of 40
(`report_tables.md`). The bounds cover missing hours within usable months, not excluded months or years; neither
estimator repairs weather-dependent missingness. Station-year-month completeness for all 68 candidate stations is in
`station_completeness.csv`.

## Annual exposure hours (transferred 5 % threshold)

Counts of stations within 5 %, 10 %, 20 % of the station reference; "under" = candidate below the reference.
Full tables, including the common subset, annual worst cases and equal weighting per distinct S10 point, in
`report_tables.md`. For the distinct-point summaries (aggregated-point checks), the annual summary averages the
station-relative differences (candidate − reference) / reference of the stations sharing a point and compares the
absolute mean with 5 %; the monthly summary averages their signed differences in °C or pp. Averaging can conceal
opposing departures of stations sharing a point.

| Candidate | RH ≥ 80 %: ≤5 / ≤10 / ≤20 %, under, median abs rel | RH ≥ 90 % | T − Td ≤ 2 °C |
|---|---|---|---|
| C1 CEY20 v2 (n 40) | 4 / 9 / 15, 21, 25 % | 2 / 4 / 8, 16, 55 % | 2 / 5 / 9, 18, 49 % |
| C2_full ERA5-Land 2006–2025 (n 40) | 3 / 7 / 16, 19, 28 % | 1 / 3 / 7, 16, 47 % | 1 / 5 / 11, 17, 46 % |
| C2_matched (n 40) | 4 / 7 / 16, 19, 26 % | 1 / 4 / 8, 16, 48 % | 2 / 4 / 10, 17, 48 % |
| C3 PVGIS-TMY (n 41) | 8 / 10 / 15, 18, 30 % | 2 / 3 / 8, 16, 52 % | 4 / 7 / 9, 18, 50 % |
| C4 NSRDB TMY (n 41) | 2 / 5 / 11, 31, 42 % | 4 / 5 / 10, 29, 59 % | 2 / 5 / 8, 26, 51 % |

Median signed relative differences: C1 −1.7 %, +16 %, +16 %; C2_full +3.9 %, +26 %, +20 %; C3 +6.3 %, +22 %,
+21 %; C4 −26 %, −49 %, −26 %. C1, C2 and C3 scatter on both sides of the reference; C4 is drier at 26–31 of 41
stations. Figure `fig_s4ext_rh80.{pdf,png}` shows the signed RH ≥ 80 % differences per station. The largest annual
relative differences are at John Wayne Airport (Orange County) for C1, C2 and C3 (+110 to +150 % for RH ≥ 80 %,
+560 to +790 % for the two rarer exposures against references of 196 and 328 h) and at Palmdale (Plant 42) for C4
(+150 %, +486 %, +315 %).

## Monthly means (common subset, 480 station-months)

| Candidate | T within 0.5 °C | RH within 2 pp | median signed dT / dRH | median abs dT / dRH |
|---|---|---|---|---|
| C1 CEY20 v2 | 125 | 100 | +0.01 °C / +0.65 pp | 1.07 °C / 4.6 pp |
| C2_full | 137 | 118 | +0.02 / +0.14 | 0.89 / 4.8 |
| C2_matched | 138 | 113 | +0.00 / +0.01 | 0.91 / 4.7 |
| C3 PVGIS-TMY | 112 | 83 | −0.15 / +0.32 | 1.30 / 5.8 |
| C4 NSRDB TMY | 105 | 86 | +1.09 / −5.06 | 1.28 / 7.4 |

No candidate meets all 12 monthly checks at any station. Largest absolute monthly T departures by candidate range
from 4.97 to 6.52 °C: the C1/C2 cases are negative at Mammoth Yosemite, C3 is negative at Bishop, and C4 is positive
at Oxnard (+6.34 °C). Largest absolute monthly RH departures include Santa Barbara (−24.13 pp for C1), Van Nuys
(+31.31 pp for C3) and Oxnard (−32.24 pp for C4). Failures by direction (all available stations): C1, C2 and C3 fail
in both directions in similar numbers; C4 fails mostly too warm (315 of 384 T failures) and too dry (301 of 406 RH
failures). With equal weight per distinct S10 point (336 point-months), the T / RH checks are met at 91 / 69 (C1),
100 / 81 (C2_full), 76 / 55 (C3) and 79 / 57 (C4) point-months. All-station monthly results for C3 and C4 (492
station-months) are in `report_tables.md` and `summary.json`.

## Decomposition (spec section 6)

C1 − station = (C1 − C2_full) + (C2_full − station), annual hours relative to the station reference, 40 stations:

The identity holds for signed differences per station; the table gives median absolute magnitudes, which do not
add up. Median signed values: C1 − C2_full −1.4 %, −7.0 %, −3.9 %; C2_full − station +3.9 %, +26 %, +20 %.

| Exposure | median abs: C1 − station / C1 − C2_full / C2_full − station | stations where abs(C1 − C2_full) < abs(C2_full − station) |
|---|---|---|
| RH ≥ 80 % | 25 % / 2.1 % / 28 % | 37 of 40 |
| RH ≥ 90 % | 55 % / 7.0 % / 47 % | 39 of 40 |
| T − Td ≤ 2 °C | 49 % / 4.3 % / 46 % | 37 of 40 |
| monthly T (°C) | 1.07 / 0.33 / 0.89 | 366 of 480 |
| monthly RH (pp) | 4.6 / 0.84 / 4.8 | 402 of 480 |

The C2_full − station term combines reanalysis discrepancy, spatial representativeness (0.25° product point, nearest native ERA5-Land sample, up to 18 km
from the station), observational uncertainty and reference-support differences; it is not an isolated estimate of
reanalysis error. C2_matched and C2_full have similar aggregate diagnostic summaries. This alone does not quantify
the contribution of observation sampling: their difference combines usable-year selection and within-month
observation sampling, and requires station-level assessment.

## Reading (spec wording)

At 36 of 40 eligible stations (RH ≥ 80 %), 38 (RH ≥ 90 %) and 38 (T − Td ≤ 2 °C), CEY20 exceeded the transferred
5 % threshold against the estimated station reference. This discrepancy includes source–station representativeness,
observational and sampling effects, as well as departure of the selected year from its source climatology. The
complete 20-year ERA5-Land series at the same points exceeds it at a similar number of stations (37, 39, 39). The
departure of the selected year from its source climatology is smaller in absolute magnitude than the
source-climatology–station discrepancy at 37–39 of 40 stations for each annual exposure metric. This identifies the
larger discrepancy term without isolating its physical or observational causes. The
typical years compared are delivered products with different source periods (C1 2006–2025, C3 2006–2023,
C4 1998–2024), source data and spatial support; differences between them are not attributed to their selection
algorithms, and no ranking is claimed beyond the counts.

## Height of the matched points (spec 2.4, `elevation_proxy.py` → `elevation_proxy.csv`)

The frozen ERA5-Land inputs contain no height variable. The S10 points are packed ERA5-Land landpoints (coordinates
checked against the packed files); their surface pressure is ERA5-Land `sp` (packed as hPa × 10). The height is
therefore labelled a **pressure-derived proxy**, not terrain elevation: hypsometric equation with the 2006–2025 mean
of ln(sp) and the mean surface virtual temperature (from T, Td and sp), a 6.5 K/km layer correction and 1013.25 hPa
at sea level (all 175,320 hours per point; packing, coordinates, hourly UTC time axis and physical ranges checked in
every source file). The ICAO standard-atmosphere formula on the mean pressure gives heights up to 3.2 % lower
(`proxy_height_isa_m`); this is a sensitivity to another atmospheric assumption, not a validation. The proxy's
absolute error has not been quantified. Reference-pressure differences alone can produce offsets of several tens of
metres (approximately 8–9 m per hPa near sea level); additional uncertainty arises from the assumed layer temperature
and the representation of the model surface. The approximately 20 m proxy at the shared Hanford/Visalia point should
not be interpreted as measured terrain elevation.

- Station elevation minus proxy height, 40 stations sharing 28 points: median −93 m (proxy heights exceed station
  elevations at most matched stations).
- Two station–proxy differences exceed 300 m in magnitude: Bishop (−514 m) and Mammoth Yosemite (−391 m), where proxy
  heights exceed station elevations (`proxy_abs_difference_gt_300m`). This is an auxiliary proxy comparison, not the
  terrain-elevation flag specified in section 2.4, which cannot be assessed from these inputs
  (`terrain_elevation_flag` = not assessed). Next largest: Santa Barbara (−299.8 m), Burbank (−265 m), Sandberg
  (+240 m). Catalina has no matched point ("unknown").
- Exploratory, not specified in advance: across 40 station pairs sharing 28 source points, the height difference is
  positively associated with the equally weighted mean of each station's 12 monthly signed dT (Pearson r = 0.39 for
  C1, 0.40 for C2_full; OLS slope 0.34 K per 100 m); Bishop and Mammoth have the two most negative mean dT (−2.4 and
  −2.6 °C for C1). The association does not identify an elevation contribution: coastal setting, geography and shared
  source points confound it. Nothing was adjusted or excluded.
- Review: Codex chain `auth003-s4ext-elevation-codex-05cf5b0107d2` (GO WITH CHANGES, applied).

## Not covered here (open)

- Spec 7: S10 internal diagnostics for C1 at the matched points against the complete ERA5-Land climatology.
- Spec 9: product terms and citations for NOAA ISD, PVGIS and NSRDB must be verified before publication.
- Reporting completeness. Present: every station/metric result (`annual.csv`), every monthly result with its signed
  difference (`monthly.csv`), annual and monthly worst cases, failure directions, all-station and common-subset
  results, distinct-point summaries (`report_tables.md`), station-year-month completeness
  (`station_completeness.csv`). Not present: completeness by UTC hour of day (only its effect, the hour-of-day
  sensitivity, is reported).

## Files

`stations.csv`, `annual.csv`, `monthly.csv`, `decomposition.csv`, `conventions.csv`, `summary.json`, `manifest.json`
(run3, unchanged); `report_tables.py` → `report_tables.md`; `make_fig_rh80.py` → `fig_s4ext_rh80.{pdf,png}`;
`verify_a3.py` → `verify_a3_run3.txt`; `elevation_proxy.py` → `elevation_proxy.csv`; `station_completeness.csv` (copy of the prepared completeness record, all 68
candidate stations).
