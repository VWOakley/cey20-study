# Amendment A3 to 08-external-comparison-spec.md (r3): output-label defect, re-run

Date: 2026-11-07, after run1 had completed (outcomes seen). This amendment changes no method, threshold, input or
station set; it repairs an output label and repeats the identical computation.

## Defect found in run1
`evaluate()` returned each annual row with the key `candidate` holding the candidate's numeric value. `run()` merged
the row as `{"station_id": ..., "candidate": <label>, "status": "ok", **row}`, so the number overwrote the label
(C1_cey20 … C4_nsrdb). Consequences in run1: the `candidate` column of `annual.csv` holds numbers instead of labels,
and the annual block of `summary.json` counted no rows (`stations_available` 0, `annual_pass` [0, 0],
`annual_median_rel_error` null). Monthly, decomposition, station and convention outputs are not affected.

## Fix
Code commit `c59f349f` (research/AUTH-003-S10-california): the field is renamed to `value`; a test asserts that no
evaluate row carries a `candidate` key. Copilot review: code fix complete and correct; verification plan extended by
the summary check below (accepted).

## Re-run and verification
run2 uses the same command, inputs, freezes and gates as run1, with the pin `08-s4ext-pin-A3.json`. run1 stays on
disk unchanged as the record of the defect. run2 is accepted only if:
1. `stations.csv`, `monthly.csv`, `decomposition.csv` and `conventions.csv` are identical to run1;
2. `annual.csv` equals run1 in every row and column, with run1's numeric `candidate` column equal to run2's `value`
   column and run2's labels equal to the labels reconstructed from run1's fixed row order;
3. every annual field of run2 `summary.json` is recomputed from run2 `annual.csv` and matches, and every monthly
   field matches run1.
Results are reported from run2 only.

## A3.1 (same day): second defect in the summary, re-run as run3
run2 wrote all five CSV files (identical to run1; labels equal to the order reconstruction) and then stopped in
`json.dumps(summary)`: with the annual rows now labelled, `annual_under` summed numpy booleans and returned
`numpy.int64`, which is not JSON-serialisable. This path was unreachable in run1 because no annual rows matched.
`summary.json` and `manifest.json` of run2 were not written; run2 stays on disk as the record.

Fix: code commit `5369f2e4`. The summary block moved unchanged into `summarise()`, except `bool(...)` around the
comparison; a test json-round-trips the summary of numpy-valued rows and fails without the cast. Copilot: GO (all
values reaching `json.dumps` checked). run3 uses pin `08-s4ext-pin-A3_1.json` and is accepted under the three
conditions above, compared against run1. Results are reported from run3 only.
