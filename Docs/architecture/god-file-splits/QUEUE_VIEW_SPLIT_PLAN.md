# Queue View Split Plan

Date: 2026-06-03

## Scope

Target file:
`DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/queueView.js`

Current audit signal:

- 3,902 lines.
- Largest WebView god file by line count in the 2026-06-03 audit.
- 258 top-level declarations, 78 public exports, 7 backend routes, 50 DOM IDs,
  and 5 event types in the generated WebView public contract baseline.

The current project state notes that command-adjacent Queue priority, strategy,
and file-overrides behavior intentionally remains in `queueView.js`. Treat this
as an explicit split pass, not opportunistic cleanup.

## Placement

Prefer the existing foldered Queue asset area:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/queue/`

Existing root-level files such as `queueView.detail.js`,
`queueView.launch.js`, `queueView.review.js`, and `queueView.summary.js` are
compatibility slices. New slices should move toward the foldered layout.

## Proposed Slices

1. `queue/selection.js`
   - Move selected queue-row state, row-key helpers, selected/excluded row
     helpers, and selection render dispatch.
   - Candidate functions include `queueRowKey`, `getSelectedQueueRow`,
     `getLastQueuePayload`, `getLastQueueRows`, `selectQueueRow`,
     `selectQueueExcludedRow`, and selected-row detail dispatch.

2. `queue/openActions.js`
   - Move `/api/queue/open` delegation, busy-state handling, open target
     summaries, and open command history.
   - Must continue to submit backend selector keys, not raw path mutation.

3. `queue/priorityStrategy.js`
   - Deferred until route ownership baselines are updated deliberately.
   - Move priority marker, priority bulk, queue strategy load/apply, and
     strategy selector event handling.
   - Owns frontend delegation only for `/api/queue/priority` and
     `/api/queue/strategy`.

4. `queue/fileOverrides.routePreview.js`
   - Move route-preview UI collection, local validation display, preview result
     rendering, and `/api/queue/file-overrides/route-preview` delegation.

5. `queue/fileOverrides.folderPreview.js`
   - Move folder-preview/folder-rule UI collection and
     `/api/queue/file-overrides/folder-preview` plus
     `/api/queue/file-overrides/folder-rule` delegation.

6. `queue/fileOverrides.drawer.js`
   - Move the file-override drawer state/rendering that does not own backend
     media policy.

## Parent Responsibilities To Preserve

- `window.mediaPipelineQueueView` remains the public namespace.
- Queue launch scope remains backend-owned. The WebView may show selected-row
  guidance and backend preview evidence only.
- No frontend code may mutate queue files, persisted settings, source media,
  scratch media, pending publish manifests, or output paths.
- Existing compatibility exports stay until the public-contract baseline proves
  they can be removed.

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
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_application_facade_queue -q
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_webview_frontend_mutation_boundary -q
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_webview_browser_launch_queue_readiness_smoke -q
```
