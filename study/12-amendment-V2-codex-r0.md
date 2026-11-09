## Verdict — APPROVE WITH CHANGES

The amendment is scientifically acceptable as an outcome-informed evaluation of the released v2 product. Freeze it after addressing the findings below. This review assesses the supplied design, without independently verifying artifacts, implementation, or earlier results.

### 1. Correct the timing claim

“No v2 outcome has been computed” conflicts with the acknowledged v2 California comparison. Distinguish the proposed rerun from all previous v2 evidence, and distinguish amendment timing from diagnostic-definition timing.

Replace the status and timing statements with

> This amendment was declared on 2026-11-09 after the v1 S3, S4-part-1 and S5 outcomes were known. The v1 boundary-discontinuity findings motivated the v2 smoothing intervention. The California comparison and data descriptor already used v2. No outcomes from the additional v2 analyses specified here have been computed, subject to confirmation by the investigators. This amendment is outcome-informed. Its definitions, inputs and analysis code will be frozen before those additional analyses run.

The manuscript must disclose **what prior v1 and v2 evidence was available when the amendment was fixed**. Any prior development checks of smoothing efficacy also belong in that disclosure.

### 2. Strengthen selection identity and artifact gates

The existing gates are necessary but insufficient. A matching `selected_source_year` field establishes metadata agreement. Actual hourly provenance needs the accompanying reconstruction checks.

Replace gates 1–5 with

> 1. **Artifact identity.** Pin the manifest and all 12 product-file SHA-256 hashes before evaluation. Verify the stated version, generating commit, variable definitions, units, packing, missing-value conventions, coordinates and timestamps. Resolve and document any discrepancy before proceeding.
>
> 2. **Selection identity.** At each of the 168 frozen point-months, verify that the v2 selected-source-year metadata equals the frozen S3 selection. Verify the same grid indices and coordinates, month/day/hour mapping, UTC convention and leap-day handling. Use these selections to reconstruct the unsmoothed input series from the pinned source data.
>
> 3. **Untouched hours.** Define the smoothing mask from the pinned implementation before comparing values. Outside that mask, require exact agreement between v2 and the reconstructed selected-source series for T, Td and p after applying the product’s documented packing and rounding. Report comparisons and mismatches per point and variable. Derive RH using the unchanged formula.
>
> 4. **Smoothing implementation.** Document the exact mask, ramp equation, excess-step definition, endpoint treatment, operation order, humidity constraint and December–January handling from commit `388cfdb4`. Verify that the released values inside the mask reproduce that transformation at product precision. Count modified positions separately for each variable and their union. Require that every modification lies within the declared mask and that the mask contains at most 144 hourly positions per point.
>
> 5. **Inherited integrity gates.** Require 8,760 correctly ordered, unique hourly timestamps, complete expected coverage and finite required values. Verify Td ≤ T over the entire product using a tolerance justified by packing precision.

If the implementation’s actual support exceeds 144 hours, resolve that discrepancy **before freezing**. A count cap alone cannot establish correct window placement or transformation.

Replace “Gate 3 confirms that Td ≤ T is enforced in the modified hours” with

> The integrity gate checks Td ≤ T. Reproduction of the pinned smoothing implementation checks how that constraint is enforced.

### 3. Retain join-step D4 and add a precisely defined local maximum

The added quantity is necessary for interpreting smoothing efficacy. The join step alone can improve while the largest discontinuity moves to a neighboring hour or ramp edge.

The proposed addition is sufficient for detecting that local displacement **if it includes both ramp edges**. It does not establish preserved temporal structure or application performance.

Use the following definition, adjusting the support indices before freezing if implementation inspection establishes different endpoints

> Let \(b\) index the first hour of the new month, with cyclic indexing across December–January. Define hourly increments as \(\Delta x_t=x_t-x_{t-1}\). Retain the original join statistic \(J_b=|\Delta x_b|\).
>
> For a smoothing support comprising hourly values \(x_{b-6},\ldots,x_{b+5}\), additionally report
> \[
> M_b=\max_{k=-6,\ldots,6}|\Delta x_{b+k}|.
> \]
> These 13 increments include every increment touching the smoothing support, including both outer edges. If the implementation uses different support endpoints, define the increment set as every increment having at least one endpoint in that support.
>
> Compute \(J_b\) and \(M_b\) for both v1 and v2 at every evaluated boundary. Report paired values, changes and exceedances of the unchanged variable-specific reference p99. Report inner boundaries and cyclic wrap separately, with denominators. Retain the original D4s eligibility and stratification rules and identify same-source-year boundaries separately.

