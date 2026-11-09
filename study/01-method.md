# AUTH-003 S1: CEY20 representative-year method, as implemented

Status: draft for AUTH-003:S1. Author of this draft: Claude (implementation).
Weights/scales rationale: retrospective, agreed with Codex 2026-10-30 (section 6). S7 preliminary review by Codex 2026-10-31 applied (R1-R3); full S7 after S3; not published.
Code basis: commit `18e208a`, `backend/scripts/build_global_cey20_landpoint_dataset.py`
(abbreviated `B` below; line numbers refer to that commit). The builder file is byte-identical
at `18e208a` and at the study commit `00efaf6` (`git diff 18e208a 00efaf6 -- <B>` is empty).

## 1. Scope

CEY20 ("Climetry Environmental Year", 2006-2025) is an hourly representative year for
environmental-exposure screening (humidity, condensation, temperature). It is **not** a
solar TMY: no radiation, wind or precipitation variables enter the selection. This is a
deliberate scope decision (operator, 2026-10-30), not an omission.

CEY20 is distinct from two other code paths in the repository:

| Path | Selection | Used for |
|---|---|---|
| `B` (this document) | weighted, scaled L1 feature distance | CEY20 product |
| `backend/scripts/build_city_cey10_from_era5_land_hourly.py` | weighted Finkelstein-Schafer (FS) | city CEY10 pages (affected by BUG-016) |
| `backend/app/climate/cey.py` | weighted FS | PoC / library (BUG-016) |

The public methodology page currently describes the FS variant for CEY selection (BUG-017).

## 2. Input data

- Source: ERA5-Land hourly, read from packed monthly NetCDF files
  `era5_land_hourly_0p25_landpoints_{year}_{month}.nc` (B:32-38, 158-167).
  Variables: 2 m temperature and 2 m dew point (stored as 0.01 degC integers) and
  surface pressure (0.1 hPa integers) (B:245-272).
- Grid: land points of the packed **0.25 degree** product, identical coordinates and order
  for every year/month (validated, B:183-235). B takes the grid from its inputs and does not
  itself check grid spacing or point count; the following delivery facts come from Codex's
  inspection of the delivery, not from B. The inspected local point-major CEY20
  delivery is itself on this 0.25 degree grid (354,592 points; 671 latitudes x 1,440
  longitudes); the delivery builder preserves coordinates and selected years and does not
  interpolate or transfer selections (Codex S7-R1). No transfer to the native 0.1 degree
  ERA5-Land grid was found; native-grid rebuilding (DATA-001) is **not** an implemented step
  of this product. **Study scope (operator, 2026-10-31): this study describes and evaluates the
  current 0.25 degree CEY20 only.** A 0.1 degree build is planned (source downloads in progress)
  and is outside this study; it may be mentioned only as future work. Identity of the production/R2 copy with the inspected local delivery is
  unverified without manifest/hash linkage.
- Period: candidate years 2006-2025 (20 years), assembled from two archives
  (2006-2014 and 2025 from the CEY20 extension, 2015-2024 from the CEY10 archive; B:29-31, 158-167).
- Time base: hours since 2001-01-01 00:00:00 (B:374; the unit string carries no time-zone
  marker, and B does not read source timestamps). ERA5-Land is distributed in UTC; that the
  inputs start at the UTC month start and are hourly and gap-free is checked by the study
  (S3 eligibility, `03-freeze.json`), not by B; months use the hour count of non-leap 2001
  (B:477-478). For February every candidate is truncated to its first 672 hours, so
  29 February of leap years is dropped (B:252-272). The year therefore has 8,760 hours.

## 3. Derived hourly quantities

With T = temperature, Td = dew point (degC):

- Saturation vapour pressure (Magnus, coefficients of Bolton 1980), over liquid water for
  all temperatures, also below 0 degC (B:310-317):
  e_s(T) = 6.112 exp(17.67 T / (T + 243.5)) hPa
- Relative humidity RH = 100 e_s(Td) / e_s(T), clipped to [0, 100] % (B:320-325)
- Absolute humidity AH = 216.7 e_s(Td) / (T + 273.15) g/m^3 (B:328-331)
- Dew-point depression D = T - Td (B:289)

## 4. Monthly features

For each land point p, calendar month m and candidate year y, ten features f_k(y) are
computed from that month's hours (definitions B:284-301; weights and scales B:42-65):

