# Amendment V2 results: paired v1/v2 evaluation of the released CEY20 v2 (run 1)

Status: written 2026-11-09 by the implementing session (Claude). Not yet reviewed (Codex S7, Copilot/Codex S8).

## What was run

- **Runner.** One run of `auth003_v2_eval.py` at `research/AUTH-003-S3-run` @ `7862bdee`. The study definitions are
  those of amendment V2 (frozen r3, `12-amendment-V2.md`) and the clarification V2.1 (approved, `12-amendment-V2.1-clarification.md`).
- **Inputs.** The pin `12-v2-pin.json` and the product inventory `12-v2-inputs.json`.
- **Time and output.** 2026-11-09, 15:26:10–17:19:53 UTC, written to `E:/40_work/AUTH-003_v2-evaluation/run1`.
- **Manifest.** It records code SHA `7862bdee`, freeze code `00efaf6a` and freeze-input inventory SHA-256 `75cfecfc…`.
- **Execution.** Exit code 0. The run was executed once. No rerun took place, and nothing was changed after the
  outcomes were seen (statement of the implementing session; not a log record).
- **Labelling.** All values are descriptive and in-sample, from 0.25° reanalysis. They are not design values.
- **Prior evidence.** The v2 Target 1 and D4 values recompute quantities that the BUG-018 development evaluation
  had already computed and stored (amendment V2, "Consequence"). They are not new outcomes.

## Gates (`gates.json`): passed

| Variable | Mismatches outside mask | Mismatches inside mask vs. pinned smoothing | Modified positions | Max per point | Non-finite |
|---|---:|---:|---:|---:|---:|
| T | 0 | 0 | 2100 | 144 | 0 |
| Td | 0 | 0 | 2100 | 144 | 0 |
| p | 0 | 0 | 2076 | 144 | 0 |
| Union | – | – | 2100 | 144 (support 144) | – |

The gates cover the 14 points and the Iqaluit region centre.

- **Td ≤ T.** Td > T occurs inside the mask at 0 hours.
- **Td > T outside the mask:** 1 hour at London, maximum Td − T = 0.010 °C. This value is identical to the
  reconstructed source series (gate 3), so it is inherited from the source data and not produced by the smoothing.
- **Pressure.** It has 24 fewer modified positions than T/Td. At those positions the pinned smoothing leaves the
  stored pressure value unchanged, and the gate reproduces this exactly. The reason per position was not analysed.

## Reproduction of v1 by the v2 runner

The runner recomputes v1 from the frozen inputs, and these v1 values were compared with the earlier results:

- **S3 annual** (`03-results/targets_annual.csv`): identical in 42 of 42 rows.
- **S3 monthly:** `selected_year` and all pass flags are identical in 168 of 168 rows.
  - The deviations differ by at most 3.4·10⁻⁵ °C and 8.4·10⁻⁵ pp. This is float32 summation order: the v2 runner
    forms monthly means from the product-read series.
- **D1–D3** (`03-results-hourly`) and **A1–A4** (`05-results`): identical.

The comparison was done with an ad hoc script by the implementing session; it is not part of the runner.

## Paired results

### Targets (unchanged thresholds and denominators)

| Quantity | Tolerance | Within, v1 | Within, v2 | Median abs. deviation v1 → v2 |
|---|---|---:|---:|---|
| Annual hours RH ≥ 80 %, RH ≥ 90 %, D ≤ 2 °C | ±5 % | 33 of 42 | 33 of 42 | 0.98 % → 1.10 % (31.7 h → 29.1 h) |
| Monthly mean T | ±0.5 °C | 108 of 168 | 109 of 168 | 0.310 → 0.307 °C |
| Monthly mean RH | ±2 pp | 154 of 168 | 153 of 168 | 0.587 → 0.607 pp |

**Annual checks.** The same nine checks are outside tolerance in v1 and v2. These are Phoenix ×3, Denver ×3,
Fairbanks ×2 and Chicago RH ≥ 90 %.

- The selected annual counts change by at most 19 h (median 4.5–5 h per metric).
- Underestimates/overestimates of the reference are 25/17 in v1 and 28/14 in v2.

