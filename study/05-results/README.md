# S5 results: example regions and engineering screening applications (run 1)

Status: revised after Codex review (chain auth003-s5-results-codex-8fe8518f4e03, GO with changes).

## What was run

One run of `auth003_s5_applications.py` under the frozen spec `05-applications-spec.md` (r4) with the pin
`05-s5-pin.json` and the product inventory `05-s5-inputs.json`, on 2026-11-06 12:42–15:37 UTC, output
`E:/ERA_DATA/auth003_s5_run1`. The manifest records code SHA 073d2b8e (`research/AUTH-003-S3-run`).

All results are screening values: descriptive, in-sample, from 0.25° reanalysis. They are not design values and
make no conformity statement for ISO 9223 or EN 14825.

## Provenance and gates

- The manifest records the run's code SHA, freeze-input inventory SHA-256 and pinned product inventory. The frozen
  protocol requires abort-on-mismatch checks for code, reference inputs, S3 selection and product inputs, together
  with the inherited builder, calendar, finite-value and coverage gates. These checks have no explicit success
  records in the manifest or log; their execution and ordering require inspection of the pinned runner.
- CEY20 selection: read from the pinned S3 monthly selection file, not recomputed.
- Centre gates (recorded in `summary.json`): for all seven region centres, the product's hourly T and Td series
  equal the reference series of the selected year exactly in every month ("equal").
- A clean checkout and initially absent output directory are reported start conditions; neither is independently
  recorded in the manifest or log.
- Operator attestation (2026-11-06): one run, nothing adjusted after outcomes were seen. This is an attestation,
  not a log record.

## A1–A4 at the 14 points

Context convention (spec §3): CEY20 value against the 20 actual-year values; percentile = 100 × share of actual
years with a value ≤ the CEY20 value, ties included.

Of 196 scalar outputs (A1 84, A2 70, A3 14, A4 28), one lies outside the actual-year range: the A1 duration-curve
distance at Quito (CEY20 0.56 °C, actual years 0.72–1.88 °C), i.e. the CEY20 curve is closer to the pooled curve
than every actual year there.

**A1 duration curves.** For the 70 hourly-temperature quantiles (5 per point), the CEY20 percentile has median 50
and range 10–75. The maximum absolute distance of the duration curve to the pooled curve (D, evaluated over the frozen 8760
quantile levels) lies at or below the actual-year median at 10 of 14 points; at Frankfurt
it is at the 95th percentile (7.98 °C; actual years 3.22–9.75 °C).

**A2 heat-pump screening.** Heating and cooling degree hours and the nested cold-hour counts lie within the
actual-year range at every point. Some threshold counts are zero in CEY20 and all 20 actual years; others are zero
in CEY20 despite positive counts in some actual years, including Dubai at ≤ 7 °C and Houston, Frankfurt and London at
≤ −7 °C. Excluding Singapore, where all 20 actual-year heating degree-hour values are zero, heating degree-hour
percentiles range from 35 to 95. Dubai is at percentile 95 (770.49 °C h; actual years 200.37–1003.40 °C h). Where
all 20 actual-year values are zero and CEY20 is zero, the tie convention gives percentile 100.

The illustrative degree-hour bases are 15 °C for heating and 24 °C for cooling. Degree hours do not estimate building
demand, electricity use, capacity adequacy, COP, SCOP or defrost losses. The three cumulative temperature thresholds
are nested screening counts, not EN 14825 climate-bin calculations or a seasonal performance assessment.

**A3 time of wetness (calculated).** CEY20 levels: τ5 Singapore, Quito; τ4 Mumbai, Houston, Frankfurt, London,
Seattle, San Francisco, Helsinki; τ3 Dubai, Fairbanks, Chicago, Phoenix, Denver. The same level is assigned to all
20 actual years at 11 points, to 19 at Phoenix, 14 at Quito and 13 at Chicago. CEY20 hours lie at the 15th–65th
percentile; the lowest are Phoenix (15) and Chicago, Denver (25).

These levels classify the calculated meteorological estimate using RH > 80 % and T > 0 °C; they do not describe
measured surface wetness, corrosion rate or a corrosivity category.

