# AUTH-003 S5: example regions and engineering screening applications (specification, pre-computation)

Status: FROZEN r4 2026-11-05, revised after Codex review (chain auth003-s5-spec-codex-4a8512db034f,
CHANGES REQUESTED). Operator 2026-11-05: add a group-E region (Iqaluit) and extract the Köppen labels from
the Beck et al. (2023) raster. Codex re-check (chain auth003-s5-spec-recheck-codex-f7f8baccd869): APPROVE WITH CHANGES; the requested
edits are applied in r4. Nothing of S5 has been computed.
Board acceptance (AUTH-003:S5): at least five climate regions spanning the Köppen range, including
regional envelopes; applications for thermal simulation (temperature duration curves, heat pump) and
environmental loading (humidity hours, time of wetness, condensation); labelled as screening, not
certification.

## 1. Purpose and claims

Show what the CEY20 product year (v1, the study product, ERA5-Land 2006-2025, 0.25 degree) gives for
typical engineering screening quantities, and where each quantity lies within the 20 actual years.
Allowed conclusions: per point and quantity, the CEY20 value, the actual-year range and its position in
it. Not allowed: design values, certification or conformity statements (ISO 9223, EN 14825), inference
about design extremes, return levels or rare-event reliability, or claims about locations other than
those evaluated.

## 2. Points, regions, data, conventions, gates

### 2.1 Application points

All 14 frozen S3 points, no subset. Data, calendar (365 days, 29 February removed), UTC hours, RH formula
(Magnus over water, as in the builder), gates (code pin, builder identity, inventory, content SHA-256,
coverage 1.0) and the CEY20 selection (must equal the S3 run) are identical to S3. Values are unrounded
float32 hourly 2 m air temperature T and dew point Td as loaded by the S3 code.

### 2.2 Regions

Seven illustrative regions cover all five major Köppen-Geiger groups A-E with selected subclasses; other
subclasses are not represented and the sample is not comprehensive coverage of the classification. The
operator added the group-E region Iqaluit on 2026-11-05 (its centre is a region centre only; the 14-point
application sample is not expanded). Six centres are frozen S3 points; the Iqaluit centre is the product
land point nearest (great circle) to the town coordinates 63.7467 N, 68.5170 W, at 0.91 km.