**Monthly checks.** Two results flip, both at Chicago:

- May T moves into tolerance (0.546 → 0.489 °C).
- March RH moves out of tolerance (1.98 → 2.07 pp).

The maximum change of a monthly deviation is 0.13 °C (T) and 0.22 pp (RH).

### D1–D3, D5

- **D1 (Hellinger, binned T/RH).** The composite year is closer to the pooled distribution than every actual year at
  9 of 14 points in both versions. Ranks elsewhere are unchanged, except Phoenix (4th → 5th of 21).
- **D2 (spells, gaps).** 195 of 196 statistics lie within the actual-year range in both versions. The exception is
  the same San Francisco 10th-percentile drying gap at RH ≥ 90 % in both versions.
  - 30 of 196 percentile positions change.
  - The largest change, Mumbai median gap at RH ≥ 90 % from the 70th to the 20th percentile, comes from ties: 13 h →
    12.5 h against an actual-year median of 13 h. Tied ranks limit interpretation, as stated for v1.
  - Mean spell length is below the actual-year median at 23 of 28 location–threshold combinations in both versions.
- **D3 (mean T in hours with RH ≥ 80 %).**
  - Points with |Δ| ≤ 0.50 °C: 11 strictly in both versions; 12 in v1 when rounded to two decimals (Chicago
    −0.5002 °C), while Chicago is −0.516 °C in v2.
  - All 14 points are within the actual-year range in both versions.
  - The differences change by at most 0.033 °C (Phoenix −1.323 → −1.356 °C).
- **D5 (conventions; V2.1 C1).**
  - Variants: local-solar days change the selection in 4 of 168 location-months; the mixed ice convention in 9.
  - Target-1 failures: baseline 9, local-solar 9, mixed ice 8. This is the same pattern as v1, where the one
    difference is Denver RH ≥ 90 %.
  - Median |relative deviation|: 1.10 % (baseline), 1.15 % (local-solar), 1.09 % (mixed ice).

### D4 month interfaces

Paired boundary steps at 150 cross-year inner boundaries, 4 same-source-year inner boundaries and 14 December–January
wraps per variable (`d4_boundaries.csv`).

- **J_b** is the step at the boundary.
- **M_b** is the largest of the 13 hourly steps touching the 12-hour smoothing support.
- **Reference p99:** all hour-to-hour changes within ±72 h of the same boundary in the 20 actual years.

Comparing a maximum over 13 steps with a single-step percentile is descriptive. It has no calibrated 1 % meaning
(amendment V2).

**Exceedances of the reference p99, cross-year inner boundaries (n = 150):**

| Variable | J_b v1 | J_b v2 | M_b v1 | M_b v2 |
|---|---:|---:|---:|---:|
| T | 68 | 0 | 76 | 14 |
| Td | 85 | 0 | 95 | 26 |
| RH | 55 | 0 | 65 | 12 |
| p (new in amendment V2, 2026-11-09) | 125 | 0 | 126 | 39 |

**Wrap (n = 14).**

| Variable | J_b v1 | J_b v2 | M_b v1 | M_b v2 |
|---|---:|---:|---:|---:|
| T | 7 | 0 | 8 | 1 |
| Td | 11 | 0 | 12 | 1 |
| RH | 4 | 0 | 4 | 0 |
| p | 8 | 0 | 10 | 4 |

**Same-source-year inner boundaries (n = 4).** These are unchanged by construction: 0 exceedances of J_b and M_b
for every variable in both versions.

**Supplementary 23→00 UTC reference.** It is smaller (median p99: T 1.55 °C instead of 2.82 °C) and gives higher
counts. At cross-year inner boundaries:

| Variable | J_b v1 | J_b v2 | M_b v1 | M_b v2 |
|---|---:|---:|---:|---:|
| T | 101 | 1 | 128 | 86 |
| Td | 95 | 1 | 113 | 48 |
| RH | 84 | 3 | 112 | 67 |
| p | 128 | 0 | 134 | 81 |

**Magnitudes.**