Add this interpretation explicitly

> The reference p99 describes individual hourly increments. Comparing a maximum over multiple increments with that threshold is descriptive and has no calibrated 1% exceedance interpretation. The unmatched-hour and leap-day-reference qualifications remain applicable.

Apply the same local-maximum definition wherever D4s reports smoothing effects. Include pressure in continuity reporting for the three-variable smoothing intervention, clearly identifying any pressure diagnostic newly introduced by this amendment.

### 4. Limit what unrepeated sensitivity, LOYO and FS analyses support

Repeating these analyses with smoothing is **optional for the stated selection-method scope**. It becomes necessary if the manuscript claims comparative performance or robustness of the final smoothed product.

Replace the “Not repeated” rationale with

> Sensitivity and LOYO analyses retain their original unsmoothed definitions and results. They characterize selection stability and the specified reference comparisons. They do not establish robustness of v2 hourly diagnostics or applications. The limited number of modified hours supplies no bound on changes in threshold counts, spells, extremes or application outputs.
>
> S4 part 1 compares unsmoothed CEY20, FS-A and FS-B constructions under common processing. Conclusions are restricted to that comparison. A claim comparing final smoothed constructions would require applying the same pinned smoothing algorithm and parameters to all three constructions and evaluating them under common definitions.
>
> Claims about sensitivity or LOYO robustness of smoothed outputs would likewise require smoothing the corresponding perturbed constructions.

Identical processing is required for an equal **smoothed-output comparison**. It is unnecessary for the explicitly unsmoothed selection comparison.

### 5. Preserve v1 results visibly and scope earlier constraints by version

Use a dedicated v1 baseline subsection and paired v1/v2 tables for every repeated target, diagnostic and S5 application. Include unchanged results and deteriorations. Keep unrepeated analyses visibly labeled as v1-only.

Replace the reporting section with

> The manuscript’s primary evaluated product is CEY20 v2. A dedicated baseline subsection retains the original v1 target failures and hourly findings, including the boundary-discontinuity evidence that motivated smoothing. Tables present paired v1/v2 results for every repeated analysis using unchanged thresholds, denominators and reference definitions. Newly added diagnostics are identified with their amendment date.
>
> Unrepeated sensitivity, LOYO and FS analyses are labeled as analyses of unsmoothed constructions. The California comparison is identified as having already used v2 before this amendment.
>
> The v2 evaluation assesses a remedy developed after observing v1 outcomes at the same frozen points. Its results do not establish independent validation, climate-wide representativeness or production readiness.

The earlier constraints remain applicable, with these scope updates

- The nine annual failures, directional counts and sensitivity counts remain **v1 findings**. Report v2 counts separately.
- The original discontinuity finding remains part of the scientific record. Smoothing efficacy becomes evaluated only to the extent supported by the new results.
- LOYO interpretation, humidity qualifications, reference limitations and the prohibition on broad representativeness claims remain unchanged.
- Preserve the separate chronology of original target specifications, hourly diagnostic specifications and this outcome-informed amendment.

### 6. Make execution and failure handling reproducible

“One run per analysis” needs a correction policy. Otherwise a software defect can leave the protocol ambiguous.

Add

> Before execution, freeze the amendment, input inventories, analysis definitions and exact runner commit. Test product reading, packing comparisons, window endpoints, December–January wrap and paired metric computation using synthetic fixtures and independently check selected reconstructed values. Preserve the recorded distinct-role review.
>
> Preserve every attempted run’s code/input identity and disposition. A gate failure stops outcome evaluation pending documented resolution. Software corrections require a recorded explanation, a new code identity and rerunning all affected outputs. Any change informed by v2 outcomes is recorded as a further amendment and labeled accordingly.

These changes permit a defensible v2-primary manuscript while retaining the chronology and evidential limits of the original study.