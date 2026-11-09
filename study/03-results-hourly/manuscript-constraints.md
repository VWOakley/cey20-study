# Manuscript constraints from the S3 hourly diagnostics review (Codex, 2026-11-01)

1. State that definitions were fixed before hourly diagnostic computation but after the S3 selection run; no diagnostic pass/fail limits were predefined.
2. Limit conclusions to the frozen 14 points, 2006–2025 source period, UTC/365-day calendar and builder humidity convention. Reproducible output does not establish scientific validity.
3. Report the corrected D2 exception, tied-rank limitation and shorter-mean-spell pattern; within-range statistics do not establish preserved temporal structure.
4. Report D4 inner and cyclic-wrap results separately, with denominators, variable-specific rates, reference definition and unmatched-hour limitation. Avoid a calibrated 1% null or significance claim.
5. Explain that removing 29 February can create nonconsecutive source-hour transitions. Confirm whether these enter the February/March reference and qualify or supplement that reference accordingly.
6. Present D5 as sensitivity analyses; eight versus nine Target-1 failures under different humidity conventions compares changed definitions as well as changed selections. Retain the UNVERIFIED coefficient qualification.
7. Describe large synthetic join discontinuities as an observed continuity limitation, while distinguishing measured jumps from untested application impacts, remedies and production artifact verification.

Product issue: yes — Report the large cross-year month-join discontinuities to the operator as a separate hourly-continuity issue. Their magnitudes justify investigation without a calibrated exceedance test. Identify the affected builder/version and reproduce examples in the published artifact before asserting that publication is verified affected; downstream severity and smoothing efficacy remain untested.
