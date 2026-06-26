# WebView Scope Preview Operator Guide

Date: 2026-05-15

Short reference for the **Queue Backend Launch Scope Preview** and **Pending Publish Backend Drain Scope Preview** panels added to the WebView. Both panels are read-only evidence surfaces. They clarify what the backend will evaluate versus what the table is merely displaying.

---

## What the Queue Backend Launch Scope Preview Proves

The Queue Backend Launch Scope Preview tells the operator:

- How many rows are loaded in the current queue snapshot.
- How many of those rows are currently visible after the active display filters.
- Whether a row is selected (selected-row detail is display-only — it does not narrow the backend's launch scope).
- The backend route that owns launch: `POST /api/pipeline/start` with a required `mode` field.
- Cached backend preflight evidence: the last backend preflight result and its timestamp.
- Recent backend start evidence from the command journal: the last pipeline start result.

**Interpretation**: Even if you have filtered the Queue table to show only a subset of rows, the backend will evaluate its full snapshot when you press Start. The visible table rows are what you are *looking at*, not what the backend *acts on*. The scope preview makes that boundary explicit.

---

## What the Queue Backend Launch Scope Preview Does NOT Prove

- That the backend will accept the next launch (only the backend preflight does that).
- That all blocked/review rows are safe to ignore (read selected-row detail; filter warnings are not substitutes for investigation).
- That a pipeline has been launched (that requires a POST and a confirmed command-journal result).
- That the queue is complete (new rows may arrive between the snapshot load and a start).

---

## What the Pending Backend Drain Scope Preview Proves

The Pending Publish Backend Drain Scope Preview tells the operator:

- How many parked rows are loaded in the current pending snapshot.
- How many of those rows are currently visible after the active display filters.
- Whether a row is selected (selected-row detail does not narrow the backend's drain scope).
- The backend route that owns drain: `POST /api/pipeline/start` with `mode: drain_pending_pushes`.
- The most recent durable drain summary from the backend.
- Recent drain evidence from the command journal.
- Whether a `frontend_guard` command has been appended locally (e.g., after a blocked Publish Parked Outputs click).

**Interpretation**: Even if you filter the Pending Publish table to show only specific rows, the backend drain will act on all parked rows in its own state, not only what is visible. The scope preview makes that boundary explicit. This is especially important when blocked/review rows are hidden by a status or investigation filter.

---

## What the Pending Backend Drain Scope Preview Does NOT Prove

- That all parked rows are safe to drain (blocked/review rows still require investigation; the Publish Button Guard blocks drain when recovery-plan blockers exist).
- That a drain was completed (only a confirmed command-journal drain result proves that).
- That parked rows match current Completed rows (use the Completed-to-Pending overlap proof in the Completed page for that).

---

## How to Interpret Filters, Selected Rows, Render Caps, and Command-History Evidence

| Element | What it controls | What it does NOT control |
|---|---|---|
| Display filter (text/status/investigation) | Which rows are visible in the WebView table | Backend action scope (launch, drain, rerun, cleanup) |
| Selected row | Which row's detail panel is shown on the right | Backend action scope or process priority |
| Render cap (250 rows shown / N loaded) | How many rows the WebView renders for performance | Backend action scope; backend acts on all loaded rows |
| Command-history evidence | A bounded journal of recent POST results, session-only | Any backend decision or process state |

Render-cap disclosure notes appear when more than 250 rows are loaded. They always state that the backend's scope is not narrowed to the visible subset.

Filter warnings appear when blocked or review rows are hidden by an active filter. These warnings do not auto-clear when you dismiss the filter — investigation is the correct response.

---

## Safe Next Actions When Hidden Blocked/Review Rows Exist

If the filter warning says hidden blocked or review rows exist:

1. **Clear the filter** — use the clear-filter button to restore the full table view.
2. **Inspect the hidden rows** — select each blocked/review row and read the detail panel and combined review plan.
3. **Follow the owning-page guidance** — the combined review plan tells you which Diagnostics tail, Completed row, or recovery-plan step to read first.
4. **Do not drain or launch while blocked rows are hidden** — the backend scope preview confirms the backend will still evaluate those rows. The Publish Button Guard independently blocks drain when blockers exist, but the Queue launch flow may still proceed if only review rows are hidden.

---

## Mutation Guardrail

Both the Queue Backend Launch Scope Preview and the Pending Publish Backend Drain Scope Preview panels:

- Are read-only evidence surfaces.
- Do not post any routes.
- Do not launch, drain, publish, rename, save, rewrite state, delete files, or touch media.
- Refresh automatically when the page payload refreshes.

The launch authority remains: `POST /api/pipeline/start` on the Launch page, backend-owned, guarded by backend preflight and launch-lock.

The drain authority remains: `POST /api/pipeline/start` with `mode: drain_pending_pushes` on the Pending Publish page, backend-owned, guarded by the Publish Button Guard and backend drain recovery-plan result.

---

## See Also

- Queue page scope behavior: `docs/CURRENT_PROJECT_STATE.md`
- Pending Publish drain ownership: `docs\archive\admin-audits\PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md`
- Full command route classification: `docs\archive\completed-audits\WEBVIEW_APIPOST_MUTATION_REVIEW.md`
- Browser smoke boundary: `docs\testing\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`

---

## Task Output

```
Task ID: CLN4-003
Files inspected: docs\DOCS_INDEX.md, docs\archive\completed-audits\WEBVIEW_APIPOST_MUTATION_REVIEW.md, docs\testing\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md, apps\desktop\webview\static\assets\queueView.js, apps\desktop\webview\static\assets\pendingPublishView.js
Files changed: docs\operator\WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md (created)
Validation: Test-Path docs\operator\WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md; Select-String -Path docs\operator\WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md -Pattern "selected row|filters|backend-owned|Mutation guardrail"
Findings: New operator guide created covering Queue Backend Launch Scope Preview, Pending Backend Drain Scope Preview, filter/selected-row/render-cap interpretation, safe next actions, and mutation guardrail.
Open questions: None.
Risk: Low — documentation only.
```
