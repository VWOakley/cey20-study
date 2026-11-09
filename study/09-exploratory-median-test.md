# Exploratory: do the failed annual checks reflect "median instead of mean" selection?

Status: exploratory, post hoc (2026-11-07), prompted by a literature summary that explains the underestimation of
rare humid hours by right-skewed annual counts (median below mean). Not part of the frozen S3 protocol; it changes no
result. Data: `03-results/targets_annual.csv` and the 20 annual counts per point and metric in `03-results/loyo.csv`
(`h_held_out_year`), whose mean reproduces H_ref for all 42 checks.

## Result (annual median of the 20 years; n = 42 checks, 9 failed)

| Point | Metric | Selected | Mean | Median | (median − mean)/mean | Error vs mean | Error vs median |
|---|---|---:|---:|---:|---:|---:|---:|
| Phoenix | RH ≥ 80 % | 404 | 511.9 | 499.5 | −2.4 % | −21.1 % | −19.1 % |
| Phoenix | T − Td ≤ 2 °C | 188 | 229.5 | 215.5 | −6.1 % | −18.1 % | −12.8 % |
| Phoenix | RH ≥ 90 % | 112 | 136.1 | 127.0 | −6.7 % | −17.7 % | −11.8 % |
| Fairbanks | RH ≥ 90 % | 619 | 723.9 | 699.0 | −3.4 % | −14.5 % | −11.4 % |
| Denver | RH ≥ 80 % | 1136 | 1305.2 | 1285.5 | −1.5 % | −13.0 % | −11.6 % |
| Denver | T − Td ≤ 2 °C | 610 | 685.1 | 685.5 | +0.1 % | −11.0 % | −11.0 % |
| Fairbanks | T − Td ≤ 2 °C | 1173 | 1308.7 | 1354.5 | +3.5 % | −10.4 % | −13.4 % |
| Chicago | RH ≥ 90 % | 1007 | 1086.1 | 1048.0 | −3.5 % | −7.3 % | −3.9 % |
| Denver | RH ≥ 90 % | 421 | 444.7 | 443.5 | −0.3 % | −5.3 % | −5.1 % |

- Among the 9 failed checks the annual median lies below the mean in 7; among the 33 passed checks in 14.
- Correlation between the gap (median − mean)/mean and the signed error, over all 42 checks: r = 0.56. Descriptive
  only: the 42 checks are three overlapping metrics at each of 14 points, and both quantities share the reference
  mean in their construction. Not reported in the data descriptor (Codex, chain auth003-median-para-codex-39dfc9ff0c9b).
- The gaps are small (−6.7 % to +3.5 %) compared with the errors (−5.3 % to −21.1 %). Measured against the median, 8
  of the 9 selected values still lie more than 5 % below it (median |error| 11.6 % vs 13.0 % against the mean).

## Reading

Using the annual median as reference leaves most failed checks below the −5 % tolerance; a median–mean difference is
not a direct measure of skewness, and this comparison does not establish a mechanism. Most of
the underestimation remains when the median is used as reference. The stronger version of the hypothesis, that the
selected year approaches the sum of the **monthly** medians, is not tested here: per-year monthly counts are not
stored in the S3 outputs, and computing them requires reading the 240 frozen source files again. 14 points; no
inference beyond them.
