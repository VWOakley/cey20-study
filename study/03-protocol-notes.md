# AUTH-003 S3: protocol notes (clarifications, not amendments)

The frozen protocol `03-study-protocol.md` is unchanged. These notes record who performs
which check, after GitHub Copilot's code-to-document review (AUTH-003-S1-METHOD-CHECK,
2026-10-31, finding AUTH003-01/02).

1. **Eligibility is a study check, not a builder property.** The production builder
   (`backend/scripts/build_global_cey20_landpoint_dataset.py`) checks month-hour counts and
   coordinate identity/order only. It does not check finite values or timestamps. The
   eligibility rules of the protocol (finite T and Td for every used hour; complete, strictly
   ordered, gap-free hourly timestamps starting at the UTC month start) are applied by the
   study tools before any outcome is computed, split as follows (Copilot recheck 2026-11-04,
   AUTH003-01):
   * `tools/s3_freeze.py` checks the timestamps and masked (missing) packed T/Td values; the
     result per point is recorded in `03-freeze.json` (`points[].eligible`, `points[].problems`,
     `input_inventory[].time_ok`). It does **not** test `np.isfinite`.
   * The finite-value rule is enforced by every S3 runner (`auth003_s3.py`, `auth003_s3_hourly.py`,
     `auth003_s3_d4s.py`): `auth003_study.valid_hour_coverage` counts hours with finite T **and**
     Td, and `auth003_s3.require_complete` aborts the run before outcomes are accepted or reported if
     the coverage of any point, year and month is below 1.0 (the per-month analysis runs before this
     check; it never reaches the outputs of a failed run). All completed runs passed this gate.
2. **UTC.** UTC anchoring of the inputs is established by that timestamp check, not by B.
3. The freeze script used is identified by its SHA-256 in the commit that adds
   `03-freeze.json`; the script is versioned under `tools/`.
4. **Protocol hash.** `03-freeze.json` records `protocol_sha256 = 3bb602894167da20e601d3d8cfd5b77337bd35d6a861ec5671726d5ade330c8d`, computed over the
   Windows working copy (CRLF line endings, git autocrlf). The committed protocol at `00efaf6` is
   the same text with LF line endings: SHA-256 `24c7d46586f898b3d701d67968c04b2216b154efea4cf9a26063c8d150321690`, git blob `1405f2f4cfece0762a6bce9195da8f849840c9d0`.
   Freeze script SHA-256 (as committed under `tools/`): `f5a7702f36cc3b14b31815bf8dbdeb7223dc120aa7058350032befcf6ef0a4eb`.
5. **Freeze result (2026-10-31T09:27:03Z, code `00efaf6`):** all 14 points eligible (no masked
   T/Td hour, no timestamp problem); 240 of 240 input files with complete, ordered, gap-free hourly
   timestamps from the UTC month start. Resolved grid points and distances are in `03-freeze.json`.
   No outcome was computed.
6. **Pre-outcome addenda (Copilot S3-runner review, 2026-10-31).** `03-freeze-input-sha256.json`
   holds the SHA-256 of all 240 inputs (computed 09:50-10:41 UTC by `tools/s3_input_hashes.py`),
   and `03-s3-code-pin.json` pins the study package and the S3 runner. The runner
   (`backend/scripts/research/auth003_s3.py`) aborts unless code, inputs, hashes and the 14
   protocol points all match. Both files were committed before any outcome was computed.
