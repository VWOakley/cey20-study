# AUTH-003 S4 part 2: external comparison in California (specification, pre-download)

Status: DRAFT r3, 2026-11-07, revised after Codex review (chain auth003-extspec-codex-7b53770b657f, CHANGES
REQUESTED) and re-check (chain auth003-extspec-recheck-codex-69e216f76738: five findings closed, five partially
closed with replacement wording, applied in r3; "suitable for approval of the defined discovery and retrieval
stages"). Nothing has been downloaded or computed. Downloads start only after the
operator approves section 10. The approved specification is frozen (SHA-256 recorded) before any download; the
retrieved-input inventory is frozen separately before any candidate metric is computed (section 8). Later changes
are versioned amendments with reasons, never in-place edits.

Operator decision 2026-11-07: the S10 data paper gets a comparison with PVGIS and other typical years before it is
published.

## 1. Questions

Q1. How far are the CEY20 v2 reference year, PVGIS-TMY and NSRDB TMY at eligible California weather stations from
    an estimated station climatology, using the study's numerical thresholds as transferred diagnostics?
Q2. How does the signed CEY20–station discrepancy decompose into CEY20–ERA5-Land climatology and ERA5-Land
    climatology–station terms (section 6)?
Q3. For the operator's question: by how much do the other typical years, as delivered, exceed the same thresholds?

All results are descriptive and describe the eligible station sample, not California-wide performance. No method
is tuned, no threshold changed after outcomes.

## 2. Locations: NOAA ISD stations in California

- Candidates: rows of `weather_station_validation/station_metadata.csv` with `preferred_source == "NOAA ISD"` whose
  coordinates lie inside the California polygon of `cb_2024_us_state_500k` (same file as S10).
- Period: 2006–2025 UTC.
- Grid match to CEY20/ERA5-Land: nearest S10 point (great circle) within 25 km.

### 2.1 Parsing and quality rules (pinned and tested before feature computation)

Global Hourly CSV is parsed with pinned rules for: missing-value sentinels (e.g. +9999), units and scaling (tenths
of °C), accepted quality flags for TMP and DEW (accepted: 0, 1, 4, 5, 9 with a valid value, the values documented by
NCEI as passed or not checked; rejected: 2, 3, 6, 7 and others), accepted report types (FM-15 METAR and FM-12
SYNOP; others, e.g. SPECI FM-16, are counted and dropped) and station identifiers (USAF+WBAN). Apply quality,
missing-value, plausibility (AUTH-001 ranges) and Td-consistency (Td > T + 1 °C sets Td missing) filters before
selecting an observation for an hourly slot. Only observations with a valid paired T and Td are eligible. Collapse
exact duplicate records; retain conflicting records sharing a timestamp until selection. Each observation is assigned
to the nearest UTC hour (minute 30 goes to the later hour). For each slot, choose the eligible observation with the
smallest absolute observation-to-slot offset, then the earliest timestamp, then a stable source-record order. Pin
input ordering and count exact duplicates, conflicting duplicates and selection ties separately. Observation-to-slot
offsets are recorded. The analysis period is filtered and 29 February slots are removed after hour assignment. Every
rejection is counted.

### 2.2 Station history

Before candidate metrics are computed, `isd-history.csv` and available station metadata are inspected for
relocations, elevation changes, identifier changes and instrument changes within 2006–2025. Known or unresolved
discontinuities are reported per station. Split records at documented relocations > 1 km or elevation changes
> 50 m. Review documented instrument or identifier changes for evidence of a location or measurement discontinuity
and record the outcome-blind treatment. Select the longest segment without a known unresolved discontinuity,
breaking duration ties by earliest start, and retain it only if it independently meets eligibility. Call this a
metadata-screened segment, not an established homogeneous segment. Where discontinuity timing or consequences remain
unresolved, report the uncertainty and fix inclusion or exclusion before candidate metrics. Distinct station
locations are never concatenated silently. The annual-mean T jump flag of AUTH-001 (3 °C) is reported as a screening diagnostic only,
not as a homogeneity test.

### 2.3 Eligibility (fixed primary rule)

A station-year-month is usable if paired T+Td completeness ≥ 0.80. A station is eligible if every calendar month has
≥ 15 usable years out of 20. The eligible count is unknown before processing. The full exclusion funnel, the usable
year sets per month, geographic coverage and station types are reported. If coverage is sparse, the result is
published as a limited descriptive comparison with that limitation; eligibility is not relaxed to gain coverage.
Any relaxed-eligibility analysis requires a separate specification and is labelled exploratory.

A feasibility stage (station list, completeness, history) runs on ISD data only, before any typical-year file is
retrieved and without computing any candidate metric; it is outcome-blind.

### 2.4 Spatial representativeness

For every station and candidate, report the distance between station and source location, the source coordinates
returned or used, the land/coastal setting and the elevation metadata. Verify the provenance and units of the
S10/ERA5-Land height field before interpreting elevation differences. Label it according to the verified derivation:
geopotential-derived model orography, pressure-derived proxy, or unknown. Do not describe a pressure-derived proxy as
terrain elevation. Report numerical height differences with that qualification; apply the > 300 m terrain-elevation
flag only where comparable elevation metadata are available, as a descriptive convention, not a validated
comparability limit. Unknown elevation is an explicit category. All eligible stations stay in the primary results;
flagged subsets are reported separately. The Köppen class of the station (Beck et al. 2023 raster on E:) is reported
directly; no coastal/inland/desert/mountain grouping is derived from it. Spatial mismatch limits the interpretation
of station agreement and prevents attributing differences solely to typical-year construction.

## 3. Station reference statistics (the yardstick)

The station reference is an equal-year-weighted, calendar-month climatology over the eligible station-year-months.
Monthly means use valid paired T+Td hours. Monthly exposure estimates equal expected monthly hours multiplied by the
observed paired-hour event fraction, averaged equally across usable years; the annual estimate is the sum of these
monthly estimates. Different calendar months may use different year sets. This is an estimated station climatology
and is not identical to the study's complete 20-year reference.

Scaling assumes that missing hours have the same event frequency as observed hours. Completeness and missingness are
reported by calendar month, year and UTC hour. For each exposure, missing-data bounds are reported, obtained by
assigning all missing hours first to non-events and then to events. These bounds cover missing hours within usable
months, not excluded months or years.

Sensitivity reference (predeclared): equal weighting of UTC hour-of-day event frequencies within each usable month,
where every hour of day has observations; months where an hour of day has no observation are reported as
unavailable for this sensitivity. Neither estimator repairs missingness related to weather conditions. The primary
estimator is fixed; the estimator is not chosen according to candidate performance.

RH is computed from T and Td with the CEY20 Magnus form (Bolton coefficients 17.67/243.5, over water) for the station
and for every candidate that supplies Td. Exposure indicators are computed hourly before any aggregation; averaged
T, Td or RH are never thresholded.

## 4. Candidates

| ID | Candidate | Source and pinned product | Period | Variables used |
|---|---|---|---|---|
| C1 | CEY20 v2 reference year | S10 dataset build 8, nearest point | selection from 2006–2025 | T, Td |
| C2_full | ERA5-Land climatology (not a typical year) | the 240 frozen ERA5-Land files, same point, all 20 complete years | 2006–2025 | T, Td |
| C2_matched | ERA5-Land on station support | as C2_full, sampled at the station's observed paired-hour slots (see below) | station support | T, Td |
| C3 | PVGIS-TMY | JRC PVGIS API `v5_3/tmy`, `raddatabase=PVGIS-ERA5`, `startyear=2006`, `endyear=2023` (latest end year of that database to be confirmed by a metadata-only request; if different, the exact range is recorded before data retrieval), `outputformat=json`, at station coordinates | as returned | T2m, RH |
| C4 | NSRDB GOES TMY v4.0.0 | NREL developer API, GOES TMY v4.0.0 download endpoint, explicit name of the most recent `tmy-<year>` product (pinned before retrieval), attributes air temperature, dew point, relative humidity, `utc=true` if offered | as returned | T, Td (RH for consistency check) |

C2_matched: sample ERA5-Land at exactly the station's observed paired-hour slots within its usable
station-year-months. Apply the same aggregation to both sources: compute monthly means and event fractions within
each usable year-month, average equally across usable years for each calendar month, and sum expected-month-hours
multiplied by those mean event fractions for annual exposures. Use these identically weighted station and C2_matched
statistics for the observed-support comparison. C2_full versus C2_matched reflects both usable-year selection and
within-month observation sampling.

Product resolution and freeze: before freezing the approved specification, resolve the exact PVGIS source-period
request, NSRDB endpoint and `tmy-<year>` identifier, requested attributes, and supported UTC parameter using
metadata-only requests where available and authoritative documentation otherwise. These discovery requests require
operator authorization under section 10. Freeze the resolved choices before time-series retrieval. Any subsequent
change to product, period, variables or timestamp convention requires a versioned amendment before retrieval;
otherwise report the candidate as unavailable. For NSRDB, request `utc=true` where supported and verify the returned
convention; otherwise apply the documented conversion and cyclic-year rule.

Product identity: before retrieval, each endpoint/version, explicit product or database identifier, source-period
request where supported, requested variables and timestamp convention are pinned. Requested and returned
coordinates, grid location, elevation, source period, selected source months where supplied, units and metadata are
recorded. Product conventions are not inferred from a generic TMY label. If a specified product or variable is
unavailable, it is reported as unavailable; substitution requires a documented amendment. Older TMY3 (1976–2005)
files are out of period and not used.

Time conventions: whether timestamps are instants or interval labels, and whether offsets apply uniformly, is
verified from the returned metadata. Conversion to UTC uses the documented convention. Local-standard-time records
are wrapped across the synthetic year boundary so that the UTC calendar has exactly 8,760 unique hourly slots; no
daylight-saving time is applied. Coverage, duplicates and month boundaries are validated before metrics. A
29 February, if present, is removed and reported.

C3 conventions: supplied RH is used directly for RH statistics; Td is derived solely for the dew-point-depression
diagnostic by inverting the same Magnus form and is labelled derived. Units, missing values and the RH domain are
checked before inversion; RH = 0 or out-of-domain values are reported, not silently clipped. The supplied precision
and its possible effect near thresholds are reported. Where a candidate supplies both RH and Td (C4), their
consistency under the common formula is reported.

## 5. Metrics, thresholds and reporting

The study's numerical thresholds are applied unchanged as **external diagnostic thresholds**:
1. Annual exposure hours (RH ≥ 80 %, RH ≥ 90 %, T − Td ≤ 2 °C): |H_cand − H_ref| / H_ref ≤ 0.05; if H_ref = 0,
   H_cand must be 0.
2. Monthly means: |T_cand − T_ref| ≤ 0.5 °C and |RH_cand − RH_ref| ≤ 2 percentage points.

The station reference differs from the study's complete source climatology; these results do not revise or replace
the study's acceptance results.

Reported: every station/metric result, all monthly failures and worst cases; annual denominators separately for each
exposure; monthly denominators as station-month checks; the number of stations satisfying all 12 monthly checks;
signed bias, mean absolute error and the distribution over stations; directions of failures. Candidate-specific
availability is reported, and all comparisons are also given on the common station subset where every candidate is
available. Distinct grid-point counts are reported, with a sensitivity summary giving equal weight to distinct
matched CEY20 points. No ranking or "better method" claim beyond the counts; no significance tests.

Wording template: "At X of N eligible stations, CEY20 exceeded the transferred 5 % threshold against the estimated
station reference. This discrepancy includes source–station representativeness, observational and sampling effects,
as well as departure of the selected year from its source climatology." Such results are not described alone as a
selection-method failure or as validation.

The primary comparison evaluates products as delivered. Differences in source periods, spatial support, input data
and variable conventions prevent attributing product differences to selection algorithms. Periods are reported beside
results, with selected-month provenance where supplied. A common-period or source-climatology analysis, if feasible,
needs its own prespecification and does not replace the delivered-product comparison.

## 6. Decomposition (Q2)

For each scalar statistic, report the identity C1 − station = (C1 − C2_full) + (C2_full − station), in the same
statistic and units. The first term measures the selected year's departure from its source climatology. The second
combines reanalysis discrepancy, spatial representativeness, observational uncertainty and reference-support
differences; it is not an isolated estimate of reanalysis error. Absolute errors, relative errors and pass/fail
outcomes do not decompose additively. C2_matched versus the station on identical support (identically weighted, Section 4) diagnoses
the source–station discrepancy on observed support; C2_full versus C2_matched reflects both usable-year selection and
within-month observation sampling. Nothing is
retuned.

## 7. Second reference (internal consistency)

For C1, report the existing S10 internal diagnostics against its complete ERA5-Land source climatology where the
matched point, statistic, units and calculation convention agree. Identify unavailable diagnostics explicitly. C2_full
compared with that same climatology has zero discrepancy by construction; present this only as an implementation
consistency check. Whether PVGIS or NSRDB source climatologies
can be accessed (e.g. PVGIS hourly series, NSRDB annual files) has not been established; it is checked before any
statement that such comparisons cannot be made, and any such analysis needs its own prespecification.

## 8. Gates and freezes

- The approved specification is frozen before downloads. After retrieval and input validation, a sanitized input
  inventory is frozen before candidate metrics are computed: file hashes, sizes, retrieval times, public endpoints and
  non-sensitive request parameters. Credential-bearing URLs, API keys, the operator's e-mail and private request
  payloads are never kept in inventories, logs or git.
- S10 dataset: SHA-256 of build 8 as in its manifest. ERA5-Land: `03-freeze-input-sha256.json`.
- Code pinned by SHA-256, tests on synthetic data and on a small real ISD sample with hand-checked values, Copilot
  code review before the run. The AUTH-001 builder and the raw-data normalisation require review for this use;
  synthetic execution alone does not establish observational correctness.
- One frozen primary analysis; documented corrective reruns preserve prior artifacts and explain changes. Failed
  gates abort; nothing is substituted.

## 9. Outputs, storage and rights

- Working directory per the E: drive rules: `E:/40_work/AUTH-003_external-comparison/` with `dataset.json`; raw
  downloads in `raw/` (append only), results in `results/`.
- Results (CSV, summary.json, manifest) are copied to `docs/research/auth003-tmy/08-results/`. Raw station series and
  typical-year files are not redistributed; the paper reports statistics.
- Before publication, authoritative, product-specific terms for NOAA ISD, PVGIS and the exact NSRDB TMY product are
  verified and recorded, including upstream-provider conditions, required acknowledgement and citation,
  redistribution and derived-output rights. Publishing statistics only does not by itself settle these conditions.
  Citations are verified against the actual product and version. Attribution for reused S10/ERA5-Land material, the
  Census boundary and the Beck classification raster is confirmed where used or reproduced. Unresolved rights block
  publication of the affected material.

## 10. Downloads requiring operator approval

| Stage | Source | What | Size (estimate) | Access |
|---|---|---|---|---|
| A feasibility | NOAA NCEI | `isd-history.csv`; Global Hourly CSV per candidate station and year 2006–2025, `https://www.ncei.noaa.gov/data/global-hourly/access/<year>/<USAF><WBAN>.csv` (≈ 60–75 stations) | ≈ 3–8 GB | free, no key |
| B candidates (after A) | JRC PVGIS | metadata discovery as needed, followed by one frozen-product TMY request per eligible station; discovery requests and their sanitized results are recorded | < 50 MB | free, no key |
| B candidates (after A) | NREL NSRDB | product discovery (documentation, metadata-only request if available), then one frozen-product GOES TMY v4.0.0 request per eligible station | < 100 MB | **operator API key and e-mail**, kept in the operator's secrets file |

## 11. Use in the data paper

A new section "Comparison with station observations and other typical years": one table with pass counts and
denominators per candidate and threshold (also on the common subset), one figure of signed annual RH ≥ 80 % hour
differences per station and candidate, and the decomposition of Section 6. The S3 failure statements and manuscript
constraints are preserved. External comparisons cannot establish hourly joint-distribution, spell, drying-gap or
boundary fidelity. Any abstract statement names the comparison reference, the denominator and the observational
limitation. The data paper stays version 1.0 if not yet published, otherwise becomes 1.1.

## 12. Effort

Spec re-check and approval: ½ day. Stage A downloads and feasibility: ½–1 day. Stage B: ½ day. Code, tests, reviews:
1–1½ days. Run, evaluation, Codex review of results and paper text: 1 day.
