---
file: apps/desktop/webview/static/assets/app/lifecycle.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-19
last_reviewed: 2026-06-04
sha256: bf696c7791eb613cb00711b828b74c660550e893e7d97032f4c0c5e025ac2490
---
# `apps/desktop/webview/static/assets/app/lifecycle.js`

**Purpose:** JavaScript implementation for lifecycle; exposes activeKeyboardPage, activeKeyboardPanel, activePageSelectableRows.

**Public symbols:** `activeKeyboardPage`, `activeKeyboardPanel`, `activePageSelectableRows`, `appendLifecycleTableCell`, `backendLifecycleCommandData`, `backendLifecycleCommandEntries`, `backendLifecycleCommandLine`, `backendLifecycleCommandResultLabel`, `backendLifecycleCommandResultState`, `backendLifecycleCommandSummary`, `backendLifecycleCommandTime`, `clearActivePageFilters`, `dispatchShortcutInputChange`, `focusActivePageDetail`, `focusActivePageSearch`, `initKeyboardShortcuts`, `keyboardShortcutHelpText`, `keyboardShortcutRegistry`, `lifecycleCloseReadinessLabel`, `lifecycleDisplayText`, `lifecycleFactNode`, `lifecycleGenerationText`, `lifecycleResultChip`, `lifecycleStateToken`, `lifecycleStopRequestedText`, `lifecycleWatcherStatus`, `moveActivePageSelection`, `renderBackendLifecycle`, `renderBackendLifecycleHistory`, `renderBackendLifecycleHistoryRows`, `renderBackendLifecycleOverview`, `renderDiagnosticsCloseReadinessOverview`, `renderLifecycleCallout`, `renderLifecycleFacts`, `shortcutElementVisible`
**In-repo imports:** `window.__appLifecycleNavigationModule`, `window.__appLifecycleTopbarModule`, `window.addEventListener`, `window.getComputedStyle`, `window.getLastSnapshot`, `window.mediaPipelineAppLifecycle`, `window.mediaPipelineCompletedView`, `window.mediaPipelinePendingPublishView`, `window.mediaPipelineQueueView`, `window.setTimeout`
**HTTP routes:** `/api/backend/shutdown`
**DOM selectors:** `[data-page-panel].is-visible`, `input, select`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/app/lifecycle.js`._
