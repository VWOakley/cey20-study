# AUTH-003 S3 — held-out hourly diagnostics: operational definitions

Written 2026-10-31 after the S3 target run (96b2e87) and **before any hourly diagnostic was computed**.
03-study-protocol.md ("Held-out diagnostics") lists the diagnostic families but not their exact
definitions; this addendum fixes them. As the protocol requires, no binary pass/fail limits are set:
every quantity is reported with its reference and its position within the 20 actual years.

"Held-out" here means hourly properties that the selection never sees (it uses ten monthly features
only). All quantities use the frozen 14 points, the builder RH formula (Magnus over water) unless stated,
UTC hours and the 365-day calendar (29 Feb removed; February = 672 hours).

## Series

* **CEY20 series** per point: the 12 selected months concatenated Jan..Dec, 8760 hours.
* **Actual years** per point: each of the 20 years 2006–2025, Jan..Dec, 8760 hours.
* **Pooled reference**: all 20 actual years together (175 200 hours).
* **Context rank**: each statistic is also computed for each actual year; the CEY20 value is reported
  with the minimum, median and maximum of the 20 actual-year values and its empirical percentile
  (share of actual years with a value <= the CEY20 value, 0..1). For distances to the pooled reference,
  `rank_closest` = 1 + number of actual years closer than CEY20 (1 = closer than every actual year).

## D1 Joint T/RH distribution

2-D histogram, T bins of 2 °C from −60 to +60 °C (values outside are clipped into the edge bins),
RH bins of 5 points from 0 to 100 (100 in the last bin). Normalised to probabilities.
Reported: Hellinger distance and total-variation distance of the CEY20 histogram to the pooled
reference; the same two distances for each actual year; context rank.

## D2 Humid spells and drying gaps

A humid spell is a maximal run of consecutive hours with RH ≥ 80 % (and separately RH ≥ 90 %).
A drying gap is a maximal run of RH < threshold strictly between two humid spells. Runs are cut at the
start and end of the 8760-hour series, in the CEY20 and in every actual year alike.
Reported per threshold: number of spells, mean, 90th percentile and maximum spell length (h); number of
drying gaps, median and 10th-percentile gap length (h); with the actual-year context. Undefined values
(no spell, no gap) are reported as empty, not 0.

## D3 Temperature during humid hours

Over RH ≥ 80 % hours: mean T, and the share of those hours with T < 0, 0–10, 10–20, 20–30, ≥ 30 °C.
CEY20 vs pooled reference (difference), with actual-year context for mean T.

## D4 Month-boundary jumps

At the 11 inner month boundaries of the CEY20 series, and the Dec→Jan wrap (reported separately,
because a typical year is often used cyclically): |ΔT|, |ΔTd| and |ΔRH| between the last hour of month m
and the first hour of month m+1. Reference: all hour-to-hour absolute changes of the actual years within
±72 h of the same boundary (for the wrap: 31 Dec of year Y to 1 Jan of Y+1, 19 year pairs). Reported:
the jump, its empirical percentile within that reference, the reference 99th percentile, and whether
both sides come from the same calendar year (`same_year`, in which case the jump is a real observed change).
Summary: number of CEY20 jumps above the reference 99th percentile, per variable.

## D5 Day convention and humidity convention

* **Local-solar days**: the daily-temperature-range feature computed on local-solar days
  (`dtr_local_day`, shift = round(lon/15) h); reselect; report the number of point-months whose
  selection changes and the Target-1 annual checks recomputed for that selection (evaluation with the
  builder formula, as in the base run).
* **Humidity convention**: features and counts with saturation over ice below 0 °C (`rh_mixed`,
  `ah_mixed`, coefficients flagged UNVERIFIED in auth003_study.py); reselect; report changed point-months
  and Target-1 checks with both selection and reference counts under the mixed convention.

Both are sensitivity results. They do not replace the baseline.

## Gates

The same pre-outcome gates as the S3 run (study code pin, now including `auth003_s3_hourly.py`,
builder identity with 00efaf6, the 14 frozen points, inventory, content SHA-256, coverage 1.0).
The selection is recomputed and must equal the S3 run's selections (`targets_monthly.csv`
selected_year), otherwise the run aborts.

## D4s Supplementary: hour-matched month-boundary reference (Codex review R5, added 2026-11-04, pre-outcome)

Supplementary to D4, clearly labelled as such; it does **not** replace the prespecified D4 results.
D4's reference pools all hour-to-hour changes within ±72 h, including diurnal transitions, while every
CEY20 month join is a 23→00 UTC transition. D4s therefore uses only observed 23→00 UTC transitions.

* Jump: identical to D4 (|ΔT|, |ΔTd|, |ΔRH| between the last hour of month m and the first hour of
  month m+1 in the CEY20 series; Dec→Jan wrap reported separately).
* Reference for inner boundary m→m+1: in each of the 20 actual years, the absolute changes from 23:00 to
  00:00 UTC on the 31 day transitions centred on the boundary (the boundary transition itself plus the
  15 preceding and 15 following midnights), i.e. at most 31 × 20 = 620 values. Transitions that cross a
  removed 29 February (Feb→Mar boundary in 2008, 2012, 2016, 2020, 2024) are excluded because they are
  not natural transitions.
* Wrap reference: the same 31 midnights across 31 Dec of year Y → 1 Jan of Y+1 for the 19 consecutive
  year pairs (at most 589 values).
* Reported per point, boundary and variable: jump, its empirical percentile in the reference (share of
  reference values ≤ jump), reference 99th percentile, reference size n, `same_year` as in D4.
  Summary: count above the matched p99 per variable, inner and wrap separately.
* Descriptive only. No null model, no expected count and no significance statement: the reference values
  are serially and spatially dependent and the joins are not natural transitions (Codex R4).
* Data, points, selection and gates are the same as for D1–D5 (S3 code pin, builder identity, 14 frozen
  points, inventory, content SHA-256, coverage 1.0, selection equal to the S3 run). The runner file is
  added to a separate pin committed before the run.
