# AUTH-003 amendment V2: evaluate the released CEY20 v2 product

Status: **FROZEN r3, 2026-11-09.** Codex r1 approved freezing once the pre-freeze implementation inspection and the prior-evidence confirmation were recorded; both are recorded below. Later changes are separate amendments. Codex review r0 (chain `auth003-v2-amendment-codex-3fe3ba7c2814`) gave APPROVE WITH
CHANGES; findings 1–6 are applied below, mostly verbatim. Deviations are marked **[deviation]** and need Codex
confirmation before freezing.

## Reason and timing

Operator decision, 2026-11-09: the preprint describes the current product. That is CEY20 v2, the version with
month-interface smoothing (BUG-018, merged in `de0d8b24`), released and in use on the website.

> This amendment was declared on 2026-11-09 after the v1 S3, S4-part-1 and S5 outcomes were known. The v1
> boundary-discontinuity findings motivated the v2 smoothing intervention. Prior v2 evidence included the BUG-018
> global evaluation, reported ramp-correction magnitudes at AUTH-003 study points, and the California comparison and
> data descriptor described below. This amendment is outcome-informed. The investigators must confirm and record
> which planned v2 analyses or component statistics had already been computed or inspected, and which remain
> uncomputed. Definitions, inputs and analysis code for the remaining analyses will be frozen before those analyses
> run.
>
> The implementing session (Claude, 2026-11-09) reports that it has read or computed no additional v2 values at the
> 14 points for this amendment. This statement concerns that session's amendment work. Prior available evidence is
> disclosed below.

**Prior v2 evidence available when this amendment was fixed (disclosure).** This must be disclosed in the
manuscript.

- **BUG-018 evaluation** (`docs/qa/cey/BUG-018-eval-results/README.md` at `de0d8b24`): run 2026-11-01 under frozen
  rules at `b9b3d0a`, over all 354,592 product points, on the same v2 files (generating commit `388cfdb`).
  - **Gate results.** The share of transitions above the reference p99 is 0.991 % (T) and 1.403 % (Td), against
    4.72 % and 5.83 % before smoothing. Pressure rises from 7.2 % to 13.1 %. The largest transition falls from
    46.83 to 14.65 °C (T) and from 47.96 to 25.47 °C (Td). Monthly-mean changes are within ±0.19 °C (T).
  - **Exposure-flag counts.** Under rule 3, exposure counts change by more than 1 % at 27,661 points (RH ≥ 80 %),
    50,314 (RH ≥ 90 %) and 38,691 (D ≤ 2 °C).
  - **At the AUTH-003 study points:** the largest ramp corrections were reported, T from 0.91 °C (Singapore) to
    16.8 °C (Fairbanks), Td up to 15.8 °C (Fairbanks).
  - These development checks provide prior evidence about v2 continuity, exposure-count changes and correction
    magnitudes, including at AUTH-003 study points. They overlap with components of the planned evaluation. The
    amendment adds the specified paired analyses under the frozen AUTH-003 definitions. Their interpretation must
    account for this prior evidence.
- **California comparison (S4 part 2) and data descriptor:** v2, 40 stations.

## Object

- The released v2 hourly product: `E:/ERA_DATA/cey_2006_2025_v2/hourly/cey20_landpoints_month01..12.nc` and
  `hourly_manifest.json`.
  - `version`: `v2-month-interface-smoothing`
  - `generating_commit`: `388cfdb4d90348750df65035cd5e94c2d2cb103a`
- It is read at the 14 frozen points: the same 0.25° indices as `03-freeze.json`, with no re-resolution.
- Inventory: `12-v2-inputs.json`, pinned before the run.

## Pre-freeze record (step 2, 2026-11-09)

### Smoothing implementation at `388cfdb4` (gate 4)

Source: `backend/scripts/smooth_cey20_month_interfaces.py`. It cites `docs/qa/cey/BUG-018-smoothing-spec.md` r4.

- **Window and support.** The window is x[b−7] … x[b+6], where b is the first hour of the new month. The modified
  rows are x[b−6] … x[b+5]: 12 hourly positions per boundary, 12 boundaries including the Dec→Jan wrap, so
  **144 positions per point at most**.
  - This equals the support assumed for M_b.
  - The 13 increments Δx[b−6] … Δx[b+6] are exactly the increments that touch the support.
  - No discrepancy with the analysis definitions.
- **Excess step.** E = J − s, with J = x[b] − x[b−1] and s = ½ ((x[b−1] − x[b−2]) + (x[b+1] − x[b])).
- **Ramp.** For k = 1..6, with w_k = (7 − k)/6:
  - x[b−k] += ½ E w_k;
  - x[b−1+k] −= ½ E w_k.
  
  All corrections are computed from the immutable input windows.
- **Skip rules.**
  - Consecutive source hours are not smoothed: same source year, except Dec→Jan and leap-year Feb→Mar.
  - T and Td share one eligibility mask: all 14 window values finite in both.
  - Pressure has its own mask, and its window is left unchanged if the result would be non-finite or ≤ 0.