| k | Feature | Definition | Weight w_k | Scale s_k |
|---|---|---|---|---|
| 1 | temperature_mean_c | mean T | 1.5 | 8.0 degC |
| 2 | temperature_p95_c | 95th percentile T | 0.8 | 10.0 degC |
| 3 | relative_humidity_mean_pct | mean RH | 1.5 | 20 %-pt |
| 4 | relative_humidity_p90_pct | 90th percentile RH | 1.0 | 20 %-pt |
| 5 | absolute_humidity_mean_g_m3 | mean AH | 1.0 | 8.0 g/m^3 |
| 6 | dewpoint_depression_p10_c | 10th percentile D | 0.8 | 8.0 degC |
| 7 | hours_rh_ge_80 | count of hours with RH >= 80 % | 1.2 | 180 h |
| 8 | hours_rh_ge_90 | count of hours with RH >= 90 % | 1.0 | 120 h |
| 9 | hours_dewpoint_depression_le_2c | count of hours with D <= 2 degC | 1.0 | 120 h |
| 10 | daily_temperature_range_mean_c | mean over days of (max T - min T) | 0.7 | 8.0 degC |

Sum of weights: 10.5. Percentiles use NumPy's default linear interpolation; means and
percentiles ignore missing values, counts treat missing values as "not exceeded".
Missing values can, however, fail **before** they reach these rules: `_read_scaled`
(B:245-249) calls `filled(np.nan)` on the packed int16 masked array before casting to float,
which raises `TypeError` for masked integer input (Codex S7-R3, reproduced synthetically).
Complete, finite, ordered hourly input is therefore a prerequisite for the study (S3), not
an assumption; the builder's hour-count check alone does not prove continuous timestamps,
absence of duplicates or chronological February order.
Days for feature 10 are consecutive 24-hour blocks of the input hour order (B:334-337); with
UTC-anchored inputs (checked in S3, see above) these are **UTC** days, not local days.

## 5. Selection rule

Climatology per feature: the arithmetic mean over all 20 candidate years, including the
candidate itself: c_k = mean_y f_k(y).

Score of candidate year y:

    S(y) = sum_k  w_k * |f_k(y) - c_k| / s_k

The year with the smallest S is selected (B:302-307). Scales s_k are **fixed global
constants**, the same for every land point and month; they are not the interannual
standard deviation at that point. Ties go to the earliest year (first minimum along the
year axis, ordered 2006 to 2025). The selected month's hourly values are copied unchanged;
months are concatenated without smoothing at month boundaries. The selection score is
stored per point and month (hourly copy B:350; selected year and score B:351-354; selection
file B:420-424).

## 6. Rationale for weights and scales (agreed with Codex, 2026-10-30)

Provenance: no rationale is recorded in the repository; the constants arrived in one squash
commit (`a6e1720`, 2026-10-18) without documentation. The rationale below is
**retrospective** (Claude draft, reviewed by Codex gpt-6.1-sol, mailbox chain
`auth003-weights-codex-ce79a88c948e`). It is not contemporaneous design evidence and no
formal expert elicitation took place.

Nominal weights (sum 10.5): moisture-related features k = 3-9 carry 7.5 (71.4 %), thermal
level and variability k = 1, 2, 10 carry 3.0 (28.6 %); the three exceedance-hour counts
k = 7-9 carry 3.2 (30.5 %). Only the ratios w_k / s_k determine the ranking: multiplying all
weights or all scales by a common factor changes nothing, and a scale change can reproduce
a weight change. Per-unit penalties:

| Feature | w/s | Note |
|---|---|---|
| T mean | 0.1875 per degC | |
| T p95 | 0.08 per degC | |
| RH mean | 0.075 per %-pt | |
| RH p90 | 0.05 per %-pt | |
| AH mean | 0.125 per g/m^3 | |
| D p10 | 0.10 per degC | |
| h RH>=80 | 0.00667 per h | 1 score unit per 150 h |
| h RH>=90 | 0.00833 per h | 1 unit per 120 h; 25 % more per hour than RH>=80 |
| h D<=2 degC | 0.00833 per h | same per-hour penalty as RH>=90 |
| DTR mean | 0.0875 per degC | |

Codex assessment per feature: the **inclusion of every feature is qualitatively
defensible** for moisture/thermal exposure screening (mean T and RH anchor the thermo-hygric
state; upper tails and exceedance counts protect humid-hour exposure; D p10 and the
D<=2 degC count proxy near-saturation; DTR adds thermal variability), but **no numerical
weight/scale pair is supported by calibration or documented elicitation**. The constants
must be presented as expert-set engineering parameters, not optimised coefficients.
Caveats: RH>=80 h is not standardised time of wetness (ISO 9223 adds a temperature
condition); 2 degC dew-point depression is not a universal condensation threshold; ambient
RH and D cannot establish surface condensation or corrosion; the three counts are nested or
overlapping and are not three independent exposure dimensions; AH overlaps with T and Td.

### Variability-proxy shares (exploratory)

