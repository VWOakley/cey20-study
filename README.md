# CEY20 study package: design and evaluation of a moisture-weighted typical-month selection

This repository is the study package for the preprint

> Okley, W. (2026): *A moisture-weighted typical-month selection for environmental exposure screening: design and
> evaluation of CEY20 at 14 locations.* Technical Research / Preprint – Not Peer Reviewed. EarthArXiv. [DOI pending]

It contains the analysis code, the product code for month selection and month-interface smoothing, the protocol,
specifications, freeze records, pins, amendments and all result tables of the evaluation.

> **Status: in preparation, not yet released.** The evaluation of the released product version 2 (amendment V2) was
> run on 2026-11-09; its code, results and figures are included (`study/12-results-v2/`). Independent review of the
> results and manuscript is pending.

## What CEY20 is

CEY20 (Climetry Environmental Year, 2006–2025) is a typical-month selection for moisture and thermal exposure
screening on the global 0.25° ERA5-Land land grid.

- **Selection.** For each land point and calendar month, it selects the source year whose ten monthly temperature
  and humidity features are closest to their 20-year means, using a weighted, scaled L1 distance.
- **Smoothing.** Product version 2 smooths the month interfaces with a 6-hour excess-step ramp.
- **Scope.** It contains no radiation or wind and is not an energy or solar typical meteorological year.

## Layout

| Path | Content |
|---|---|
| `code/backend/scripts/build_global_cey20_landpoint_dataset.py` | Month selection: features, weights, scales, score (product builder at commit `00efaf6`, the version evaluated) |
| `code/backend/scripts/smooth_cey20_month_interfaces.py` | Month-interface smoothing of product version 2 (commit `388cfdb4`, the generating commit of the released v2 files) |
| `code/backend/scripts/research/` | Study scripts: S3 targets, hourly diagnostics D1–D5, D4s, FS comparison, screening applications, California comparison, paired v1/v2 evaluation (`auth003_v2_eval.py`) |
| `code/backend/tests/` | Unit tests of the study scripts |
| `code/SOURCES.json` | Source commit, path and SHA-256 of every code file |
| `study/` | Protocol, specifications, freeze records, pins, amendments, method description and all result tables |
| `verify_package.py` | Checks that the packaged code equals the code pinned before each run |

The code files are byte-identical (LF line endings) to the commits that were pinned before each run, so that the
pins in `study/*pin*.json` can be checked. They therefore contain the original default paths of the author's
machine. All paths can be overridden on the command line.

## Reproduce

```sh
python -m pip install numpy netCDF4 pytest
python verify_package.py                 # packaged code == pinned code
cd code/backend && python -m pytest -q tests
```

- **Tests.** Two CLI tests need the product's city builder for point resolution and are skipped here. Point
  resolution was done once and is frozen in `study/03-freeze.json`.
- **Rerunning the analyses.** This needs the ERA5-Land hourly inputs for the 14 points, 2006–2025 (T, Td, surface
  pressure). [Pending: point extract with checksums under `data/`.] Each runner documents its command line in its
  module docstring and in the corresponding `study/` README.

## Study record

- **Protocol and targets:** `study/03-study-protocol.md`. It was frozen and hashed (`study/03-freeze.json`) before
  any target outcome was computed.
- **Results:** in `study/0x-results*/`. Each result folder has a README with run history, gates and limitations.
- **Amendments:**
  - `study/08-amendment-A*.md`: California comparison;
  - `study/12-amendment-V2.md`: evaluation of the released version 2. This amendment is outcome-informed and
    discloses the evidence available when it was fixed. `study/12-amendment-V2.1-clarification.md` records three
    implementation clarifications approved before any version-2 outcome.
- **Version-2 results:** `study/12-results-v2/README.md` (gates, paired v1/v2 tables). The 31.5 MB duration-curve
  file `a1_curves.csv` is not included; its SHA-256 is recorded there.
- **Figures:** `study/06-figures/` with the scripts that produce them from the result tables.
- **Negative results** are reported unchanged. The tolerances were not changed after outcomes were known.
- **Reviews.** Specifications and results were reviewed for method and code. The review records named in the result
  READMEs, and the Codex reviews of amendment V2, are included.

## Licences

- Code: MIT (`LICENSE`).
- Documents, result tables and figures: CC BY 4.0 (`LICENSE-DATA`).
- ERA5-Land: contains modified Copernicus Climate Change Service information (2026). Neither the European Commission
  nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains.

## Related records

- Data descriptor: Okley (2026), https://doi.org/10.5281/zenodo.24073751
- California dataset: https://doi.org/10.5281/zenodo.24016356
- California tools: https://github.com/VWOakley/cey20-california, https://doi.org/10.5281/zenodo.24073640

## Use of AI tools

AI coding and writing assistants (Anthropic Claude, OpenAI Codex, GitHub Copilot) were used under the author's
direction for software development, scripted analysis runs, internal code and method consistency checks, and
drafting. All analyses were executed as deterministic scripts with pinned code and hashed inputs. The author reviewed
and edited the content as needed and takes full responsibility for it.

## Author

Wadim Okley, Independent researcher, ORCID [0009-0000-2257-9728](https://orcid.org/0009-0000-2257-9728).
