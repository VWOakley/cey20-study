# S4 results: exploratory Finkelstein-Schafer comparison (run 1)

Status: revised after Codex review (chain auth003-s4-results-codex-cfd4d75cb7cd, GO with changes).

## What was run

One run of `auth003_s4_fs.py` under the frozen spec `04-fs-exploratory-spec.md` and the pin `04-s4-fs-pin.json`
(commit 184d8db7), on 2026-11-06 06:18–12:42 UTC, output `E:/ERA_DATA/auth003_s4_fs_run1`.

The comparison is exploratory and descriptive. It does not replace the CEY20 baseline. FS-A and FS-B are the
specified FS-based variants, without secondary ranking or persistence screening.

## Provenance

The manifest records `code_sha: null`. The pin lists SHA-256 hashes for five scripts and the S3 monthly target file,
together with source commit references and LF normalisation. These identify the pinned artifacts; the manifest and
run log do not themselves record that the executed files matched those hashes.

Evidence for the execution link, separated by kind:

- Code path (contemporaneous gate): the runner calls `verify_pin` and then `verify_input_hashes` before any outcome
  is computed, and exits on any mismatch. Neither gate writes a success line to the log; a completed run implies
  both passed.
- Start conditions (contemporaneous): the run was launched only if the checkout `research/AUTH-003-S3-run` was clean
  and the output directory did not exist.
- Retrospective check (2026-11-06, after the run): the checkout is still at 073d2b8e and clean, and the LF-normalised
  SHA-256 of all five pinned scripts equals the pin. Only one S4 output directory exists.
- Statements that nothing was tuned after outcomes rest on the study record and operator attestation, not on the log.
- Operator attestation (2026-11-06): one run, nothing adjusted after outcomes were seen. This is an attestation,
  not a log record.

## Consistency with S3

Retrospective row-level comparison (2026-11-06): the 42 annual and 168 monthly CEY20 target rows in this run are
identical to `03-results/targets_annual.csv` and `03-results/targets_monthly.csv` in every shared column. The
aggregate counts are 9/42 annual exposure, 60/168 monthly temperature and 14/168 monthly RH failures, as in S3.

## Results

| Method | Target 1 annual failed | Target 2 monthly T failed | Target 2 monthly RH failed | Same year as CEY20 |
|---|---|---|---|---|
| CEY20 | 9 / 42 | 60 / 168 | 14 / 168 | – |
| FS-A | 13 / 42 | 35 / 168 | 52 / 168 | 48 / 168 point-months |
| FS-B | 13 / 42 | 49 / 168 | 36 / 168 | 72 / 168 point-months |

Descriptive medians: annual absolute exposure errors pooled over 42 point–metric checks per method; monthly absolute
mean-temperature and mean-RH errors over 168 point-months per method. The three exposure metrics overlap, so the 42
checks are not independent observations.

| Method | Median abs. annual exposure error (h) | Median abs. monthly ΔT (°C) | Median abs. monthly ΔRH (pp) |
|---|---|---|---|
| CEY20 | 31.7 | 0.31 | 0.59 |
| FS-A | 69.4 | 0.20 | 1.14 |
| FS-B | 67.0 | 0.28 | 0.87 |

Target 1 failures by metric (CEY20 / FS-A / FS-B): RH ≥ 80 % 2 / 5 / 3; RH ≥ 90 % 4 / 4 / 6;
dew-point depression ≤ 2 K 3 / 4 / 4.

## Reading

1. Across these 14 points under the frozen targets, the aggregate results show different balances of temperature,
   RH and exposure errors. FS-A has fewer monthly temperature failures than CEY20 (35 vs 60) and a smaller median
   monthly |ΔT|. CEY20 has fewer annual exposure failures (9 vs 13) and fewer monthly RH failures (14 vs 52).
2. Relative to FS-A, FS-B has fewer monthly RH failures (36 versus 52), more monthly temperature failures (49 versus
   35), and the same total annual exposure failures (13/42). Annual failures differ by metric: RH ≥ 80 % decreases
   from 5 to 3, RH ≥ 90 % increases from 4 to 6, and dew-point depression ≤ 2 K remains at 4.
3. The FS variants choose different source years from CEY20 in most point-months (FS-A 120/168, FS-B 96/168).
4. D5 conventions: local solar days change 4 CEY20 point-months, 25 FS-A and 37 FS-B point-months. The mixed
   water/ice humidity convention changes 9 CEY20 and 9 FS-B point-months and no FS-A point-months. FS-A uses
   temperature and dew point only, so an RH convention cannot change its selection.
5. D1 reports, per point, the fraction of the 20 actual years whose joint T/Td distance to the pooled distribution
   is less than or equal to the selected composite's distance. Median Hellinger percentiles are 0.00, 0.00 and 0.05
   for CEY20, FS-A and FS-B, respectively. The composite has a strictly smaller Hellinger distance than every actual
   year at 9/14, 8/14 and 6/14 points, respectively. Median total-variation percentiles are 0.00 for all three
   methods. These are descriptive comparisons against the same pooled reference, not independent validation.

## Limits

- 14 points, one run, one frozen weighting per FS variant; no uncertainty interval for the counts.
- The targets were frozen in S3 for CEY20, whose selection features overlap the evaluated target quantities. FS-B's
  daily exposure counts also overlap the annual exposure targets; FS-A uses daily T/Td indices. Target pass/fail
  counts therefore describe performance against these frozen requirements, not a fair overall ranking of methods.
  D1–D5 use the same data, and some overlap selection quantities; they are not independent validation.
- This study makes no claim of TMY3 or ISO 15927-4 conformity, solar/energy suitability, or general superiority.
- No claim beyond these points, months and targets.

## Open before S6

- Publication copy with relative paths: `manifest_public.json`. Closed.
- Run environment: `../06-run-environment.json` (recorded after the run; not independently verified as unchanged). Closed.
- D2–D4/D4s CSVs and the runner tests were not part of this review.

## Files

`selection.csv`, `top5.csv`, `targets_annual.csv`, `targets_monthly.csv`, `d1_joint.csv`, `d2_spells.csv`,
`d3_humid_temperature.csv`, `d4_boundaries.csv`, `d4s_boundaries.csv`, `d5_conventions.csv`, `d5_selection.csv`,
`summary.json`, `manifest.json`, `run.log`.