- **Humidity constraint.** Td = min(Td, T) only in modified, T/Td-eligible hours.
- **Storage.** v1 month files are copied byte-for-byte, then only the window rows are rewritten. Values are float32.
  Gate 3 therefore compares float32 values exactly against v1/reconstruction.

### Prior-evidence inventory (overlap with the planned analyses)

The BUG-018 evaluation (`evaluate_cey20_month_smoothing.py` at `b9b3d0a`) computed values at the **14 AUTH-003
points** and stored them in `docs/qa/cey/BUG-018-eval-results/summary.json`, committed on `main` via `de0d8b24`
since 2026-11-01. The point set was bound to `03-freeze.json` by its SHA-256.

| Stored per study point | Overlapping planned analysis |
|---|---|
| per boundary: boundary step and maximum absolute transition within the window, before and after smoothing (ramp and two comparators), maximum correction | D4/D4s components J_b and essentially M_b, for T, Td and p |
| `exposure_delta`: change of annual hours RH ≥ 80 %, RH ≥ 90 %, D ≤ 2 °C, v2 minus v1 | Target 1 on v2. Combined with the v1 S3 results, this determines the v2 annual counts. |

Not stored per study point: monthly means (Target 2), D1–D3, D5, S5 applications.

**Implementing session.** During this inspection the session printed one stored study-point record: Singapore,
boundary 01→02, T and Td boundary steps and maximum transitions. It read no other per-point value and no
`exposure_delta`.

**Consequence.** The v2 Target 1 and D4 results are **recomputations of quantities that were already computed
and stored before this amendment**. They are not new outcomes. The manuscript must state this. Target 2, D1–D3, D5
and S5 on v2 remain uncomputed, as far as the records show.

**Investigator confirmation (recorded 2026-11-09).**

- **Operator:** no human has looked at `docs/qa/cey/BUG-018-eval-results/summary.json`.
- **Agent sessions** (record search, 2026-10-31 to 2026-11-02, session that ran BUG-018):
  - The session printed the summary's top-level keys, a v1/v2 study-point match check (336 comparisons, maximum
    difference 1.8e-6) and the global flagged-points file. That file is not limited to the study points.
  - It wrote the study-point maximum ramp corrections into the BUG-018 README. These are disclosed above.
  - No output of per-point `exposure_delta` or per-point boundary records was found.
  - The BUG-018 Codex review (`codex-sol-review.json`) does not mention study-point values.
- **This session:** one record, Singapore 01→02, as stated above.


## Pre-outcome gates (abort on failure)

1. **Artifact identity.** Pin the manifest and all 12 product-file SHA-256 hashes before evaluation. Verify the
   following, and resolve and document any discrepancy before proceeding:
   - the stated version and generating commit;
   - variable definitions, units and packing;
   - missing-value conventions, coordinates and timestamps.
2. **Selection identity.** Verify the following, then use these selections to reconstruct the unsmoothed input
   series from the pinned source data:
   - at each of the 168 frozen point-months, the v2 selected-source-year metadata equals the frozen S3 selection;
   - the same grid indices and coordinates;
   - month, day and hour mapping, the UTC convention and leap-day handling.
3. **Untouched hours.** Define the smoothing mask from the pinned implementation before comparing values. Outside
   that mask, require exact agreement between v2 and the reconstructed selected-source series for T, Td and p, after
   applying the product's documented packing and rounding. Report comparisons and mismatches per point and variable.
   Derive RH using the unchanged formula.
4. **Smoothing implementation.**
   - Document the following from commit `388cfdb4`: the exact mask, ramp equation, excess-step definition, endpoint
     treatment, operation order, humidity constraint and December–January handling.
   - Verify that the released values inside the mask reproduce that transformation at product precision.
   - Count modified positions separately for each variable and their union.
   - Require that every modification lies within the declared mask, and that the mask contains at most 144 hourly
     positions per point.
   - If the implementation's actual support exceeds 144 hours, resolve that before freezing.
5. **Inherited integrity gates.** Require 8,760 correctly ordered, unique hourly timestamps, complete expected
   coverage and finite required values.
   - **[deviation]** Td ≤ T is required **inside the smoothing mask**, with a tolerance justified by packing
     precision.
   - Outside the mask, count and report Td > T hours per point, including their maximum Td − T. Require their
     agreement with the reconstructed selected-source series under gate 3.
   - The Td ≤ T integrity requirement applies inside the smoothing mask. Reproduction of the pinned smoothing
     implementation separately checks how that constraint is enforced.
   - Context: the v1 product already contains 243,294 Td > T point-hours globally (BUG-018 evaluation).

## Unchanged definitions

- Reference: the 20 unsmoothed actual years 2006–2025, same cells, UTC, water-relative RH (Bolton), 365-day calendar.
- Targets 1 and 2: same thresholds and denominators.
- D1–D3, D5 and S5 A1–A4 with regional envelopes: same definitions. The input is the v2 product series.

