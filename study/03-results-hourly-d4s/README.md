# AUTH-003 S3: D4s month-boundary jumps against observed 23→00 UTC changes (supplementary)

Supplementary to D4 (Codex R5); descriptive, no null model. It does not replace the prespecified D4 in
`03-results-hourly/`. Rules: `03-diagnostics-spec.md`, section "D4s Supplementary" (committed `e819c4a4`
before the run); code pin `03-s3-d4s-pin.json` (`617b4f87`); runner `auth003_s3_d4s.py` at `28784e80`.
Run 2026-11-04 07:14-11:10 UTC with the same gates as the hourly runner (code pin, input inventory and
SHA-256 of all 240 inputs, finite coverage 1.0, selection equal to `03-results/targets_monthly.csv`).

Reference per inner boundary: |23→00 UTC change| on the 31 midnights centred on the boundary (±15 days) in
the 20 actual years (n ≤ 620; Feb→Mar in leap years excluded, n = 615). Dec→Jan wrap: the same midnights
across the 19 consecutive year pairs (n ≤ 589).

| Variable | inner boundaries above ref p99 (of 154) | rate | Dec→Jan wrap above ref p99 (of 14) |
|---|---:|---:|---:|
| Temperature | 101 | 65.6 % | 9 |
| Dew point | 95 | 61.7 % | 10 |
| RH | 84 | 54.5 % | 6 |

None of the 4 same-year inner boundaries exceeds the reference p99 for any variable. Over the 164
cross-year joins (150 inner + 14 wrap), the median jump is 1.65 × ref p99 for temperature, 1.68 × for dew
point and 1.14 × for RH.

Inner-boundary exceedance rates are higher under D4s than D4 (44 %, 55 %, 36 %). The reference
definitions differ in hour matching, window width and treatment of removed leap days; these descriptive
results do not isolate their individual effects (the dew-point wrap count is 10 under D4s, 11 under D4).
The same-year results and median ratios are computed from `d4s_boundaries.csv`. Both are descriptive; neither rate is a calibrated
exceedance probability, and no expected count under a null model is claimed. The study evaluates the
unsmoothed v1 product; the released v2 product smooths month interfaces (BUG-018), which these numbers do
not assess.

Files: `d4s_boundaries.csv` (one row per point, boundary and variable: jump, percentile, ref_p99, ref_n,
above_ref_p99, same_year, years), `summary.json`, `manifest.json`.
