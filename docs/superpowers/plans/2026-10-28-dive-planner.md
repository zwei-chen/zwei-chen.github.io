# Dive Vision implementation plan

**Goal:** Replace the multiplication demo with a light-colour, iPad-friendly single-dive planner inspired by https://yuanzhendong.cn/.
**Architecture:** Static Jekyll page; Python calculation in the existing Pyodide module worker; JavaScript only edits inputs and draws returned results. No remote calculation endpoint. Preserve the title, hidden favicon and absence of homepage navigation.
**Scope:** ZHL-16C nitrogen and helium compartments with GF; editable environment/rates/oxygen/RMV; gas mixtures, cylinders and automatic deco switches; multi-level segments; automatic ascent and 3 m decompression; profile, cylinder and tissue charts; stop table, oxygen/gas advisories, export and a Python SAC calculator.

## Decisions
- White/slate surfaces with cyan/blue accents. Independent planner layout avoids the narrow personal-homepage article styling.
- Defaults: reference-site GF 50/70, surface pressure 1.01325 bar, density 1.03 kg/L, 18 m/min descent and 9 m/min ascent; these are editable demonstration inputs.
- A segment is a linear move from the previous depth to its target over its stated duration; equal depths create a hold. Initial tissues are equilibrated with surface air. No repetitive dive / residual loading / CCR support.
- Published ZHL-16C coefficients and Schreiner/GF equations; independent implementation with DecoTengu 0.14.0 as a temporary comparison dependency, not production code.
- Stop spacing 3 m, last stop selectable 3/6 m, waits in 1 min increments, evaluate transit ceiling at 1 s intervals. Document first-stop GF anchor and switch time handling.
- Clearly identify educational simulation and model assumptions. Show oxygen/cylinder/decompression issues next to results. Do not claim certification or guaranteed safe profiles.

## Tasks
- [x] Implement `Diving/vision/planner.py`: validated JSON API, tissue model, schedule, gases, exposure integration, SAC; verify independent numeric fixtures and invalid/extreme inputs.
- [x] Replace `index.html`, `vision.css`, `vision.js`, `worker.mjs`; add `charts.js` and a dedicated `_layouts/diving.html`. Implement editable tables, stale-result clearing, worker errors/retry/cancel, charts with time cursor, exports and SAC.
- [x] Run Python fixtures and end-to-end comparison against DecoTengu, Jekyll/bilingual checks, browser checks at desktop and iPad sizes where browser tooling is available. Inspect input bounds, disabled/deleted gases, GF ordering and stale output.
- [x] Update README and model-method documentation with sources, limitations and test commands. Keep local preview running; no publication or commit requested.

## Validation limits
CSV download end-to-end QA was skipped after the user declined browser download permission. No deployment or Git commit was performed. Browser calculation, GF error handling, gas disabling, chart/time controls and iPad-width rendering were verified.
