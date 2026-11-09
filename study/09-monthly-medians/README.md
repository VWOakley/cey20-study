# Exploratory: selected annual counts against the sum of the monthly medians (14 S3 points)

Status: exploratory, post hoc (2026-11-07), prompted by an external review comment on the open sentence in data paper
section 4.3. Not part of the frozen S3 protocol; it changes no result. `monthly_medians.py` (run with the S3 study code
`research/AUTH-003-S10-california @ 5369f2e4`, frozen inputs of `03-freeze.json`, inventory check `verify_inputs`)
recomputes the selection per month and writes, per point and metric, the selected annual count, the 20-year mean and
the sum over the 12 months of the median of the 20 monthly counts (`monthly_medians.csv`), plus the per-month values
(`monthly_medians_by_month.csv`). The script aborts unless the selected and mean annual counts reproduce
`03-results/targets_annual.csv` (`h_selected` exactly, `h_ref` within rounding).

## Result (42 checks, 9 failed in S3)

| Point | Metric | Selected | Mean | Sum of monthly medians | Selected vs mean | Selected vs sum of medians | Sum of medians vs mean |
|---|---|---:|---:|---:|---:|---:|---:|
| Phoenix | RH ≥ 80 % | 404 | 511.9 | 410.0 | −21.1 % | −1.5 % | −19.9 % |
| Phoenix | T − Td ≤ 2 °C | 188 | 229.5 | 186.5 | −18.1 % | +0.8 % | −18.7 % |
| Phoenix | RH ≥ 90 % | 112 | 136.1 | 107.5 | −17.7 % | +4.2 % | −21.0 % |
| Fairbanks | RH ≥ 90 % | 619 | 723.9 | 674.0 | −14.5 % | −8.2 % | −6.9 % |
| Denver | RH ≥ 80 % | 1136 | 1305.2 | 1172.5 | −13.0 % | −3.1 % | −10.2 % |
| Denver | T − Td ≤ 2 °C | 610 | 685.1 | 613.0 | −11.0 % | −0.5 % | −10.5 % |
| Fairbanks | T − Td ≤ 2 °C | 1173 | 1308.7 | 1282.0 | −10.4 % | −8.5 % | −2.0 % |
| Chicago | RH ≥ 90 % | 1007 | 1086.1 | 1025.5 | −7.3 % | −1.8 % | −5.6 % |
| Denver | RH ≥ 90 % | 421 | 444.7 | 394.5 | −5.3 % | +6.7 % | −11.3 % |

- At all 9 failed checks the sum of monthly medians is below the mean; over all 42 checks in 20 (median gap +0.1 %).
- Within ±5 %: 33 of 42 selected counts against the mean, 39 of 42 against the sum of monthly medians; 6 of the 9
  failed checks are within ±5 % of the sum of monthly medians.
- Median absolute difference: 1.0 % against the mean, 0.8 % against the sum of monthly medians.

## Reading

Descriptive, 14 points, in-sample: more selected annual counts fall within ±5 % of the sum of the monthly medians than of
the annual mean. The exposure counts are also selection features, so the selected months are expected to be near
typical monthly values; this does not establish a mechanism, and the three failed checks still outside ±5 % of the sum
of monthly medians (Fairbanks RH ≥ 90 %, Fairbanks T − Td ≤ 2 °C, Denver RH ≥ 90 %) are not explained by it.
