# Completed View Split Plan

Date: 2026-06-03

## Scope

Target file:
`DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/completedView.js`

Current audit signal:

- 1,597 lines.
- Second-highest dependency-surface score from the 2026-06-03 god-file audit.
- 160 top-level declarations, 127 public exports, 4 backend routes, 5 DOM IDs,
  and 1 event type in the generated WebView public contract baseline.

This is a WebView rendering and command-delegation split. Backend ownership of
completed-output acceptance, publish/final-placement evidence, repairs, reruns,
and filesystem mutation must not move into the frontend.

## Placement

Prefer the existing foldered Completed asset area:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/completed/`

The current root-level `completedView.*.js` files should be treated as existing
compatibility slices, not a pattern to expand indefinitely.

## Proposed Slices

1. `completed/selection.js`
   - Move selected-row keys, row-key helpers, row selection, selected-row
     summary state, and detail dispatch helpers.
   - Candidate state/functions include `selectedCompletedRowKey`,
     `selectedCompletedPendingProofKey`, `selectedCompletedSizeEvidenceKey`,
     `completedRowKey`, `selectCompletedRow`, selected at-a-glance helpers, and
     selected detail render dispatch.

2. `completed/openActions.js`
   - Move completed output open request/status/history helpers.
   - Owns frontend delegation to `/api/completed/open`; it must not open raw
     filesystem paths directly.
   - Candidate functions include completed open busy-state helpers, diagnostic
     open target lines, open history formatting, and open command recognition.

3. `completed/promotionCommands.js`
   - Move final-library promotion pause/resume/promote command button handling.
   - Owns frontend delegation to `/api/final-library-promotion/pause`,
     `/api/final-library-promotion/resume`, and
     `/api/final-library-promotion/promote-queue`.
   - Keep command confirmation and backend result display unchanged.

4. `completed/statusBoards.js`
   - Move local read-only board rendering that remains in the parent after
     existing `completedView.evidence.js`, `completedView.proof.js`, and
     `completedView.review.js` slices.
   - Good candidates are workflow, integrity, runtime, consistency, validation,
     size-review, and breakdown render helpers.

## Parent Responsibilities To Preserve

- `window.mediaPipelineCompletedView` remains the public namespace.
- Existing public flat exports remain until generated contract evidence proves
  they can be removed.
- The parent remains the loaded payload owner and calls child renderers.
- Completed/Pending proof remains evidence-only. Do not add repair, delete,
  publish, drain, or rerun mutation controls during this split.

## Validation

Before editing:

```powershell
npm run webview:prework:check
```

After each slice:

```powershell
npm run webview:check
npm run webview:lint:budget:check
npm run webview:map
npm run webview:contract
npm run webview:routes
```

Focused tests:

```powershell
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_application_facade_web_static -q
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_webview_frontend_mutation_boundary -q
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_webview_browser_completed_pending_proof_smoke -q
```
