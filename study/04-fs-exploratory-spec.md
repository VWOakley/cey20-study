# AUTH-003 S4: exploratory FS-based selection at the S3 points (specification, pre-computation)

Status: FROZEN 2026-11-05 after Codex review (2026-11-04); section 6a added 2026-11-05 before any
calculation. Nothing has been computed.
Operator 2026-11-01 (board AUTH-003:S4): exploratory addition; FS-based selection at the same 14 points,
same data 2006-2025 at 0.25 degree, same targets 1/2 and diagnostics D1-D5 as CEY20; definition
committed before any calculation; result labelled exploratory; it does not replace the CEY20 baseline.

## 1. Purpose and claims

Compare the CEY20 selection (weighted L1 distance of 10 monthly features) with an established family of
methods (Finkelstein-Schafer on daily indices, as in the Sandia/TMY2/TMY3 family and ISO 15927-4) on
identical data and identical evaluation. Allowed conclusions: which method meets targets 1/2 at these
14 points and how the prespecified diagnostics on the same data differ. Not allowed: superiority in general, conformity with
TMY3 or ISO 15927-4, or any statement about solar/energy use (radiation and wind are out of scope).

## 2. Data, points, conventions, gates

Identical to S3 (`03-study-protocol.md`, `03-freeze.json`): the 14 frozen points, ERA5-Land 2006-2025
from the pinned inputs with content SHA-256, UTC hours and UTC days, 365-day calendar with 29 February
removed from every candidate and reference year, water-relative RH (Bolton 1980 Magnus, as in the
builder), same eligibility rules. A new runner file is added to a separate pin before the run.

## 3. Daily indices

Per UTC day, from hourly T and Td: maximum, minimum and mean of T; maximum, minimum and mean of Td.

Variant **FS-A** (thermodynamic, TMY3-like): only these six indices.
Variant **FS-B** (exposure-oriented): FS-A plus three daily exposure counts, the number of hours per day
with RH >= 80 %, RH >= 90 % and T - Td <= 2 degC (integers 0-24; daily counts of hourly binary
indicators). The three counts overlap and are not three independent dimensions.

## 4. FS statistic

For calendar month m, index k and candidate year y: the long-term CDF is the empirical CDF of the daily
values of index k in month m over all 20 years (right-continuous: F(x) = #{values <= x} / N). The
candidate CDF is the empirical CDF of the n daily values of year y. Following Finkelstein and Schafer
(1971) as used in the TMY family:

    FS_k(y) = (1/n) * sum_{i=1..n} | F_cand(x_i) - F_lt(x_i) |,   x_i = the n daily values of year y

Ties are handled by the right-continuous definition on both sides, and F is evaluated at every candidate
daily value including repetitions. Required tests: tied values (the FS defect in BUG-016 concerned tie
handling), constant series, and identical distributions yielding FS = 0. The candidate is one calendar month
of one year; the long-term pool includes that candidate month (as in TMY3 practice).

Weighted sum: WS(y) = sum_k w_k * FS_k(y). Selection: the year with minimum WS; ties go to the earliest
year. No secondary ranking and no persistence screening. This is a declared deviation from TMY3 steps
2-4 (Wilcox & Marion 2008, s. 2.2). The five lowest-WS candidates are reported for transparency only.

## 5. Weights

FS-A: TMY3 relative weights of the temperature indices, renormalised after dropping wind and radiation:
T max 1, T min 1, T mean 2, Td max 1, Td min 1, Td mean 2, each divided by 8. Source: Wilcox & Marion 2008,
Table 2-1, NSRDB TMY column (T max/min/mean 1/20, 1/20, 2/20; Td the same; wind max/mean 1/20 each;
global and direct radiation 5/20 each; grouping 4:4:2:10). Confirmed by Codex review 2026-11-04.

FS-B: FS-A weights scaled to 1/2 in total, plus 1/6 each for the three exposure counts. Frozen weights:
T max, T min, Td max, Td min 1/16 each; T mean, Td mean 1/8 each; the three exposure counts 1/6 each.
Rationale: an equal split between the thermodynamic state and the exposure counts. This is a design
choice, not a literature value; confirmed by Codex before any run (2026-11-04). No tuning after outcomes.

## 6. Evaluation (identical to CEY20)

Targets 1 and 2 exactly as in `03-study-protocol.md` (annual exposure hours ±5 %, monthly means T
±0.5 degC, RH ±2 percentage points). Diagnostics D1-D5 exactly as in `03-diagnostics-spec.md`,
including the supplementary D4s. Results are reported side by side for CEY20, FS-A and FS-B, per point,
with every failure listed. Selection agreement with CEY20: the number of point-months with the same year.

## 6a. D5 for the FS variants (added 2026-11-05, pre-outcome)

D5 is defined for CEY20's monthly features. Its two conventions are applied to FS-A and FS-B as follows,
reported per method next to the CEY20 D5:

* **Local-solar days:** all daily indices of the variant are computed on full local-solar days (shift =
  round(lon/15) h as in `dtr_local_day`; partial edge days of the month are dropped); reselect; report
  the point-months whose selection changes and the Target-1 checks of that selection (builder formula).
* **Humidity convention:** the RH-based daily exposure counts use saturation over ice below 0 degC
  (`rh_mixed`); reselect; Target-1 checks with selection and reference counts under the mixed
  convention, as for CEY20. FS-A uses no RH index, so its selection is unchanged by construction.

The FS statistic aborts on any non-finite daily value; coverage 1.0 is already required by the gates.

Limitations stated in advance:
- CEY20's selection objective overlaps the targets 1/2 (its features include the target quantities);
  FS-B's exposure counts overlap the annual exposure targets too, FS-A's indices do not. Scores on
  targets 1/2 are therefore not a fair method comparison, and no ranking is implied.
- D1-D5 are prespecified diagnostics on the same data; some overlap selection quantities. They are not
  independent validation.

## 7. Process

1. Codex reviews this specification and confirms or changes the weights. The weight values are checked
   against Table 2-1. The specification is committed as frozen.
2. Runner `auth003_s4_fs.py` and tests (tied-value and synthetic FS cases) in `research/AUTH-003-S3-run`;
   Copilot code review; then the pin is committed (study/S3/hourly/D4s scripts, this runner and the S3
   `targets_monthly.csv`).
3. One run with the same gates; results under `04-results-fs/`; Codex review of the wording.
4. Labelling in the manuscript: "exploratory comparison"; it does not replace the CEY20 baseline.

The PVGIS-TMY and NOAA ISD comparisons of S4 (reference set AUTH-001:S1) are separate steps and are
specified separately.

## References

- Finkelstein, J. M. and Schafer, R. E. (1971): Improved goodness-of-fit tests. Biometrika 58(3), 641-645.
- Wilcox, S. and Marion, W. (2008): Users Manual for TMY3 Data Sets (Revised). NREL/TP-581-43156,
  sections 2.1-2.6 (https://www.osti.gov/biblio/928611).
- ISO 15927-4:2005, clauses 5.2-5.3.1 (preview only; no conformity claimed).
