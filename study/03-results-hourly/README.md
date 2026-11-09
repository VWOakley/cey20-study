# AUTH-003:S3 — held-out hourly diagnostics D1–D5

Definitions: 03-diagnostics-spec.md (77b64bc, committed before any diagnostic was computed). Runner
auth003_s3_hourly.py at research/AUTH-003-S3-run @ bee90b5, pin 03-s3-hourly-pin.json (9586a80).
All pre-outcome gates passed, and the recomputed selection equals the S3 run in all 12 months.
No pass/fail limits apply; values are reported against the 20 actual years 2006–2025.

## Runs and reproducibility

| Run | Start (UTC) | End (UTC) | Outcome |
|---|---|---|---|
| 1 | 2026-10-31 | — | stopped by the 2.5 h timeout Claude set on the command after month 10; no outputs (run1-timeout.log) |
| 2 | 2026-10-31 19:53 | 23:08 | complete. The Claude Code shell was stopped for low system memory, but the Python process finished; it was first wrongly reported as aborted. manifest: run2-manifest/ (code_sha null because the process had lost its shell) |
| 3 | 2026-11-01 06:30 | 08:42 | complete; files in this directory |

All five CSV files and summary.json of runs 2 and 3 are byte-identical.

## What "held-out" means here

Diagnostics of hourly properties that the selection does not use directly (it uses ten monthly features).
They are not independent data or external validation: the pooled reference contains the selected source
months, and the selection features are related to temperature and humidity. Definitions were fixed after the
S3 selection run and before any hourly diagnostic was computed; no pass/fail limits were predefined.
Scope: the 14 frozen points, 2006–2025, UTC days, 365-day calendar, builder humidity convention.

## D1 Joint T/RH distribution

Distance of the binned CEY20 T/RH histogram to the pooled 20-year histogram, ranked against each actual year
(rank 1 = closer than every actual year). Hellinger: rank 1 at 9 points, 2 at Singapore and Denver, 3 at
San Francisco, 4 at Phoenix, 7 at Frankfurt. Total variation: rank 1 at 9 points, 2 at Helsinki and Denver,
3 at Phoenix, 4 at London, 7 at Frankfurt (d1_joint.csv). This is relative agreement of binned distributions
at these points, not an adequacy test.

## D2 Humid spells and drying gaps

195 of 196 defined CEY20 values lie inside the inclusive range of the 20 actual years; the exception is
San Francisco, RH ≥ 90 %, 10th-percentile gap 3.0 h (actual-year minimum 3.2 h). 10 of 196 values have a
percentile ≤ 0.05 or = 1.0 (with ties, percentile 1.0 need not be a range endpoint). Mean spell length is
below the actual-year median in 23 of 28 point-threshold combinations. These are descriptive, correlated
comparisons, not independent tests (d2_spells.csv).

## D3 Temperature during humid hours (RH ≥ 80 %)

Difference of the mean temperature to the pooled reference: |Δ| ≤ 0.50 °C at 12 points after rounding to two
decimals (Chicago −0.5002 °C; 11 points strictly within 0.5 °C); Phoenix −1.32 °C, Denver +1.13 °C. All 14
CEY20 means lie inside the actual-year range. The temperature-band shares (< 0, 0–10, 10–20, 20–30, ≥ 30 °C)
with their pooled differences are in d3_humid_temperature.csv.

## D4 Month-boundary jumps

154 inner boundaries (11 × 14): 150 join two different years, 4 the same year. Jumps above the reference
99th percentile (all hour-to-hour changes within ±72 h of the same boundary in the 20 actual years):

| Variable | inner boundaries above p99 | rate | Dec→Jan wrap (of 14) |
|---|---:|---:|---:|
| Temperature | 68 / 154 | 44.2 % | 7 |
| Dew point | 85 / 154 | 55.2 % | 11 |
| RH | 55 / 154 | 35.7 % | 4 |

None of the 4 same-year boundaries exceeds p99 for any variable. Largest jumps: Fairbanks Jan→Feb 33.7 °C
temperature and 31.5 °C dew point (2007 → 2024; reference p99 2.4 / 1.9 °C); Denver Feb→Mar 19.2 °C;
Phoenix Jan→Feb 56.2 RH points (reference p99 23.2). The CEY20 builder does not smooth month boundaries
(d4_boundaries.csv).

Exceedance of p99 is a descriptive diagnostic, not a calibrated test: the reference mixes all hours of the
day (the join is always 23→00 UTC), and cross-year joins are not natural transitions, so no expected count
under a null model is claimed. In leap years the removed 29 February makes the 28 Feb 23:00 → 1 Mar 00:00
step non-consecutive; it lies inside the Feb→Mar reference window.

## D5 Day and humidity convention (sensitivity)

* Local-solar days: 4 of 168 point-months change selection; Target 1 failures stay at 9 (same nine checks).
* Saturation over ice below 0 °C (coefficients flagged UNVERIFIED in auth003_study.py): 9 point-months change
  selection; Target 1 failures 8 — Denver RH ≥ 90 % is within 5 % (1.3 %) under this convention. Selection
  and reference counts both change definition, so 8 vs 9 is not a like-for-like comparison
  (d5_conventions.csv). The baseline is unchanged.

## Reading

At these 14 points the binned joint T/RH distribution of CEY20 is closer to the pooled 20-year distribution
than most single actual years, and spell and gap statistics lie (with one exception) inside the actual-year
range, although mean spell length tends to be shorter. The clear limitation is continuity at month joins:
unsmoothed joins of different years produce jumps above the reference p99 at 44 % (temperature), 55 % (dew
point) and 36 % (RH) of inner boundaries, up to 33.7 °C in one hour. Sequence-dependent applications near
month ends may be affected; impacts, and whether smoothing would remove the effect, were not tested.

## Open items

* Supplementary D4s (Codex R5): done, see `../03-results-hourly-d4s/README.md` (descriptive; 65.6 %,
  61.7 % and 54.5 % of inner boundaries above the 23→00 UTC reference p99). Not a replacement for D4.
* Product issue: verify the jumps in the published CEY20 hourly artefacts and report as a separate
  hourly-continuity issue (Codex).

## Review

Codex (gpt-6.1-sol) review R1–R9 applied; manuscript constraints in manuscript-constraints.md.
