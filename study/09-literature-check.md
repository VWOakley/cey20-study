# Check of a Gemini Deep Research summary on typical-year accuracy (2026-11-07)

The operator ran Gemini Deep Research on "how far do established typical-year methods miss our targets". Its claims
were checked against Crossref metadata and freely available abstracts; full texts behind paywalls were not read.
Rule: nothing from the summary is cited unless verified in the primary source.

| Source (as cited by Gemini) | Exists (DOI) | Metadata correct? | Claimed content | Verdict |
|---|---|---|---|---|
| Huld et al. 2018, Atmosphere 9, 53 | yes | yes | "45 BSRN/ECA&D stations; T bias SD 1.18 °C; RH errors 5–12 pp; > 60 % of sites fail" | **Contradicted/unsupported.** Abstract: validation against **487** stations in Europe, via degree days and EnergyPlus; relative SD < 6 % for heating. No RH or monthly-T figures in the abstract. |
| Hong et al. 2013, Appl. Energy 103 (DOI …2012.10.013) | DOI exists | **no** | "TMY3, 17 US cities, monthly ΔT up to 2.4 °C" | **Wrong citation.** The DOI is Hong, Koo, Kwak, "Framework for the implementation of a new renewable energy system in an educational facility". |
| Kalamees & Vinha 2004, J. Thermal Envelope Build. Sci. 27, 199–220 | yes | partly (year 2004) | "ISO 15927-4 TRY, Tartu, 31 yr; monthly ΔT/ΔRH and 8–18 % high-RH hour deviations" | **Mismatch.** Abstract: six Estonian stations 1970–2000; **10 %-level critical moisture reference years** for condensation and mould risk; no ISO TRY deviation figures. |
| Salonvaara et al. 2010 / ASHRAE RP-1325 | URL dead; project exists | authors partly wrong | "TMY2/TMY3 deviate 10–35 % in RH ≥ 80/90 % hours in 17 cities" | **Unsupported.** RP-1325 developed a severity index for moisture design years (8 US locations, 30 yr, 4 for validation); public summaries report ranking performance, not these deviations. |
| Cornick, Djebbar, Dalgliesh 2003, Build. Environ. 38, 1367–1379 | yes | yes | TOW statistics for 5 Canadian cities; reference years −10 to −25 % in cold/dry sites | **Unverified** (no abstract available); topic matches (moisture index reference years). |
| Pernigotto et al. 2014 (online 2013), J. Build. Perf. Sim. 7, 391–410 | yes | yes | "30–45 % / 30–50 % of station-months fail" | **Unverified;** Gemini marks related rates as estimates. |
| Levermore & Parkinson 2006, BSERT 27, 311–325 | yes | yes (title "…for the UK") | 14 UK sites, FS-based TRY; "15–25 % of months exceed ±0.5 °C" | Sites and method confirmed by abstract; **percentage unverified** (Gemini: "graphical distributions indicate"). |
| Pissimanis 1988, Petrakis 1998, Argiriou 1999, Chan 2006, Sawaqed 2005, Jiang 2010, Bhandari 2012, Zhou 2016 | yes | yes | single-site or few-site monthly deviations | **Unverified** (no abstracts via Crossref); several pass rates are Gemini's own estimates. |

## Consequences

- None of the quantitative pass/fail rates in the summary can be cited. Two key claims are contradicted (Huld 2018,
  Kalamees & Vinha) and one citation is wrong (Hong 2013).
- What can be said from verified sources: typical-year construction methods (FS-based TMY, ISO 15927-4 TRY,
  reanalysis-based TMY such as PVGIS) are routinely validated through degree days and energy simulations rather than
  through monthly-mean or humidity-hour tolerances (Huld et al. 2018); moisture reference years are a separate line
  of work (Kalamees & Vinha 2004; Cornick et al. 2003; RP-1325).
- Direct numbers for PVGIS-TMY and NSRDB TMY against our thresholds will come from the S4 part 2 comparison, not from
  the literature.
- If the paper needs literature figures for monthly deviations, the full texts of Pissimanis 1988, Chan 2006,
  Levermore & Parkinson 2006 and Cornick et al. 2003 must be read first.
