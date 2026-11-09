**APPROVE WITH CHANGES.** The gate 5 deviation is acceptable. Freeze after the following replacements.

### 1. Make gate 5’s scope consistent

Gating Td ≤ T inside the smoothing mask is appropriate when gate 3 independently requires preservation of the reconstructed source outside it. The global violation count supplies context. It does not establish the provenance of each study-point violation.

Replace the final two bullets of gate 5 with

> - Outside the mask, count and report Td > T hours per point, including their maximum Td − T. Require their agreement with the reconstructed selected-source series under gate 3.
> - The Td ≤ T integrity requirement applies inside the smoothing mask. Reproduction of the pinned smoothing implementation separately checks how that constraint is enforced.

### 2. Clarify the overlap with prior v2 evidence

The disclosure of global evaluation results and study-point ramp magnitudes is necessary and appropriate. However, “no outcomes … have been computed” remains broader than the disclosed evidence supports. Continuity and modification checks overlap with the planned evaluation even if the final paired analyses remain unrun.

Replace the first blockquote and implementing-session confirmation with

> This amendment was declared on 2026-11-09 after the v1 S3, S4-part-1 and S5 outcomes were known. The v1 boundary-discontinuity findings motivated the v2 smoothing intervention. Prior v2 evidence included the BUG-018 global evaluation, reported ramp-correction magnitudes at AUTH-003 study points, and the California comparison and data descriptor described below. This amendment is outcome-informed. The investigators must confirm and record which planned v2 analyses or component statistics had already been computed or inspected, and which remain uncomputed. Definitions, inputs and analysis code for the remaining analyses will be frozen before those analyses run.
>
> The implementing session (Claude, 2026-11-09) reports that it has read or computed no additional v2 values at the 14 points for this amendment. This statement concerns that session’s amendment work. Prior available evidence is disclosed below.

Replace “Those are global or summary development checks…” with

> These development checks provide prior evidence about v2 continuity, exposure-count changes and correction magnitudes, including at AUTH-003 study points. They overlap with components of the planned evaluation. The amendment adds the specified paired analyses under the frozen AUTH-003 definitions. Their interpretation must account for this prior evidence.

### 3. Resolve implementation details before freezing

The current sequence freezes the amendment before inspecting the implementation, although gate 4 explicitly requires resolving support exceeding 144 hours before freezing.

Replace the numbered execution steps with

> 1. Codex confirms the revised amendment, including gate 5.
> 2. Inspect the smoothing implementation at `388cfdb4`. Record the exact support and transformation required by gate 4, resolve any discrepancy affecting the analysis definitions, and complete the investigator confirmation of prior evidence.
> 3. Freeze the amendment and analysis definitions.
> 4. Implement the v2 reader and paired v1/v2 runner, with synthetic tests.
> 5. Obtain Copilot review and resolve findings.
> 6. Pin the exact runner commit and input inventories before outcome evaluation.
> 7. Execute the pre-outcome gates. Run outcome evaluation only after all gates pass.

With these replacements, I approve freezing the amendment once the specified pre-freeze implementation inspection and prior-evidence confirmation are recorded. This review assesses the supplied text. The reported numerical results and artifact identities remain unverified here.