Measurement (Claude, 2026-10-30, read-only, builder code unchanged; reproducible with
`docs/research/auth003-tmy/tools/cey20_effective_weights.py`, which imports the builder's own
loader and humidity functions): for each feature,
w_k * sigma_k / s_k with sigma_k the interannual population standard deviation (NumPy
default, ddof = 0) of the monthly feature over 2006-2025; these amplitudes were **averaged
over the 12 months first and then normalised to 100 %** (not the mean of monthly
normalised shares), at the ERA5-Land land point nearest to each city. These are
**variability-proxy shares**, not actual score contributions and not causal selection
effects (L1 contributions depend on absolute departures; selection also depends on feature
correlations and score margins). Eight points are illustrative, not a climate sample.

| Point | T mean | T p95 | RH mean | RH p90 | AH mean | D p10 | h RH>=80 | h RH>=90 | h D<=2 | DTR | sum of 3 counts |
|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal (w only) | 14.3 | 7.6 | 14.3 | 9.5 | 9.5 | 7.6 | 11.4 | 9.5 | 9.5 | 6.7 | 30.5 |
| Singapore | 4.9 | 2.6 | 8.0 | 2.4 | 3.7 | 0.9 | 20.3 | 27.7 | 27.4 | 2.0 | 75.4 |
| Dubai | 8.3 | 4.7 | 18.0 | 12.2 | 7.9 | 4.8 | 15.0 | 11.2 | 12.6 | 5.4 | 38.8 |
| Houston | 9.6 | 4.3 | 14.0 | 3.4 | 5.8 | 1.2 | 17.6 | 20.1 | 20.6 | 3.3 | 58.3 |
| Seattle | 11.5 | 7.0 | 11.5 | 3.2 | 3.6 | 1.0 | 17.1 | 20.3 | 20.8 | 4.1 | 58.2 |
| Frankfurt | 13.3 | 7.2 | 13.2 | 5.3 | 3.7 | 1.8 | 18.0 | 16.0 | 18.1 | 3.4 | 52.1 |
| London | 11.8 | 6.6 | 9.9 | 3.6 | 3.7 | 1.1 | 17.4 | 20.7 | 22.2 | 2.9 | 60.3 |
| San Francisco | 8.6 | 6.6 | 16.0 | 3.9 | 3.7 | 1.3 | 18.5 | 17.3 | 19.3 | 4.8 | 55.1 |
| Mumbai | 6.4 | 3.5 | 12.6 | 5.4 | 5.5 | 2.0 | 19.6 | 19.5 | 21.7 | 3.7 | 60.8 |

Observation: under the fixed scales the three hour counts account for about 52-75 % of the
proxy at seven of eight points and 39 % at arid Dubai, against 30.5 % nominal; RH p90, D p10
and AH carry little. Codex classifies this as an **undocumented consequence of the
weight/scale choice requiring validation**, neither a proven defect nor an established
design intention. Risks: selection driven by threshold counts while tail magnitudes, event
durations and joint T-RH conditions are not matched; threshold sensitivity near 80/90 % RH
and 2 degC; climate- and month-dependent priorities; loss of persistence.

### Requirements for the study (AUTH-003:S3, from the Codex review)

1. Document exact constants, units, thresholds, operators, percentile definition and score
   equation; state that the original rationale is unavailable and this one is retrospective.
2. Report w/s next to nominal weights with the physical-unit trade-offs (table above).
3. Reproduce the proxy shares with stated std convention, missing-data handling, point
   coordinates and aggregation order; label them variability-proxy shares.
4. Climate-stratified sample (cold, arid, maritime, continental, tropical, high elevation):
   proxy shares, **actual normalised score contributions** for all and for selected
   candidates, feature correlations, best-vs-runner-up margins, seasonal patterns.
5. Equal weights (this does not equalise influence); each weight -25 %/+25 % one at a time
   plus a bounded set of joint perturbations.
6. Local-std scaling as a comparator only, with explicit rules for zero/small spread and
   completeness.
7. Feature-group ablations: drop each count, drop all three, keep each count alone; rescale
   the count block to a stated group priority with internal ratios kept.
8. Threshold brackets (RH 78/80/82 %, 88/90/92 %, D 1/2/3 degC), separately and combined,
   with the frequency of hours near each threshold.
9. Validation against the full 20-year reference with diagnostics **not used for
   selection**: hourly and joint T-RH distributions, humid-spell duration and drying gaps,
   temperature during humid hours, seasonal/annual exposure totals, month-junction jumps.
10. Report year turnover together with changes in physical exposure metrics and
    worst-performing strata; predeclare tolerances in application units before looking.
11. Sampling dependence via leave-one-year-out or year-block resampling with a documented
    protocol (only excluding the candidate from its own climatology rescales departures by
    20/19 and cannot change rankings).
12. Before publication: data completeness, cold-climate humidity convention, UTC-day effect,
    and provenance of delivered artefacts versus this builder.

