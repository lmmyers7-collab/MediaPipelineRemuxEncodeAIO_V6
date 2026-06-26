# networkView.js Prework Prompt

Use this prompt before moving more code out of
`apps/desktop/webview/static/assets/networkView.js`.

## Prompt

You are working in this repository on the WebView Network
page. Begin prework for a troubleshooting-oriented refactor of
`apps/desktop/webview/static/assets/networkView.js`.

This is a prework task only. Do not move functions, rename exports, add routes,
change backend behavior, change script order, or alter UI behavior unless the
operator explicitly changes the task scope. The output should make a later
refactor safer by freezing the current contract and identifying the cleanest
troubleshooting seams.

## Read First

Read these before source edits or planning claims:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/implementation/network-view-troubleshooting-refactor/README.md`
- `docs/implementation/network-view-troubleshooting-refactor/PHASE_0_BASELINE.md`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`
- `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/networkView.js.md`

If any generated summary says `Purpose: (unparsed)`, treat it as a navigation
hint only and build the real ledger from source, inventories, and tests.

## Current File Facts

| Item | Current value |
|---|---|
| Source file | `apps/desktop/webview/static/assets/networkView.js` |
| Observed local line count | 4,087 |
| Public namespace | `window.mediaPipelineNetworkView` |
| Current flat exports | 0 in `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` |
| Current script tag | `/assets/networkView.js` |
| Main partial | `apps/desktop/webview/static/partials/page-network.html` |
| Existing planning pack | `docs/implementation/network-view-troubleshooting-refactor/` |

## Non-Negotiable Boundaries

- Network lifecycle/setup authority stays in backend Local API routes.
- WebView may render route evidence, stage intent, and call backend routes only.
- WebView must not own coordinator/worker process lifecycle, claim/release/done
  policy, queue mutation, settings persistence, path trust, media policy, or
  filesystem mutation.
- Network route paths used by command flows must remain contract-derived, not
  hard-coded in new child modules.
- Confirmed lifecycle commands must keep fresh dry-run matching and strict
  `confirm_start` or `confirm_stop` payloads.
- Setup commands must keep `confirm_create`, optional `confirm_rotate`, and
  `confirm_import` exactly where backend contracts require them.
- `window.mediaPipelineNetworkView` remains the public facade during refactor
  work.

## Prework Deliverables

Produce a concise baseline packet or planning note that contains:

1. Current `mediaPipelineNetworkView` export ledger:
   export name, current signature, source line, known direct callers, proposed
   owner module, and whether a parent wrapper must remain.
2. Route ledger for all `/api/network/*` and related diagnostics/settings
   handoffs:
   route, method, effect, frontend caller, required confirmation fields, and
   backend authority note.
3. DOM ledger for `network-*` IDs from the page partial and inventory:
   region, renderer/helper owner, and smoke/static test coverage.
4. Direct caller search results for `mediaPipelineNetworkView` across
   `apps/desktop/webview/static/assets/` and `tests/`.
5. Source-only guardrail list for tests or scripts that currently assume all
   protected Network behavior is in `networkView.js`.
6. Served-static guardrail verification for
   `tests/python/desktop/application_facade_test_support.py`: prove whether
   `network_view_js` is still parent-only or has been migrated to the ordered
   parent-plus-child Network asset set. Do not trust existing planning docs for
   this; inspect the live source.
7. Target troubleshooting seams, not line-count chunks.
8. A rollback rule for each proposed seam.
9. Validation commands that must pass before and after the first extraction.

## Suggested Troubleshooting Seams

| Seam | Candidate owner | Prework question |
|---|---|---|
| Contract route lookup | `assets/network/contract.js` | Which functions only interpret `/api/contract` metadata? |
| Runtime status/readiness | `assets/network/status.js` and `assets/network/readiness.js` | Which renderers explain why Network is blocked or noisy? |
| Lifecycle model/view | `assets/network/lifecycle.model.js` and `.view.js` | Which helpers are pure evidence versus DOM rendering? |
| Lifecycle commands | `assets/network/lifecycle.commands.js` | Which flows build dry-run and confirmed POST payloads? |
| Setup commands | `assets/network/setup.commands.js` | Which flows test connection, discover coordinators, create join blobs, and import joins? |
| Worker board | `assets/network/workers.model.js` and `.view.js` | Which helpers classify persisted worker rows and render them? |
| State files | `assets/network/stateFiles.js` | Which helpers only explain backend-authored state artifacts? |
| Settings handoff | `assets/network/settingsHandoff.js` | Which code delegates to `mediaPipelineSettingsView` without direct persistence? |

Do not create every candidate file mechanically. A seam is valid only if it has
a stable contract, caller ledger, test target, and rollback path.

## Baseline Commands

Run or record why you cannot run:

```powershell
git status --short
rg -n "mediaPipelineNetworkView|networkView.js|/api/network|confirm_start|confirm_stop|confirm_create|confirm_rotate|confirm_import" apps tests docs/inventories ops/scripts/dev
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_network_read_only_boundary -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_network_smoke -q
npm run webview:prework:check
```

Browser-backed smoke may be skipped only with a concrete environment reason.

## Stop Conditions

Stop prework and report the blocker if:

- The existing Network planning pack conflicts with current source or tests.
- `PHASE_0_BASELINE.md` or any newer baseline claims the served-static Network
  helper is parent-plus-child aware, but live
  `tests/python/desktop/application_facade_test_support.py` still fetches only
  `/assets/networkView.js` into `network_view_js`.
- Route ownership guards are stale and command code would move next.
- A proposed child module needs to load after `networkView.js`.
- A proposed split would duplicate selected worker, lifecycle row, evidence row,
  state-file, filter, last-payload, or dry-run-cache state.
- Any command flow would lose strict confirmation, dry-run freshness, command
  journal evidence, or backend route authority.

## Final Prework Report

End with:

- change packet ID
- current file size and public contract counts
- ledgers produced
- proposed first extraction phase
- validation commands and results
- uncovered unrelated dirty files
- explicit statement that no runtime behavior changed