**A4 near-saturation and zero-crossing days.** Hours with T − Td ≤ 1 °C lie at the 25th–60th percentile.
Singapore, Mumbai, Dubai and Quito have zero zero-crossing days
in CEY20 and every actual year, giving percentile 100 under the tie convention. San Francisco also has zero in
CEY20, against an actual-year range of 0–10 days, giving percentile 50. Across the remaining ten points, including
San Francisco, percentiles range from 30 to 85.

Near-saturation hours are an air indicator, not surface-condensation events. Zero-crossing days require a UTC day's
minimum air temperature strictly below 0 °C and maximum strictly above 0 °C; they are not measured material
freeze-thaw cycles.

## Regional envelopes

Seven regions in 2° × 2° boxes, 37–81 land points each (Singapore 37, Dubai 50, Houston 62, Frankfurt 81,
Helsinki 55, Fairbanks 81, Iqaluit 72), 12 months × 3 quantities = 252 rows. Each row gives the spatial minimum,
10th, 50th, 90th percentile and maximum across points of the CEY20 product year, and the centre's actual-year
minimum, median and maximum. Iqaluit (group E) is not an S3 point; its selected year per month is read from the product's
`selected_source_year` (listed in `summary.json`), and the centre gate confirms that the product series equals
that actual year's reference series.

The envelopes describe spatial variation among grid points, each with its own selected source year per month.
They are not a simultaneous regional weather field, and the spatial spread and the centre's interannual range are
different populations, not equivalent uncertainty intervals.

## Limits (from the frozen spec §6)

- 0.25° reanalysis; local, urban, coastal and mountain effects are not resolved.
- In-sample: S5 uses the archive CEY20 was selected from, and several quantities reuse or overlap selection
  features (RH ≥ 80 % hours; A3; the A4 1 °C count nested in the 2 °C feature; monthly means). Not independent
  validation.
- The 20-year range is an observed archive range, not a confidence interval, return period or future bound.
- Duration curves, degree hours and threshold totals ignore hour order; they cannot assess persistence or dynamic
  response. No smoothing (product v1).
- No claim for locations other than those evaluated.

## Files

In this folder: `a1_duration.csv`, `a2_heat_pump.csv`, `a3_tow.csv`, `a4_saturation_zero_crossing.csv`,
`regional_envelopes.csv`, `summary.json`, `manifest.json`, `run.log`.

Not in git because of size (15.4 MB): `a1_curves.csv` (duration-curve rows for the S6 figures), kept at
`E:/ERA_DATA/auth003_s5_run1/a1_curves.csv`, SHA-256
`9f26f1747c748443b74d7c3985e7d0372a3bb9fe0504d7b66f88c664239bd3bf`.

Check of `a1_curves.csv` (2026-11-06, `a1_curves_check.csv`): at all 14 points the grid is k = 1..8760 with
p_k = (k − 0.5)/8760, exceedance = 1 − p, CEY20 and pooled curves are non-decreasing in p, and the maximum
|CEY20 − pooled| equals the A1 distance D. That maximum lies at an outer quantile level at every point
(p ≤ 0.0104 or p ≥ 0.9993). The pooled curve lies within the actual-year band at every level; the CEY20 curve lies
outside the band at 20 of 8760 levels at Denver and at none elsewhere. CEY20 combines months from different years, so
its annual quantiles are not bounded by the band of single actual years.

Duration-curve and regional-envelope figures are planned for S6. The duration-curve figure input is retained
externally; its contents require verification before figure production.

## Open before S6

- Runner review evidence: Copilot code review of `auth003_s5_applications.py` and its tests, chain
  `auth-003-s5-review-copilot-f708519180ec` (2026-11-05). Its findings (curves not saved; mtime, variable and hour
  gates; gate tests) were fixed in f66f4d24 and 073d2b8e before the pin; the run used 073d2b8e. Closed.
- EN 14825: verified, see `../06-en14825-citation-check.md`. Closed.
- Publication copy with relative paths: `manifest_public.json`. Closed.