## D4 on smoothed series

> Let \(b\) index the first hour of the new month, with cyclic indexing across December–January. Define hourly
> increments as \(\Delta x_t=x_t-x_{t-1}\). Retain the original join statistic \(J_b=|\Delta x_b|\).
>
> For a smoothing support comprising hourly values \(x_{b-6},\ldots,x_{b+5}\), additionally report
> \[ M_b=\max_{k=-6,\ldots,6}|\Delta x_{b+k}|. \]
> These 13 increments include every increment touching the smoothing support, including both outer edges. If the
> implementation uses different support endpoints, define the increment set as every increment having at least one
> endpoint in that support.
>
> Compute \(J_b\) and \(M_b\) for both v1 and v2 at every evaluated boundary. Report paired values, changes and
> exceedances of the unchanged variable-specific reference p99. Report inner boundaries and cyclic wrap separately,
> with denominators. Retain the original D4s eligibility and stratification rules and identify same-source-year
> boundaries separately.
>
> The reference p99 describes individual hourly increments. Comparing a maximum over multiple increments with that
> threshold is descriptive and has no calibrated 1% exceedance interpretation. The unmatched-hour and
> leap-day-reference qualifications remain applicable.

- The same local-maximum definition applies wherever D4s reports smoothing effects.
- **Pressure** is included in the continuity reporting. It is a diagnostic **newly introduced by this amendment
  (2026-11-09)**; the earlier D4 covered T, Td and RH only.

## Not repeated on v2

> Sensitivity and LOYO analyses retain their original unsmoothed definitions and results. They characterize
> selection stability and the specified reference comparisons. They do not establish robustness of v2 hourly
> diagnostics or applications. The limited number of modified hours supplies no bound on changes in threshold counts,
> spells, extremes or application outputs.
>
> S4 part 1 compares unsmoothed CEY20, FS-A and FS-B constructions under common processing. Conclusions are restricted
> to that comparison. A claim comparing final smoothed constructions would require applying the same pinned smoothing
> algorithm and parameters to all three constructions and evaluating them under common definitions.
>
> Claims about sensitivity or LOYO robustness of smoothed outputs would likewise require smoothing the corresponding
> perturbed constructions.

## Reporting

> The manuscript's primary evaluated product is CEY20 v2. A dedicated baseline subsection retains the original v1
> target failures and hourly findings, including the boundary-discontinuity evidence that motivated smoothing. Tables
> present paired v1/v2 results for every repeated analysis using unchanged thresholds, denominators and reference
> definitions. Newly added diagnostics are identified with their amendment date.
>
> Unrepeated sensitivity, LOYO and FS analyses are labeled as analyses of unsmoothed constructions. The California
> comparison is identified as having already used v2 before this amendment.
>
> The v2 evaluation assesses a remedy developed after observing v1 outcomes at the same frozen points. Its results do
> not establish independent validation, climate-wide representativeness or production readiness.

Scope updates to the earlier constraints:

- The nine annual failures, the directional counts and the sensitivity counts remain v1 findings. v2 counts are
  reported separately.
- The original discontinuity finding remains part of the scientific record.
- The LOYO interpretation, humidity qualifications, reference limitations and the prohibition on broad
  representativeness claims remain unchanged.
- The chronology is preserved: target specification (2026-10-31), hourly diagnostic specification, BUG-018
  evaluation (2026-11-01), and this amendment (2026-11-09).

## Execution and failure handling

> Before execution, freeze the amendment, input inventories, analysis definitions and exact runner commit. Test
> product reading, packing comparisons, window endpoints, December–January wrap and paired metric computation using
> synthetic fixtures and independently check selected reconstructed values. Preserve the recorded distinct-role
> review.
>
> Preserve every attempted run's code/input identity and disposition. A gate failure stops outcome evaluation pending
> documented resolution. Software corrections require a recorded explanation, a new code identity and rerunning all
> affected outputs. Any change informed by v2 outcomes is recorded as a further amendment and labeled accordingly.

Steps, in order:

1. Codex confirms the revised amendment, including gate 5. **Done:** r1 recheck, chain
   `auth003-v2-amendment-r1-codex-c7bd486feb63`, APPROVE WITH CHANGES; the changes are applied in r2.
2. Inspect the smoothing implementation at `388cfdb4`. Record the exact support and transformation required by
   gate 4, resolve any discrepancy affecting the analysis definitions, and complete the investigator confirmation of
   prior evidence.
3. Freeze the amendment and analysis definitions. **Done: r3, this commit.**
4. Implement the v2 reader and paired v1/v2 runner, with synthetic tests.
5. Obtain Copilot review and resolve findings.
6. Pin the exact runner commit and input inventories before outcome evaluation.
7. Execute the pre-outcome gates. Run outcome evaluation only after all gates pass.

Output goes to `E:/40_work/AUTH-003_v2-evaluation/`; results to `12-results-v2/`.
