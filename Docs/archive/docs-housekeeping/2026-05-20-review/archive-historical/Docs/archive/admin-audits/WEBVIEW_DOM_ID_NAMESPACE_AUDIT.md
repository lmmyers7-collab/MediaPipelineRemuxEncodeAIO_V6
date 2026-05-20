# WebView DOM ID Namespace Audit

Purpose: document the DOM element ID naming convention used across the single-page WebView, confirm no duplicate IDs exist, identify which view file owns each ID prefix, and provide guidance for future additions. This is a static audit document; it does not add new tests.

---

## Architecture Summary

The WebView is a single HTML file (`DesktopApp/mediapipeline_desktop_app/ui_web/static/index.html`) with all element IDs declared in one place. JavaScript view files do not create or clone elements with new IDs at runtime — all IDs are static and present in the HTML at page load.

DOM access is centralized through `byId(id)` in `domHelpers.js`, which wraps `document.getElementById`. View files use `byId()` exclusively; they do not call `document.getElementById` or `document.querySelector` directly. This centralization makes all ID dependencies greppable by searching for `byId("` across the JS assets.

**Total JS files**: 31 (20 view files + 11 utility/helper files)  
**Total HTML files with IDs**: 1 (`index.html`)

---

## ID Prefix Convention

Every element ID uses a kebab-case prefix that matches its owning view file or functional area. The prefix is the first segment before the first hyphen (or the first two segments for disambiguation).

| ID prefix | Owning view file | Examples |
|---|---|---|
| `queue-` | `queueView.js` | `queue-rows`, `queue-filter`, `queue-status-filter`, `queue-investigation-filter`, `queue-detail`, `queue-launch-decision-rows`, `queue-review-rows`, `queue-excluded-rows`, `queue-diagnostics-actions` |
| `completed-` | `completedView.js` | `completed-rows`, `completed-filter`, `completed-status-filter`, `completed-investigation-filter`, `completed-size-review-rows`, `completed-size-evidence-rows`, `completed-output-acceptance-rows`, `completed-route-agreement-rows` |
| `launch-` | `launchView.js` | `launch-settings-risk-rows`, `launch-settings-intent-rows`, `launch-real-media-proof-rows`, `launch-sample-execution-rows`, `launch-sample-execution-detail`, `launch-backend-preflight-rows`, `launch-backend-preflight-refresh-button` |
| `settings-` | `settingsView.js` | `settings-rows`, `settings-filter`, `settings-patch-json`, `settings-active-media-policy-rows`, `settings-save-review-rows`, `settings-backend-result-rows` |
| `diagnostics-` | `diagnosticsView.js` | `diagnostics-log-rows`, `diagnostics-log-filter`, `diagnostics-tail-refresh-button`, `diagnostics-drilldown-actions`, `diagnostics-investigation-actions` |
| `network-` | `networkView.js` | `network-role`, `network-coordinator-target`, `network-worker-rows`, `network-evidence-rows`, `network-readiness-status` |
| `rename-` | `renameView.js` | `rename-mode`, `rename-show`, `rename-season`, `rename-start`, `rename-paths`, `rename-apply-readiness-status`, `rename-apply-readiness-rows`, `rename-detail` |
| `pending-publish-` | `pendingPublishView.js` | `pending-publish-rows`, `pending-publish-filter`, `pending-publish-drain-evidence-rows`, `pending-publish-recovery-plan-rows`, `pending-publish-diagnostics-actions` |
| `reports-` | `reportsView.js` | `reports-failure-rows`, `reports-audit-rows`, `reports-filter`, `reports-detail` |
| `schedule-` | `scheduleView.js` | `schedule-rows`, `schedule-status`, `schedule-detail` |
| `maintenance-` | `maintenanceView.js` | `maintenance-rows`, `maintenance-status`, `maintenance-release-result` |
| `sample-validation-` | `crossPageContextView.js` / `homeView.js` | `sample-validation-decision`, `sample-validation-notes`, `sample-validation-preview-button`, `sample-validation-append-button`, `sample-validation-result`, `sample-validation-records`, `sample-validation-detail`, `sample-validation-execution-status`, `sample-validation-execution-summary`, `sample-validation-execution-rows`, `sample-validation-execution-legend`, `sample-validation-execution-detail` |
| `cross-page-` | `crossPageContextView.js` | `cross-page-context-status`, `cross-page-conflict-rows`, `cross-page-sample-rows`, `cross-page-real-media-rows`, `cross-page-real-media-detail`, `cross-page-validation-template` |
| `home-` | `homeView.js` | `home-readiness-status`, `home-settings-trust-status`, `home-active-work-status`, `home-runtime-open-status` |
| `pipeline-` | `launchView.js` / `progressView.js` | `pipeline-state`, `pipeline-start-mode`, `pipeline-start-sleep`, `pipeline-event-rows` |
| `pipeline-start-` | `launchView.js` | `pipeline-start-mode`, `pipeline-start-sleep`, `pipeline-start-schedule-override`, `pipeline-start-show-config`, `pipeline-start-show-console` |
| `audit-start-` | `launchView.js` | `audit-start-library-root`, `audit-start-include-sidecars` |
| `progress-` | `progressView.js` | `progress-detail-rows`, `progress-evidence-rows`, `progress-evidence-status`, `progress-evidence-detail` |
| `command-` | `commandHistory.js` | `command-rows`, `command-status`, `command-summary`, `command-detail`, `command-diagnostics-actions` |
| `control-` | `launchView.js` | `control-readiness-status`, `control-readiness`, `control-status`, `control-history` |
| `active-job-` | `diagnosticsView.js` | `active-job-detail-rows`, `active-job-diagnostics-actions` |
| `telemetry-` | `homeView.js` | `telemetry-readiness-status`, `telemetry-readiness-summary` |
| `gpu-` | `homeView.js` | `gpu-value`, `gpu-chart`, `gpu-rows`, `gpu-detail-status`, `gpu-note` |
| `cpu-` | `homeView.js` | `cpu-value`, `cpu-chart` |
| `ram-` | `homeView.js` | `ram-value`, `ram-chart` |
| `daily-driver-` | `homeView.js` | `daily-driver-status`, `daily-driver-summary`, `daily-driver-rows`, `daily-driver-legend` |
| `state-pill` | `app.js` | `state-pill` (global status indicator) |
| `refresh-*` | `app.js` | `refresh-health`, `refresh-button` |
| `activity` | `app.js` | `activity` (main activity label) |
| `close-readiness` | `app.js` | `close-readiness` |
| `app-version` | `app.js` | `app-version` |

