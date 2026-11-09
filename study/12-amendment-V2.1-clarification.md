# AUTH-003 amendment V2.1: implementation clarifications (before any v2 outcome)

Status: **APPROVED**, 2026-11-09. Codex chain `auth003-v21-codex-1dba115e3c35` approved C1–C3 without changes (`12-amendment-V2.1-codex.md`). Runner code reviews: Copilot rounds 1–2, chains `auth-003-copilot-8df27cdafd66` and `auth-003-copilot-a9b2e2cff9d7`; findings fixed in `fe9b617a` and `7862bdee`. Earlier draft status line follows.

Draft written 2026-11-09. Written while implementing the runner `auth003_v2_eval.py`
(`research/AUTH-003-S3-run` @ `461e5cb2`). No v2 outcome has been computed. Codex confirmation is needed before
the runner is pinned.

The frozen amendment V2 (r3) leaves three implementation points open. This document records how the runner resolves
them. It does not change any threshold, reference or definition.

## C1. D5 on version 2

**The issue.** V2 lists D5 among the analyses repeated on v2 ("input is the v2 product series"). D5 compares the
baseline selection with two convention variants:

- local-solar days;
- saturation over ice below 0 °C.

The two variants select different source years. A product series exists only for the baseline.

**Resolution.**

- **Baseline:** the v2 product series.
- **Variants:** each variant selection is assembled from the unsmoothed source months. The **same pinned smoothing
  function** (`smooth_cey20_month_interfaces.smooth_boundary` @ `388cfdb4`) is then applied with that variant's
  source years.
- **Counts:** annual exposure counts are taken from these smoothed series. The mixed-ice variant uses the mixed
  humidity convention, both for the counts and for its reference.
- This is the "smoothed construction" route named in Codex r0 finding 4. It concerns only these two D5 variants.
  Sensitivity, LOYO and the FS comparison stay unsmoothed, as frozen.

## C2. S5 centre gate replaced by gates 3–4

**The issue.** The S5 runner requires the product series at each region centre to equal the unsmoothed reconstruction
exactly. For v2 this fails by construction. S5 is therefore not run unchanged.

**Resolution.** The v2 runner calls the unchanged S5 functions directly: `application_rows`, `duration_curves`,
`monthly_point_values`, `spatial_summary` and `box_members`. In place of the centre gate:

- Gates 3 and 4 apply to all 14 points **and** the Iqaluit centre. Outside the mask, values must be exact; inside the
  mask, they must reproduce the pinned smoothing exactly.
- Regional envelopes read T and Td of all box members from the v2 product files. The centre context (actual-year
  minimum, median and maximum) is unchanged.

## C3. Definition of the smoothing mask in the gates

The mask comes from the pinned eligibility function (`eligibility`), separately per variable group:

| Variable group | Mask |
|---|---|
| T and Td | the 12-hour support x[b−6] … x[b+5] of every boundary with a T/Td-eligible window |
| Pressure | the same support, for every boundary with an eligible pressure window |

- **Not in the mask:** boundaries skipped as consecutive source hours, and windows that are non-finite or would give
  non-positive pressure. Their values must equal the reconstruction exactly (gate 3).
- **The Td ≤ T gate** applies inside the T/Td mask.
- **Bound:** the union of the masks is at most 144 positions per point.

## Runner tests (synthetic, 13)

- `boundary_hours` and the Dec→Jan wrap.
- J_b and M_b: cyclic, both outer increments included, x[b−8] excluded.
- Reproduction of the join-step reduction.
- Consecutive same-year boundaries unchanged; leap-year Feb→Mar and Dec→Jan smoothed.
- Gates:
  - exact reproduction passes;
  - tampering outside or inside the mask fails;
  - Td > T outside the mask is reported, not gated;
  - Td > T inside the mask fails.
- Counts and means equal the builder feature definitions; monthly tolerance boundaries.
- Manifest version, commit and clean tree; units, hourly time axis and coordinates.
- The pin rejects a changed inventory.
- Smoothing constants N = 6, W = 14, B = 7.
