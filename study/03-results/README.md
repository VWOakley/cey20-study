# AUTH-003:S3 — first outcome run (pre-registered targets)

Run: `auth003_s3.py` at code 7d222a8 (pin 03-s3-code-pin.json), freeze 03-freeze.json (builder 00efaf6),
input SHA-256 03-freeze-input-sha256.json. Started 2026-10-31T10:41:56Z, finished 13:06:40Z, exit 0.
All pre-outcome gates passed (code pin, builder identity, 14 frozen points, inventory, content hashes, coverage 1.0).
Targets and thresholds were not changed after seeing these results.

## Target 1 — annual counts, |Hsel − Href| / Href ≤ 5 %

42 checks (14 points × 3 metrics), **9 fail**. All 9 failures underestimate the 20-year mean:

| Point | Metric | Hsel | Href | rel. error |
|---|---|---:|---:|---:|
| Phoenix | RH ≥ 80 % | 404 | 511.95 | −21.1 % |
| Phoenix | Td depression ≤ 2 °C | 188 | 229.5 | −18.1 % |
| Phoenix | RH ≥ 90 % | 112 | 136.05 | −17.7 % |
| Fairbanks | RH ≥ 90 % | 619 | 723.85 | −14.5 % |
| Denver | RH ≥ 80 % | 1136 | 1305.15 | −13.0 % |
| Denver | Td depression ≤ 2 °C | 610 | 685.1 | −11.0 % |
| Fairbanks | Td depression ≤ 2 °C | 1173 | 1308.7 | −10.4 % |
| Chicago | RH ≥ 90 % | 1007 | 1086.1 | −7.3 % |
| Denver | RH ≥ 90 % | 421 | 444.7 | −5.3 % |

Across all 42 checks, 25 are below and 17 above the reference.

## Target 2 — monthly means, |ΔT| ≤ 0.5 °C, |ΔRH| ≤ 2 points

168 point-months. **Temperature: 60 fail** (36 %). **RH: 14 fail** (8 %).
Median |ΔT| 0.31 °C, median |ΔRH| 0.59 points. Worst: Phoenix Oct ΔT +2.12 °C; Helsinki Jul +2.02 °C;
Chicago Dec −1.86 °C; Phoenix Feb ΔRH +4.22; Denver Feb −4.09.
T failures by point: Fairbanks 9, Helsinki 8, Houston/Chicago/Phoenix/Denver 6, Frankfurt/San Francisco 5,
Seattle/London 3, Dubai 2, Mumbai 1, Singapore and Quito 0.

## Leave-one-year-out (840 rows)

Median |rel. error vs 19-year reference| 1.1 %, 90th percentile 12.1 %, 82 % within 5 %.
On average 9.8 of 12 monthly selections are unchanged when a year is held out.

## Sensitivity (Target 1 failures out of 42)

Baseline 9. Single-feature ±25 %: 7–9. Joint moisture/thermal ±25 %: 7–8. Equal weights: 7.
Count block ×0.5: 9. **Count block ablated: 14.** Local inter-annual std scaling: 10.
Threshold brackets (RH 78/82, 88/92, Td-dep 1/3 °C): 7–8.

## Not produced in this run

Held-out hourly diagnostics (joint T/RH distribution, spells, drying gaps, month-boundary jumps) — separate step.

## Reading

The pre-registered targets are not met: annual counts 9/42, monthly temperature 60/168 and monthly RH 14/168
checks fail. The annual failures occur only at four of the 14 sampled points (Phoenix, Denver, Fairbanks,
Chicago), and all nine underestimate the reference; across all 42 annual checks there are 25 underestimates
and 17 overestimates, so there is no universal directional bias. Monthly temperature failures are spread over
12 of the 14 points, with Fairbanks and Helsinki highest. Any climate-class interpretation is exploratory.
Weight and threshold perturbations do not remove the annual failures; removing the count block raises their
number to 14. These results are reported as they are; the targets are not relaxed.

## Completeness

Gate evidence is in run.log and manifest.json (code pin, builder identity, frozen points, inventory, content
hashes, coverage). Reconciliation of all deliverables against 03-study-protocol.md is done in the manuscript
step (S5); until then the only declared outstanding item is the held-out hourly diagnostics.

## Review

Copilot (gpt-5.6-terra) reported sensitivity counts of 16-17, 8 and 10; a recount by variant (281 failures over
34 x 42 rows, 0 pass-flag inconsistencies) and Codex (gpt-6.1-sol) found these findings invalid. Codex's
manuscript constraints are in manuscript-constraints.md.