### Criteria for a later product change (not decided here)

Keep the constants if the stated objective accepts the count emphasis and independent
diagnostics meet predeclared tolerances across climate strata. Consider a change only if
count redundancy or dominance causes material bias in exposure metrics or climate-specific
failures, and prefer a replacement only if it improves independent diagnostics across
climates and is stable under resampling. If failures stem from missing persistence or
joint-state information, weight changes may be insufficient. Any change needs its own
product ticket, a CEY20 version bump and a reproducible comparison with existing artefacts.

### Proposed preprint paragraph (Codex draft, adjusted to the actual aggregation)

> CEY20 selects calendar months using a weighted L1 distance between ten temperature and
> humidity summaries and their 2006-2025 means. Its weights and fixed global scales are
> treated as expert-set engineering parameters rather than statistically optimized
> coefficients; the original numerical rationale was not recorded, and the
> application-based rationale presented here is retrospective. The features emphasize
> ambient moisture exposure while retaining thermal level and variability. An exploratory
> analysis at eight land points found that the three humid/near-saturation hour counts
> accounted for approximately 39-75% of a normalized interannual-variability proxy,
> compared with 30.5% of nominal weight. These proxy shares are not actual score
> contributions or independent selection effects. They indicate climate-dependent emphasis
> requiring broader sensitivity and exposure-representativeness assessment; the constants
> are not established as optimal.

## 7. Differences from established reference-year methods

The established procedures are distinct and are compared separately (Codex S7-R2). Only
statements verified against the cited sources are entered; everything else is **PENDING**
and must not be filled by inference.

| Aspect | ISO 15927-4:2005 | Sandia method family / TMY2 / TMY3 (NREL) | CEY20 |
|---|---|---|---|
| Purpose | typical year for heating/cooling energy (ISO preview, cl. 1) | typical year for solar/building energy | screening of moisture/thermal exposure |
| Primary similarity | Finkelstein-Schafer statistic on daily values (cl. 5.2-5.3.1) | weighted Finkelstein-Schafer on daily indices (Wilcox & Marion 2008, s. 2.1-2.6) | weighted L1 distance of 10 monthly summary features |
| Secondary parameter / criteria | wind identified as secondary parameter (cl. 5.3.1); later ranking steps **PENDING** (clauses not in inspected preview) | ranking by closeness of monthly mean/median to long-term values, then persistence screening; TMY3 relaxes persistence relative to TMY2 | none |
| Month junctions | **PENDING** (not verified from inspected preview) | 6 h smoothing on both sides of month boundaries | none (months concatenated unchanged) |
| Variables | per standard (incl. radiation, wind) | incl. solar radiation and wind | T and humidity features only (not a solar TMY) |
| Leap day | **PENDING** | per implementation | removed by truncation |

References: ISO 15927-4:2005 preview (clauses 1, 5.1, 5.2, start of 5.3.1); Wilcox, S. and
Marion, W. (2008) Users Manual for TMY3 Data Sets, NREL/TP-581-43156, sections 2.1-2.6.
These are methodological adaptations for an exposure dataset and must be stated as such;
no conformity with ISO 15927-4 is claimed. ISO 15927-4 targets typical heating/cooling
energy, not extreme moisture-damage years.

## 8. Open points for verification

1. **Resolved (Codex S7-R1):** selection and the inspected delivery are both 0.25 degree; no
   0.1 degree transfer exists. Production/R2 identity with the local delivery: unverified.
2. Missing data: masked packed integers fail in `_read_scaled` before NaN rules apply
   (S7-R3); counts undercount NaN hours; an all-NaN point raises in `nanargmin`; inventory
   checks hour counts but not NaN completeness or timestamp order. A loader fix would be a
   separately scoped code change with regression tests, not a silent change to the studied
   algorithm.
3. UTC days for daily temperature range: effect on far-from-Greenwich points.
4. Magnus over water below 0 degC (Bolton 1980, eq. 10, liquid water): kept unchanged to
   reproduce the product; cold-climate sensitivity is assessed separately and documented as
   extrapolation. No validated temperature range is claimed.
5. Climatology includes the candidate year and uses the mean, not the median.
6. Deployed artefact provenance (Codex S7, answer to 8.6): the chain is identifiable -
   `build_global_cey20_landpoint_dataset.py` (selection, hourly NetCDF) ->
   `build_cey_hourly_point_major_delivery.py` (point-major delivery) ->
   `build_cey20_monthly_summaries.py` (summaries). The manifests record constants and source
   paths but **no producing Git commit**: the generating commit is **UNKNOWN**. Commit
   `18e208a` must not be claimed as the producer. The study discloses this; a bounded
   reproduction can establish reproducibility, not the original execution identity.
7. Earliest-year tie rule and the absence of month-junction smoothing: effect size.
