# Amendment A1 to 08-external-comparison-spec.md (r3, frozen 3b8ddca3)

Date: 2026-11-07, before any candidate metric was computed and before any usable ISD hourly file existed.

1. **ISD endpoint.** The NCEI Global Hourly access path in section 10
   (`https://www.ncei.noaa.gov/data/global-hourly/access/<year>/<id>.csv`) now answers with HTTP 301 to an S3 file
   browser page. The first stage-A run therefore stored 1,360 identical 36,822-byte HTML pages instead of data
   (inventory `raw/inventory_isd.json`, folder `raw/isd/<year>/`; `isd-history.csv` there is valid). The same Global
   Hourly product is downloaded from the NOAA Open Data bucket `https://noaa-global-hourly-pds.s3.amazonaws.com/
   <year>/<id>.csv` into `raw/isd_s3/`, inventory `raw/inventory_isd_s3.json`.
2. **Content check.** Every downloaded file must start with the expected header (`"STATION"` for hourly files,
   `"USAF"` for `isd-history.csv`); otherwise it is recorded as `invalid_content` and not written.
3. The invalid HTML files stay in place until the operator approves their deletion (drive rule 2); they are never
   read by the analysis.

No other part of the specification changes.
