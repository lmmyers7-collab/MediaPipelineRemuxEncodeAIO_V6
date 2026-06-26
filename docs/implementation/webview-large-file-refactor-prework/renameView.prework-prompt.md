# renameView.js Prework Prompt

Use this prompt before moving code out of
`apps/desktop/webview/static/assets/renameView.js`.

## Prompt

You are working in this repository on the WebView Rename
surface. Begin prework for a troubleshooting-oriented refactor of
`apps/desktop/webview/static/assets/renameView.js`.

This is a prework task only. Do not move functions, rename exports, change
backend routes, change rename policy, or alter UI behavior unless the operator
explicitly changes the task scope. The goal is to make a later refactor safer
by documenting the current public contract, mutation boundaries, source-only
test assumptions, and clean failure seams.

## Read First

Read these before source edits or planning claims:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/inventories/RENAME_SAFETY_TEST_INVENTORY.md`
- `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`
- `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/renameView.js.md`
- `apps/desktop/webview/static/assets/renameLabels.js`
- `apps/desktop/webview/static/assets/renameHistoryView.js`
- `apps/desktop/webview/static/partials/page-rename.html`

If the generated summary is sparse, build the real map from source, inventories,
and tests.

## Current File Facts

| Item | Current value |
|---|---|
| Source file | `apps/desktop/webview/static/assets/renameView.js` |
| Observed local line count | 3,482 |
| Public namespace | `window.mediaPipelineRenameView` |
| Current flat exports | 0 in `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` |
| Current script tag | `/assets/renameView.js` |
| Main partial | `apps/desktop/webview/static/partials/page-rename.html` |
| Adjacent dependencies | `renameLabels.js`, `renameHistoryView.js`, Queue and Settings namespaces |

## Non-Negotiable Boundaries

- Rename preview/apply/undo policy stays backend-owned.
- WebView may stage paths, render preview evidence, and call backend routes.
- WebView must not rename, delete, move, rewrite sidecars, infer path safety, or
  bypass backend root/collision checks.
- `/api/rename/apply` must keep `confirm_apply: true`.
- `/api/rename/undo` must keep `confirm_undo: true`.
- `/api/rename/filter-cases` must keep `confirm_append: true`.
- Backend browse remains a shell-dialog route; the WebView must not implement
  local filesystem browsing or path trust.
- `window.mediaPipelineRenameView` remains the public facade during refactor
  work.

## Prework Deliverables

Produce a concise baseline packet or planning note that contains:

1. Current `mediaPipelineRenameView` export ledger:
   export name, current signature, source line, known direct callers, proposed
   owner module, and wrapper requirement.
2. Rename route ledger:
   `/api/rename/preview`, `/api/rename/browse`,
   `/api/rename/filter-cases`, `/api/rename/apply`, `/api/rename/undo`, and
   the cleaner/workbench helper routes used by this file.
3. DOM ledger for `rename-*` IDs from the partial and DOM inventory:
   region, renderer/helper owner, and smoke/static test coverage.
4. Direct caller search results for `mediaPipelineRenameView` across
   `app.js`, `settingsView.js`, browser smokes, static tests, and rename
   service tests.
5. Source-only guardrail list for tests that read `renameView.js` directly.
6. Current mutable state list:
   selected row, checked rows, path origins, final overrides, force overrides,
   preview payload/signature, command activity, undo manifest, dialog state,
   workbench state, and filter editor state.
7. Target troubleshooting seams and a rollback rule for each seam.
8. Validation commands required before any extraction.

## Suggested Troubleshooting Seams

| Seam | Candidate owner | Prework question |
|---|---|---|
| Cleaning filter editor | `assets/rename/cleaningFilters.js` | Which code stages filter patches but does not save settings directly? |
| Workbench | `assets/rename/workbench.js` | Which code builds backend test queries and suggestion rows? |
| Path intake | `assets/rename/pathInput.js` | Which code handles typed paths, browse results, queue handoffs, and drag/drop? |
| Preview model | `assets/rename/preview.model.js` | Which helpers classify rows, duplicates, statuses, warnings, and caps? |
| Preview view | `assets/rename/preview.view.js` | Which functions render preview rows, selected inputs, and source summaries? |
| Bulk edit | `assets/rename/bulkEdit.js` | Which functions stage local final-name overrides only? |
| Bad-case logging | `assets/rename/badCase.js` | Which functions build fixture append payloads with `confirm_append`? |
| Apply readiness | `assets/rename/applyReadiness.js` | Which code explains why apply is blocked or allowed? |
| Apply/undo commands | `assets/rename/commands.js` | Which flows call backend apply/undo with strict confirmations? |
| Dialogs | `assets/rename/dialogs.js` | Which code renders confirm/result/undo dialogs without owning mutation? |

Do not create every candidate file mechanically. A seam is valid only if it has
a stable contract, caller ledger, test target, and rollback path.

## Baseline Commands

Run or record why you cannot run:

```powershell
git status --short
rg -n "mediaPipelineRenameView|renameView.js|/api/rename|confirm_apply|confirm_undo|confirm_append" apps tests docs/inventories
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_rename_readiness_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_rename_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_web_static_rename -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_rename_workbench -q
npm run webview:prework:check
```

Browser-backed smoke may be skipped only with a concrete environment reason.

## Stop Conditions

Stop prework and report the blocker if:

- A proposed child module would own rename apply, undo, path-boundary, collision,
  or sidecar policy instead of calling backend routes.
- Any strict confirmation field would be weakened or moved out of the command
  flow ledger.
- A child module needs to load after `renameView.js`.
- More than one module would own preview payload, checked-row state, overrides,
  selected row, undo manifest, or dialog state.
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