| Region | Centre point index | Centre lat, lon (deg) | Label (Beck et al. 2023, 1991-2020) |
|---|---|---|---|
| Singapore | 197100 | 1.50, 103.75 | Af |
| Dubai | 160629 | 25.00, 55.25 | BWh |
| Houston | 149373 | 29.75, -95.25 | Cfa |
| Frankfurt | 93901 | 50.00, 8.75 | Cfb |
| Helsinki | 60358 | 60.25, 25.00 | Dfb |
| Fairbanks | 41781 | 64.75, -147.75 | Dfb (the draft's provisional Dfc was not confirmed by the raster) |
| Iqaluit | 46334 | 63.75, -68.50 | ET |

Fairbanks is kept as a frozen region although it shares the label Dfb with Helsinki; no region is replaced
after the lookup.

A region contains every point of the product land-point set (the points of the v1 monthly files
`cey20_landpoints_monthMM.nc`, which define the land mask) with latitude in [lat - 1, lat + 1] and
longitude in [lon - 1, lon + 1] degrees of the centre, bounds inclusive. Boxes are not administrative
regions.

### 2.3 Köppen labels

Extracted 2026-11-05 before any S5 calculation from the Beck et al. (2023) 1991-2020 present-day raster
(figshare 10.6084/m9.figshare.21789074, version 2, CC BY 4.0; `koppen_geiger_tif.zip`, MD5
7fc2f5a15d4f5fe0ce59c9a9b502aa09 as published, SHA-256
bb84453d4541f1a0bc5a804ead83f483c19ce70f16a5197f6d3a7b6a63e65562; `1991_2020/koppen_geiger_0p00833333.tif`,
SHA-256 2130f0071dfb2904947d8ec3a0d807fac71004df76e769262004f1602e4d6a13; 43200 x 21600 pixels of 1/120 degree, origin 180 W, 90 N). Containing-pixel rule
without categorical interpolation: col = floor((lon + 180) x 120), row = floor((90 - lat) x 120); a centre
on a pixel edge belongs to the pixel to its south-east. Pixel, value and class per centre:
`05-koppen-centres.json`. A centre label does not classify the whole box or the grid-cell footprint.

### 2.4 Regional inputs

The v1 product month files hold hourly `temperature_c` and `dewpoint_c` (float32, time x point) for all
land points; their SHA-256 and the SHA-256 of `hourly_manifest.json` are recorded in the run manifest and
the inventory of files and variables is part of it. For each retained point and month: arithmetic mean
hourly T, arithmetic mean hourly RH (RH evaluated hourly before aggregation) and the number of hours with
RH >= 80 %, from all hourly samples. Every point-month must have exactly 24 times the number of days of
the month in the 365-day calendar, all finite; otherwise the run aborts (nothing is dropped or filled).
Pinned before calculation (`05-s5-inputs.json`): SHA-256, size and mtime of the 12 product month files,
SHA-256 of `hourly_manifest.json`, the variables used, the land-point count and the SHA-256 of the
float32 coordinate arrays (identical in all 12 files) that define the boxes. The run aborts on any
difference.

Gates: for the six centres that are frozen S3 points, the centre point's 8760 h series in the product
files must equal the S3 CEY20 series of that point. For Iqaluit, the centre CEY20 series is reconstructed
from the pinned reference sources and the product's recorded point-specific selected source years
(`selected_source_year`), using the same loader as S3, and must equal the product series exactly; its 20
actual-year series must pass the inherited calendar, finite-value and coverage gates. This additional
verification does not change the 14-point application sample.

## 3. Comparison convention and estimator

* Quantile estimator, used throughout: linear interpolation at index r = (n - 1)p in the ascending sorted
  sample, zero-based (numpy `percentile`, method "linear"). Percentiles are non-exceedance percentiles.
* For a scalar quantity q at a point: CEY20 value; minimum, median (frozen estimator) and maximum of the 20
  actual-year values; context percentile = 100 x #{y: q_y <= q_CEY20} / 20, ties included. This applies to
  all scalar outputs of A1-A4. Section 5 reports its own spatial summaries and centre-year context.
* Comparisons and categories are computed before any display rounding. CSV/JSON numerical outputs retain
  computation precision; presentation tables round temperatures and distances to 0.01 degC, RH to 0.01
  percentage points and degree hours to 0.01 degC h; counts remain integers. No rounded value feeds a
  calculation.

## 4. Applications (all 14 points)

**A1 Temperature duration curve.** Hourly T quantiles at p = 0.01, 0.05, 0.50, 0.95 and 0.99. Pooled
reference Q_pool: all 175 200 retained hourly temperatures of the 20 actual years at the point, equal
weights; the pooled reference includes the year being evaluated (no leave-one-year-out reference). For
the CEY20 series and each actual year y: D_y = max over k of |Q_y(p_k) - Q_pool(p_k)| with
p_k = (k - 0.5)/8760, k = 1..8760, in degC, with section 3 context from the 20 actual-year distances. The
duration curve is plotted in descending order against exceedance fraction 1 - p; the reported percentiles
remain non-exceedance values. The actual-year band is the pointwise minimum-maximum of the 20 actual-year
quantile curves on the frozen grid p_k.

**A2 Heat-pump screening.** Heating degree hours sum_h max(0, 15 - T_h) and cooling degree hours
sum_h max(0, T_h - 24), in degC h. Bases of 15 degC for heating and 24 degC for cooling are fixed
illustrative assumptions; degree hours do not estimate building demand, heat-pump electricity use,
capacity adequacy, COP, SCOP or defrost losses. Cumulative hours with T <= -7 degC, T <= +2 degC and
T <= +7 degC: three selected screening thresholds motivated by heating part-load test temperatures
associated with EN 14825; the +12 degC condition is not included. The counts are nested, not disjoint
bins, and they are not EN 14825 climate-bin calculations or a seasonal performance assessment.

**A3 Calculated time-of-wetness screening estimate.** tau = sum_h 1(RH_h > 80 % and T_h > 0 degC) x 1 h.
Level: tau1: tau <= 10 h; tau2: 10 < tau <= 250 h; tau3: 250 < tau <= 2500 h; tau4: 2500 < tau <= 5500 h;
tau5: tau > 5500 h. These thresholds follow ISO 9223:2012, informative Annex B, Table B.1. They describe
the calculated meteorological estimate, not measured surface wetness or a corrosivity category. Reported
additionally: the number of actual years, out of 20, assigned the same level as CEY20. No corrosion rate,
corrosivity category or conformity is inferred.

**A4 Air near-saturation and zero-crossing days.** Hours with T - Td <= 1 degC (unrounded hourly 2 m air
temperature and dew point, S3 conventions). This is an air near-saturation indicator, not a prediction or
count of surface-condensation events. UTC calendar days whose hourly minimum T is strictly below 0 degC
and hourly maximum T strictly above 0 degC; days reaching exactly 0 degC only do not qualify. These are
air-temperature zero-crossing days, not measured material freeze-thaw cycles. Month joins fall at UTC
midnight, so every day lies within one source month.

## 5. Regional envelopes

For each region and calendar month, over all points in the box, from the CEY20 product year of each point:
monthly mean T, monthly mean RH and monthly hours with RH >= 80 % (section 2.4). Reported per region and
month: number of points, minimum, 10th percentile, median, 90th percentile and maximum across points
(frozen estimator, equal weight per grid point, not area-weighted). For context, the same three
quantities at the centre point for each of the 20 actual years (minimum, median, maximum).

These envelopes describe spatial variation among product land-grid points within fixed geographic boxes.
Boxes can include multiple climate classes, elevations and coastal settings; their area and land coverage
differ. Each point has its own selected source year for each month, so the envelope does not represent a
simultaneous historical regional weather field. The centre's interannual range and the box's spatial
distribution describe different populations and are not equivalent uncertainty intervals.

## 6. Limitations stated in advance

* All quantities are screening values from 0.25-degree reanalysis; local, urban, coastal and mountain
  effects are not resolved.
* S5 uses the same source archive from which CEY20 was selected. Some quantities directly reuse selection
  features (RH >= 80 % hours); others share variables or are related functionals (A3 adds temperature
  conditioning to a high-RH count; the A4 1 degC count is nested within the 2 degC selection feature;
  monthly means and A1/A2 concern distributions targeted by the multi-feature selection). This is an
  in-sample descriptive assessment, not independent validation or out-of-sample predictive evidence.
  Threshold modifications do not remove this dependence.
* The 20-year range is an observed archive range, not a confidence interval, return-period estimate or
  guaranteed future bound. Empirical percentiles are descriptive ranks in this archive, not probabilities
  of future exceedance.
* Duration curves, degree hours and hourly threshold totals are invariant to reordering the retained
  hourly samples. Month concatenation nevertheless does not preserve continuous weather evolution across
  joins. These summaries cannot assess event persistence, equipment cycling, recovery, storage or other
  dynamic responses; S3 D4 addresses join discontinuities. No smoothing is applied (product v1).

## 7. Freezing, reporting and deviations

All points, boxes, masks, thresholds, estimators, pooled references and planned tables and figures are
frozen before computation. Every prespecified quantity is reported for every assigned point or region,
including zero counts and values outside the actual-year range. No replacement regions, thresholds or
summaries are chosen based on results. Failed gates and protocol deviations are recorded; a correction
that requires recomputation keeps the original run record and an explanation ("one run" means one frozen
analytical protocol, not a ban on documented bug corrections).

Planned outputs: `a1_duration.csv`, `a2_heat_pump.csv`, `a3_tow.csv`, `a4_saturation_zero_crossing.csv`,
`regional_envelopes.csv`, `summary.json`, `manifest.json`; figures for S6: duration curves (CEY20, pooled,
actual-year band) for the 14 points and monthly envelope plots for the regions.

## 8. Process

1. Done 2026-11-05: operator decisions (group E: Iqaluit; Beck raster lookup), label extraction, Codex
   re-check (APPROVE WITH CHANGES, edits applied), input pin `05-s5-inputs.json`. The specification is
   frozen with this revision.
2. Runner `auth003_s5_applications.py` and tests on `research/AUTH-003-S3-run`; Copilot code review; pin.
3. One run; results under `05-results/`; Codex review of the wording; figures for S6.

## References

* Beck, H. E. et al. (2023): High-resolution (1 km) Köppen-Geiger maps for 1901-2099 based on constrained
  CMIP6 projections. Scientific Data 10, 724.
* ISO 9223:2012, Corrosion of metals and alloys - Corrosivity of atmospheres - Classification,
  determination and estimation; informative Annex B, Table B.1 (time-of-wetness levels).
* EN 14825 (heat pumps, part-load testing and seasonal performance); only the heating part-load test
  temperatures -7, +2 and +7 degC are used as screening thresholds. Edition and table to be verified
  before citation in S6.