---

## Duplicate ID Audit Result

**No duplicate element IDs found** in the current codebase.

The strict prefix convention enforces this structurally: each view owns its prefix and no two views use the same prefix. Global/shared elements (`state-pill`, `refresh-button`, `activity`, `close-readiness`) are owned by `app.js` and have unique, unprefixed or distinctly-named IDs.

---

## Dynamic ID Construction — Not Used

No `byId()` call uses string concatenation or template literals to construct an ID at runtime. All ID strings are static string literals. This means the full ID namespace is statically greppable and there is no risk of a dynamic ID collision that static analysis would miss.

---

## Rules For Future ID Additions

1. **Use the view's prefix**: IDs added to `queueView.js` must start with `queue-`. IDs added to the home view must start with `home-`, `daily-driver-`, `sample-validation-`, `cross-page-`, `telemetry-`, `cpu-`, `gpu-`, or `ram-`.
2. **Declare in index.html first**: add the element to `index.html` before adding the `byId()` call in the view file.
3. **Use only static string literals**: do not construct IDs dynamically via concatenation.
4. **One ID per element**: do not reuse the same ID for two elements. If two independent elements need the same logical role in different contexts, use different IDs (e.g., `queue-filter` and `completed-filter`, not `filter` for both).
5. **No cross-view ID access**: view files should not call `byId()` with an ID owned by a different view. Shared data flows through backend payload refresh, not DOM-to-DOM reads.

---

## How To Verify No New Duplicates

To check for duplicate ID declarations in index.html:

```powershell
$ids = (Select-String -Path 'DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html' -Pattern 'id="([^"]+)"' -AllMatches).Matches |
    ForEach-Object { $_.Groups[1].Value }
$duplicates = $ids | Group-Object | Where-Object { $_.Count -gt 1 }
if ($duplicates) { $duplicates | Format-Table Name, Count } else { "No duplicate IDs." }
```

To find all IDs accessed in JS but not declared in index.html (orphan JS references):

```powershell
$htmlIds = (Select-String -Path 'DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html' -Pattern 'id="([^"]+)"' -AllMatches).Matches |
    ForEach-Object { $_.Groups[1].Value }
$jsRefs = (Select-String -Path 'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js' -Pattern 'byId\("([^"]+)"\)' -AllMatches).Matches |
    ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
$orphans = $jsRefs | Where-Object { $_ -notin $htmlIds }
if ($orphans) { $orphans } else { "No orphan JS references." }
```

Run both checks from the repository root before adding new IDs.

---

## See Also

- `domHelpers.js` — `byId()` implementation and other shared DOM helpers
- `index.html` — single source of truth for all element ID declarations
- WebView smoke catalog: `WEBVIEW_SMOKE_TEST_CATALOG.md`
