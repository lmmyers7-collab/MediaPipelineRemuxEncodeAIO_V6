# settingsView.js Prework Prompt

Use this prompt before moving more code out of
`apps/desktop/webview/static/assets/settingsView.js`.

## Prompt

You are working in this repository on the WebView Settings
surface. Begin prework for a troubleshooting-oriented refactor of
`apps/desktop/webview/static/assets/settingsView.js`.

This is a prework task only. Do not move functions, rename exports, add child
scripts, change backend routes, change config semantics, or alter UI behavior
unless the operator explicitly changes the task scope. The goal is to document
the parent facade's current responsibilities, existing builder-child boundaries,
strict save/preview contracts, and the safest seams for future extraction.

## Read First

Read these before source edits or planning claims:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/CONFIG_KEY_GLOSSARY.md`
- `docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`
- `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`
- `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/settingsView.js.md`
- `apps/desktop/webview/static/assets/settingsView.builders.*.js`
- `apps/desktop/webview/static/assets/settingsView.rawTriage.js`
- `apps/desktop/webview/static/assets/settingsView.safetyLocks.js`
- `apps/desktop/webview/static/assets/settings/patchReview.js`
- `apps/desktop/webview/static/partials/page-settings.html`

If the generated summary is sparse, build the real map from source, inventories,
and tests.

## Current File Facts

| Item | Current value |
|---|---|
| Source file | `apps/desktop/webview/static/assets/settingsView.js` |
| Observed local line count | 2,853 |
| Public namespace | `window.mediaPipelineSettingsView` |
| Current flat exports | 4 in `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` |
| Current script tag | `/assets/settingsView.js` |
| Main partial | `apps/desktop/webview/static/partials/page-settings.html` |
| Existing split children | builder modules, raw triage, safety locks, patch review, policy impact, backend result modules |

## Non-Negotiable Boundaries

- Backend owns settings validation, preview, save, reload, schema migration,
  JSON authority writes, PSD1 projection, backups, and runtime policy.
- WebView may stage local patches, render backend preview/save evidence, and
  call documented backend routes.
- WebView must not write config files, infer final runtime media policy, or
  bypass backend preview/save review confirmation.
- `/api/settings/save-patch` must keep `confirm_save: true` and matching
  backend `review_confirmation`.
- Preset apply and wizard save flows must keep their own strict confirmations.
- Network worker settings handoff remains delegated; Network setup/lifecycle
  policy stays in Network backend routes.
- `window.mediaPipelineSettingsView` remains the public facade during refactor
  work.

## Prework Deliverables

Produce a concise baseline packet or planning note that contains:

1. Current `mediaPipelineSettingsView` namespace export ledger and flat export
   ledger:
   export name, current signature, source line, known direct callers, proposed
   owner module, wrapper requirement, and compatibility-export status.
2. Existing child module ledger:
   child file, stash global, factory function, injected dependencies, exports
   consumed by parent, and tests that assume the child exists.
3. Settings route ledger:
   `/api/settings/validate`, `/api/settings/preview-patch`,
   `/api/settings/save-patch`, `/api/settings/browse-path`,
   `/api/settings/reload`, wizard routes, preset-library routes, and any
   delegated rename/network calls.
4. DOM ledger for `settings-*` IDs:
   general settings, patch summary, effective policy, builders, raw-key plan,
   rename workbench, libraries handoff, and save-review dialog.
5. Direct caller search results for `mediaPipelineSettingsView`, flat exports,
   and settings child stash globals across `apps/desktop/webview/static/assets/`
   and `tests/`.
6. Current mutable state list:
   last settings, staged patch, pending patch review, busy state, preview result,
   save result, selected policy/effective rows, raw triage selection, builder
   dirty flags, pending browse target, and post-save refresh handoff.
7. Target troubleshooting seams and a rollback rule for each seam.
8. Validation commands required before any extraction.

## Suggested Troubleshooting Seams

| Seam | Candidate owner | Prework question |
|---|---|---|
| Parent facade cleanup | `settingsView.js` | Which wrappers only delegate to existing builder children? |
| Patch staging | `assets/settings/patchState.js` | Which helpers own local unsaved changes and dirty flags only? |
| Preview/save commands | `assets/settings/patchCommands.js` | Which flows call backend preview/save with strict confirmations? |
| Browse path commands | `assets/settings/pathBrowse.js` | Which code calls backend browse without owning path trust? |
| Effective policy trust | `assets/settings/effectivePolicy.js` | Which renderers explain saved-vs-staged policy evidence? |
| Backend result rendering | existing backend-result module | Which parent logic still formats backend preview/save/reload errors? |
| Rename workbench bridge | `assets/settings/renameWorkbenchBridge.js` | Which code delegates rename cleaner tests and case append routes? |
| Network builder bridge | existing network builder | Which code stages Network settings but never starts lifecycle? |
| Preset and wizard handoffs | existing Settings modules | Which flows need route/confirmation ledgers before moving? |

Do not create every candidate file mechanically. A seam is valid only if it has
a stable contract, caller ledger, test target, and rollback path.

## Baseline Commands

Run or record why you cannot run:

```powershell
git status --short
rg -n "mediaPipelineSettingsView|settingsView.js|/api/settings|confirm_save|review_confirmation|__settings" apps tests docs/inventories
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_settings_patch_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_settings_live_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_handbrake_settings_ui -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_web_static_settings -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_facade_settings_patch_policy -q
npm run webview:prework:check
```

Browser-backed smokes may be skipped only with a concrete environment reason.

## Stop Conditions

Stop prework and report the blocker if:

- A proposed child module would own config persistence, PSD1 projection,
  backend validation, runtime media policy, or path trust.
- Any save path would lose `confirm_save` or backend review-confirmation
  matching.
- A child module needs to load after `settingsView.js`.
- More than one module would own staged patch, busy state, preview/save result,
  builder dirty state, raw triage selection, or post-save refresh state.
- A source-only guardrail would fail after extraction and has no migration plan.
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
