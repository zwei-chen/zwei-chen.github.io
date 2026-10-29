# Dive Vision four-page implementation plan

**Goal:** Separate visualization, planning, gas blending and SCR; give each Chinese/English routes and system/light/dark appearance.
**Architecture:** Shared Jekyll layout/includes, locale-aware JavaScript UI and existing Pyodide worker. Python owns numerical calculation. Keep existing manual-plan draft and no backend.
**Confirmed:** SCR = surface consumption in L/min at 1 bar. Partial-pressure blending with configurable pure O2 / He / air supplies.

- [x] Extend Python API: visualization only executes entered segments, current-depth GF99/per-compartment values, retain planning behavior; blend solves nonnegative component balances with absolute pressure; SCR exposes arithmetic details. Add regressions first.
- [x] Shared shell: four independent routes per language, persistent theme (default system), per-page draft persistence across languages. Reuse existing layout and runtime.
- [x] Separate planner/visualization UI; explicit segment direction, linked timeline/GF99/tissue visualization and playback. Independent blending and SCR forms/results.
- [x] Translate all visible copy, validation messages, dynamic results, charts and accessible labels; theme charts as well as controls.
- [x] Test physics invariants, infeasible mixtures, unchanged planner cases, route/build/localization checks and actual browser interactions at iPad size. Review before completion. Do not retry previously declined download test.

## Review focus
- GF99 is current ambient pressure, SurfGF is surface pressure; no 100% clipping.
- Visualization may cross ceiling but reports it; planner still refuses unsafe entered ascent.
- Blend uses gauge pressure + surface absolute pressure, preserves components and rejects negative additions.
- Language switch preserves each tool's draft; error and busy results cannot become stale.
- System follows live OS theme changes; explicit theme persists and SVG follows theme.


## Completion evidence
- 28 Python tests pass, including 80 generated blending conservation cases.
- Jekyll build succeeds; all 8 bilingual routes/assets/navigation/disclaimers pass; existing bilingual homepage tests pass.
- Browser: visualization/GF99, preserved locale drafts, dark/light/system, English text, feasible/infeasible mixing and SCR verified. SCR iPad 768 px layout fits without horizontal overflow.
- Original planner sample remains 30 m, 36.3 min runtime, 7 min deco, 11.3 min TTS.
- Independent review found lost altitude and English PPO2 legend; reproduced/fixed altitude and verified locale persistence, fixed legend and verified 'Deco limit' in browser.
- Added requested testing badge and bilingual disclaimer across all four tools.
- Download verification remains excluded in accordance with the prior user refusal. No publication or commit performed.


## User-directed settings revision
- [x] Restore complete settings in both profile tools; core settings are GF High/Low, water and SCR, plus global ascent/descent speeds for the planner.
- [x] Move visualization speed to each movement segment; preserve existing drafts through Python duration-to-speed conversion. Holds keep duration inputs.
- [x] Remove switch-dwell and safety-stop controls in both pages; ignore stale browser draft values and use zero defaults.
- [x] Keep environment/automatic-planning parameters in advanced settings with applicability explained, and expose custom density and gas derived data.
- [x] Preserve GF Low instead of overwriting it; render separate fixed GF Low/High reference ceilings without modifying the entered profile.
- [x] Verify numerical regressions and built parameter grouping; browser checked draft conversion and independent speed-to-time updates.