- **Median at cross-year inner boundaries, v1 → v2:**
  - J_b: T 2.60 → 0.43 °C, Td 2.81 → 0.22 °C, RH 9.3 → 1.7 pp, p 360 → 20 Pa.
  - M_b: T 3.09 → 1.78 °C, Td 2.96 → 1.30 °C, RH 12.5 → 7.6 pp, p 360 → 105 Pa.
- **Largest values over all boundaries:**
  - J_b: T 33.66 → 2.62 °C, Td 31.52 → 2.13 °C.
  - M_b: T 33.66 → 5.96 °C (v2 at Denver, February→March), Td 31.52 → 6.26 °C (v2 at Denver, November→December).
- **M_b larger in v2 than in v1:** at 31 (T), 30 (Td), 35 (RH) and 5 (p) of 150 cross-year inner boundaries. The ramp
  replaces one large step by smaller steps. Where a large natural change lies inside the support, the ramp can add to
  it. Paired values are in `d4_boundaries.csv`.

### S5 applications A1–A4 (V2.1 C2)

**Outputs within the actual-year range.**

- v1: 195 of 196.
- v2: 194 of 196.
- In v2 both exceptions are A1 duration-curve distances below every actual year, i.e. closer to the pooled
  curve:
  - Quito (unchanged, 0.56 °C);
  - Dubai (0.850 → 0.825 °C, 5th → 0th percentile; smallest actual year 0.845 °C).

**Changes v1 → v2.** 13 of 196 percentile positions change, by at most 15 points:

- **A1** (8 changes): T quantiles at Denver, Fairbanks, Houston, London, Mumbai and Quito, plus the Dubai distance.
  - The T-quantile percentile has median 50 and range 10–75 in both versions.
- **A2** (2): Fairbanks cooling degree hours above 24 °C (255.8 → 235.2 °C·h) and hours ≤ 2 °C.
  - Rare cold counts that are zero in the composite year while positive in some actual years are unchanged: Dubai
    ≤ 7 °C, and Houston, Frankfurt and London ≤ −7 °C.
- **A3** (2): time of wetness at Denver (+3 h) and Fairbanks (−3 h).
  - Calculated time-of-wetness levels equal those of all 20 actual years at 11 points in both versions.
- **A4** (1): Phoenix near-saturation hours (34 → 31 h, 40th → 25th percentile).
  - The range is 25th–60th percentile in both versions.

**Regional envelopes** (`regional_envelopes_v2.csv`, 7 regions × 12 months × 3 quantities): they were read from the
v2 product for all box members. Their comparison with v1 is for the S6 figures.

## Files

In this folder:

- results: `gates.json`, `summary.json`, `targets_annual.csv`, `targets_monthly.csv`, `d1_joint.csv`,
  `d2_spells.csv`, `d3_humid_temperature.csv`, `d4_boundaries.csv`, `d5_conventions.csv`, `a1_duration.csv`,
  `a2_heat_pump.csv`, `a3_tow.csv`, `a4_saturation_zero_crossing.csv`, `regional_envelopes_v2.csv`;
- provenance: `manifest.json` (as written), `manifest_public.json` (paths made repository-relative, otherwise
  identical) and `run.log`.

Not in git because of size (31.5 MB): `a1_curves.csv` (v1 and v2 duration-curve rows for the S6 figures). It is
kept at `E:/40_work/AUTH-003_v2-evaluation/run1/a1_curves.csv`, SHA-256
`58905fcf541d4d5635b9aab61ae6c70706fd64833eb852ef6feb679e72e1edb8`.

## Interpretation limits (from amendment V2)

- **Scope of v2.** The v2 evaluation assesses a remedy developed after the v1 outcomes were seen at the same frozen
  points. It does not establish independent validation, climate-wide representativeness or production readiness.
- **Unsmoothed analyses.** Sensitivity, LOYO and the FS comparison remain analyses of unsmoothed constructions.
- **Smoothed hours.** They are synthetic. The limited number of modified hours (at most 144 per point) supplies no
  bound on changes in threshold counts, spells or extremes; the observed changes are reported above.
