# settingsLibraries.js Prework Prompt

Use this prompt before moving code out of
`apps/desktop/webview/static/assets/settingsLibraries.js`.

## Prompt

You are working in this repository on the WebView Library
Profiles surface. Begin prework for a troubleshooting-oriented refactor of
`apps/desktop/webview/static/assets/settingsLibraries.js`.

This is a prework task only. Do not move functions, rename exports, add child
scripts, change backend routes, change Library Profile semantics, or alter UI
behavior unless the operator explicitly changes the task scope. The goal is to
document the current Library Profiles contract, Settings handoff points,
profile inheritance rules, and safe seams for future extraction.

## Read First

Read these before source edits or planning claims:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/CONFIG_KEY_GLOSSARY.md`
- `docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md`
- `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`
- `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/settingsLibraries.js.md`
- `docs/implementation/library-route-map/README.md`
- `apps/desktop/webview/static/assets/settingsView.js`
- `apps/desktop/webview/static/assets/settings/routePolicyModel.js`
- `apps/desktop/webview/static/partials/page-settings.html`

If the generated summary is sparse, build the real map from source, inventories,
and tests.

## Current File Facts

| Item | Current value |
|---|---|
| Source file | `apps/desktop/webview/static/assets/settingsLibraries.js` |
| Observed local line count | 2,528 |
| Public namespace | `window.mediaPipelineSettingsLibraries` |
| Current flat exports | 0 in `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` |
| Current script tag | `/assets/settingsLibraries.js` after `/assets/settingsView.js` |
| Main partial | `apps/desktop/webview/static/partials/page-settings.html` |
| Primary dependency | `window.mediaPipelineSettingsView` preview/save helpers |

## Non-Negotiable Boundaries

- Backend owns Library Profile validation, inheritance semantics, effective
  settings evidence, settings preview, settings save, and active config writes.
- WebView may render profiles, stage library patch intent, delegate preview/save
  to Settings, and show backend evidence.
- WebView must not write config, persist profile state directly, infer final
  runtime media policy, or bypass Settings preview/save confirmation.
- Missing override keys inherit global settings. Explicit override keys remain
  explicit even when equal to global values. Reset-to-global removes overrides.
- Custom missing/blank output paths inherit `Outsource`; promotion destinations
  remain explicit.
- `window.mediaPipelineSettingsLibraries` remains the public facade during
  refactor work.

## Prework Deliverables

Produce a concise baseline packet or planning note that contains:

1. Current `mediaPipelineSettingsLibraries` export ledger:
   export name, current signature, source line, known direct callers, proposed
   owner module, and wrapper requirement.
2. Settings handoff ledger:
   every call into `mediaPipelineSettingsView`, including busy rejection,
   preview patch, save patch, mark patch touched, and patch summary refresh.
3. Library profile state ledger:
   selected profile, staged profile edits, override groups, route rules,
   watch-folder controls, dirty state, reset requests, and post-save refresh
   state.
4. DOM ledger for Settings library IDs:
   `settings-library-*` controls, profile list/editor, override controls,
   route/promotion/watch panels, and any route-map handoff IDs.
5. Direct caller search results for `mediaPipelineSettingsLibraries` across
   browser smokes, static tests, Settings code, Launch/Home/route-map helpers,
   and documentation inventories.
6. Source-only guardrail list for tests that read `settingsLibraries.js`
   directly.
7. Target troubleshooting seams and a rollback rule for each seam.
8. Validation commands required before any extraction.

## Suggested Troubleshooting Seams

| Seam | Candidate owner | Prework question |
|---|---|---|
| Profile state | `assets/settings/libraries.state.js` | Which code owns selected profile and local staged edits? |
| Override groups | `assets/settings/libraries.overrides.js` | Which helpers compute explicit/inherited/reset override display? |
| Patch builder | `assets/settings/libraries.patch.js` | Which code builds Settings patch payloads but does not save them? |
| Preview/save bridge | `assets/settings/libraries.commands.js` | Which code delegates to `mediaPipelineSettingsView` preview/save? |
| Route/promotion evidence | `assets/settings/libraries.routes.js` | Which renderers explain source/output/final promotion decisions? |
| Watch-folder panel | `assets/settings/libraries.watch.js` | Which code stages watch-folder settings without starting scans? |
| Profile list/editor view | `assets/settings/libraries.view.js` | Which functions render list, detail, status, empty states, and editor controls? |
| Reset/default logic | `assets/settings/libraries.reset.js` | Which helpers stage reset-to-global while preserving backend inheritance semantics? |

Do not create every candidate file mechanically. A seam is valid only if it has
a stable contract, caller ledger, test target, and rollback path.

## Baseline Commands

Run or record why you cannot run:

```powershell
git status --short
rg -n "mediaPipelineSettingsLibraries|settingsLibraries.js|settings-library-|LibraryProfiles|previewSettingsPatch|saveSettingsPatch" apps tests docs/inventories docs/implementation/library-route-map
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_settings_libraries -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_library_profiles_save_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_settings_launch_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_final_library_promotion -q
npm run webview:prework:check
```

Browser-backed smokes may be skipped only with a concrete environment reason.

## Stop Conditions

Stop prework and report the blocker if:

- A proposed child module would own config persistence, backend profile
  validation, final promotion policy, runtime media policy, or path trust.
- A save path would bypass `mediaPipelineSettingsView.saveSettingsPatch`.
- A child module needs to load after `settingsLibraries.js`.
- More than one module would own selected profile, staged profile edits,
  override state, route/promotion state, watch-folder dirty state, or reset
  requests.
- A proposed split would break script order: `settingsView.js` and
  `settings/routePolicyModel.js` must still load before `settingsLibraries.js`,
  and downstream Settings wizard/route-map scripts must still load after it.
- Any baseline or prework note claims a source/static guardrail was migrated,
  but live source still reads only the parent file or otherwise keeps the old
  assumption.

## Final Prework Report

End with:

- change packet ID
- current file size and public contract counts
- ledgers produced
- proposed first extraction phase
- validation commands and results
- uncovered unrelated dirty files
- explicit statement that no runtime behavior changed
