# AUTH-003 S3: predeclared study protocol (frozen before outcomes)

Status: agreed between Codex (S7 preliminary review, 2026-10-31, `work/auth003-s7-review-20261031/REVIEW.md`)
and Claude; operator Wadim Okley. This file is hashed into `03-freeze.json` before any
outcome is computed. Changes after the freeze are recorded as amendments, never edited in place.

## Scope and honesty statement

- Bounded **pilot** of 14 locations, not a statistically representative global validation panel.
- Eight of the points (the city points) were already inspected for variability-proxy shares
  (01-method.md section 6). The study is therefore **not** a fully blind preregistration;
  this is disclosed.
- Targets below are **engineering targets**, not ISO requirements, confidence intervals or
  field accuracy. Failing them informs the study; it does not authorise changing weights or
  rebuilding the product.

## Locations (requested coordinates, fixed)

| Location | Latitude | Longitude | Stratum |
|---|---:|---:|---|
| Singapore | 1.3521 | 103.8198 | humid tropical, coastal |
| Mumbai | 19.0760 | 72.8777 | monsoon, coastal |
| Dubai | 25.2048 | 55.2708 | hot arid, coastal |
| Houston | 29.7604 | -95.3698 | humid subtropical |
| Frankfurt | 50.1109 | 8.6821 | temperate continental-maritime |
| London | 51.5074 | -0.1278 | temperate maritime |
| Seattle | 47.6062 | -122.3321 | maritime |
| San Francisco | 37.7749 | -122.4194 | cool maritime, coastal |
| Helsinki | 60.1699 | 24.9384 | cold, coastal |
| Fairbanks | 64.8378 | -147.7164 | subarctic continental |
| Chicago | 41.8781 | -87.6298 | humid continental |
| Phoenix | 33.4484 | -112.0740 | hot arid |
| Denver | 39.7392 | -104.9903 | semi-arid, elevation |
| Quito | -0.1807 | -78.4678 | equatorial, high elevation |

The nearest existing 0.25 degree land point is resolved **once** (great-circle distance, as in
the city builder) and recorded with actual coordinates, distance and index in `03-freeze.json`.
No cell is substituted after outcomes are seen; coastal or elevation mismatch is reported as a
limitation.

## Conventions (identical on both sides of every comparison)

Same cell; UTC hours and UTC days; water-relative RH (Bolton 1980 Magnus, as in the builder);
thresholds RH >= 80 %, RH >= 90 %, T - Td <= 2 degC; 365-day calendar with 29 February removed
from every candidate **and** every reference year.

## Eligibility (checked before outcomes)

For each point, all 20 years x 12 months must have finite T and Td for every hour used and
complete, strictly ordered, gap-free hourly timestamps starting at the month start (UTC).
Otherwise the point is **ineligible/UNKNOWN** and investigated; missing hours are never treated
as zero exposure.

## Acceptance targets

1. Annual exposure hours, per point and metric (RH >= 80 %, RH >= 90 %, T - Td <= 2 degC):
   Href = mean of the 20 non-leap annual counts. If Href > 0: |Hselected - Href| / Href <= 0.05.
   If Href = 0: Hselected = 0. Report signed hours, absolute hours and relative error (N/A at
   zero). No hidden absolute-hour floor; sparse events may fail this strict target intentionally.
2. Monthly means, per point and calendar month: |T_sel - T_ref| <= 0.5 degC and
   |RH_sel - RH_ref| <= 2 percentage points, where the reference is the mean over the 20 years.
   No averaging across months or points to hide individual failures; report every failure and
   the worst case.

Selection-feature agreement is in-sample representativeness, not independent validation.

## Held-out diagnostics (reported, no binary limits invented afterwards)

Joint T/RH distributions; humid-spell lengths and drying gaps; temperature during humid hours;
month-boundary jumps; sensitivity to UTC vs local-solar days and to the humidity convention.

## Sensitivity and stability (from 01-method.md section 6)

Equal weights; each weight -25 %/+25 % one at a time plus a bounded set of joint perturbations;
local-std scaling as comparator; count-block ablations and rescaling; threshold brackets
RH 78/80/82 %, 88/90/92 %, D 1/2/3 degC; fixed 20-fold leave-one-year-out: exclude each year
from both the candidate pool and the climatology, rebuild the selection and evaluate on that
held-out year (stability and out-of-sample variability, not guaranteed closeness to any year).

## Reporting rules

Preserve the baseline; publish negative results; label any later threshold change exploratory.
Publication remains gated on these findings, the data-completeness checks and an explicit
disclosure that the generating commit of the delivered CEY20 artefacts is UNKNOWN.
