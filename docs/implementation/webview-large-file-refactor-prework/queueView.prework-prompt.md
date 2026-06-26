# queueView.js Prework Prompt

Use this prompt before moving more code out of
`apps/desktop/webview/static/assets/queueView.js`.

## Prompt

You are working in this repository on the WebView Queue
surface. Begin prework for a troubleshooting-oriented refactor of
`apps/desktop/webview/static/assets/queueView.js`.

This is a prework task only. Do not move functions, rename exports, add child
scripts, change backend routes, change queue policy, or alter UI behavior unless
the operator explicitly changes the task scope. The goal is to make future
Queue troubleshooting easier by recording what the parent facade still owns,
what the existing child modules already own, and which seams remain safe to
split later.

## Read First

Read these before source edits or planning claims:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`
- `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/queueView.js.md`
- `apps/desktop/webview/static/assets/queueView.summary.js`
- `apps/desktop/webview/static/assets/queueView.review.js`
- `apps/desktop/webview/static/assets/queueView.detail.js`
- `apps/desktop/webview/static/assets/queueView.launch.js`
- `apps/desktop/webview/static/assets/queue/table.js`
- `apps/desktop/webview/static/assets/queue/fileOverrides.drawer.js`
- `apps/desktop/webview/static/partials/page-queue.html`

If the generated summary is sparse, build the real map from source, inventories,
and tests.

## Current File Facts

| Item | Current value |
|---|---|
| Source file | `apps/desktop/webview/static/assets/queueView.js` |
| Observed local line count | 2,913 |
| Public namespace | `window.mediaPipelineQueueView` |
| Current flat exports | 79 in `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` |
| Current script tag | `/assets/queueView.js` |
| Main partial | `apps/desktop/webview/static/partials/page-queue.html` |
| Existing split children | summary, review, detail, launch, table, file-overrides drawer modules |

## Non-Negotiable Boundaries

- Backend owns queue scan, source discovery, source-root policy, priority
  manifest writes, strategy writes, file override persistence, launch scope, and
  source media safety.
- WebView may render loaded rows, stage operator intent, and call documented
  backend routes.
- Filtering and selection remain visual/local and must never imply backend
  launch scope.
- Hidden active/problem/review row warnings must be preserved.
- `/api/queue/priority`, `/api/queue/strategy`, `/api/queue/scan`,
  `/api/queue/open`, and `/api/queue/file-overrides` ownership must stay
  documented in command inventories and tests.
- `window.mediaPipelineQueueView` remains the public facade during refactor
  work.
- Existing child factory stash globals must continue to be consumed and deleted
  by the parent.

## Prework Deliverables

Produce a concise baseline packet or planning note that contains:

1. Current `mediaPipelineQueueView` namespace export ledger and flat export
   ledger:
   export name, current signature, source line, known direct callers, proposed
   owner module, wrapper requirement, and compatibility-export status.
2. Existing child module ledger:
   child file, stash global, factory function, injected dependencies, exported
   helpers consumed by parent, and source tests that assume the child exists.
3. Queue route ledger:
   `/api/queue/scan`, `/api/queue/priority`, `/api/queue/strategy`,
   `/api/queue/open`, `/api/queue/file-overrides`, method/effect, caller, and
   backend authority note.
4. DOM ledger for `queue-*` IDs:
   table/filter/selection/detail/readiness/launch-scope/file-override region,
   renderer owner, and smoke/static coverage.
5. Direct caller search results for `mediaPipelineQueueView` and remaining flat
   exports across `apps/desktop/webview/static/assets/` and `tests/`.
6. Current mutable state list:
   selected row, selected priority rows, last queue payload, last queue rows,
   filters, investigation filter, open history, scan state, strategy state, file
   override drawer state, and launch/readiness payloads.
7. Target troubleshooting seams and a rollback rule for each seam.
8. Validation commands required before any extraction.

## Suggested Troubleshooting Seams

| Seam | Candidate owner | Prework question |
|---|---|---|
| Parent facade cleanup | `queueView.js` | Which wrappers only delegate to existing children? |
| Selection and filters | `assets/queue/selection.js` | Which code owns selected row, multi-select priority rows, and filter warnings? |
| Open actions/history | `assets/queue/openActions.js` | Which code calls `/api/queue/open` or renders open history? |
| Scan and curation | `assets/queue/scan.commands.js` | Which code starts/observes source scan without owning discovery policy? |
| Priority commands | `assets/queue/priority.commands.js` | Which code builds priority payloads and result lines? |
| Strategy commands | `assets/queue/strategy.commands.js` | Which code stages backend queue strategy changes? |
| File override bridge | existing `assets/queue/fileOverrides.*` | Which parent functions still bridge to drawer modules? |
| Compatibility exports | parent facade ledger | Which flat exports are still directly called by tests or pages? |

Do not create every candidate file mechanically. A seam is valid only if it has
a stable contract, caller ledger, test target, and rollback path.

## Baseline Commands

Run or record why you cannot run:

```powershell
git status --short
rg -n "mediaPipelineQueueView|queueView.js|/api/queue|QUEUE_PRIORITY_ROUTE|QUEUE_STRATEGY_ROUTE|QUEUE_FILE_OVERRIDES_ROUTE" apps tests docs/inventories ops/scripts/dev
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_row_detail_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_large_table_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_queue_file_overrides_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_web_static_queue -q
npm run webview:prework:check
```

Browser-backed smokes may be skipped only with a concrete environment reason.

## Stop Conditions

Stop prework and report the blocker if:

- A proposed child module would own source discovery, source-root trust,
  priority/strategy persistence policy, file override persistence policy, or
  launch scope.
- A split would remove or rename a flat export without a caller ledger and
  inventory update plan.
- A child module needs to load after `queueView.js`.
- More than one module would own selected row, selected priority rows, filters,
  last payload, last rows, open history, or drawer state.
- A filter/selection change would make visible rows look like backend launch
  scope.
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
