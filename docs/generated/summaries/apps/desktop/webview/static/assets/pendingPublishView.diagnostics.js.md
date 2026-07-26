---
file: apps/desktop/webview/static/assets/pendingPublishView.diagnostics.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: observability
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: b2f8e85bcc01381e9d664f3cdfd020cb35be2234f025250a6148f5faa3a54295
---
# `apps/desktop/webview/static/assets/pendingPublishView.diagnostics.js`

**Purpose:** JavaScript implementation for pending publish view diagnostics; exposes createPendingPublishDiagnosticsModule, getPendingOpenInFlight, isPendingOpenCommand.

**Public symbols:** `createPendingPublishDiagnosticsModule`, `getPendingOpenInFlight`, `isPendingOpenCommand`, `pendingAddDiagnosticsAction`, `pendingDiagnosticsActionLabel`, `pendingDiagnosticsActionsForRow`, `pendingDiagnosticsActionStatusText`, `pendingDiagnosticsGuidanceLines`, `pendingOpenHistoryLine`, `pendingSelectedOpenTargetLines`, `rejectPendingOpenWhileBusy`, `renderPendingDiagnosticsLinks`, `renderPendingOpenHistory`, `requestPendingDiagnosticsAction`, `requestPendingPublishOpen`, `setPendingOpenBusy`, `setPendingOpenInFlight`
**In-repo imports:** `window.__pendingPublishDiagnosticsModule`, `window.mediaPipelineAppRowOpenActions`, `window.requestDiagnosticsOpen`, `window.requestDiagnosticsTail`
**HTTP routes:** `/api/pending-publish/open`
**DOM selectors:** `[data-open-pending]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/pendingPublishView.diagnostics.js`._
