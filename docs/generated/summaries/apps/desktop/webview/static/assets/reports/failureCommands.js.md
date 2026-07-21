---
file: apps/desktop/webview/static/assets/reports/failureCommands.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-01
last_reviewed: 2026-06-24
sha256: 5aacaa68a843bd3857aded64fe9cfe16ed3c71008f846ad17095f6012fa2521d
---
# `apps/desktop/webview/static/assets/reports/failureCommands.js`

**Purpose:** JavaScript implementation for failure commands; exposes allFailureMarkerPaths, appendFailureArtifactCleanupDetails, appendFailureArtifactCleanupList.

**Public symbols:** `allFailureMarkerPaths`, `appendFailureArtifactCleanupDetails`, `appendFailureArtifactCleanupList`, `applyLocalFailureMarkerClear`, `artifactCleanupPolicyKey`, `artifactCleanupSizeText`, `configureFailurePrimaryAction`, `confirmedArtifactCleanupPayload`, `createReportsFailureCommandsModule`, `failureArchivePreviewKey`, `failureArchiveRequest`, `failureArtifactCleanupPayload`, `failureArtifactCleanupRequest`, `failureClearPreviewKey`, `failureClearRequest`, `failureLifecycleBackendReason`, `failureLifecyclePreviewKey`, `failureLifecyclePreviewRequired`, `failureLifecycleRequest`, `failureLifecycleRequiresReason`, `failureLifecycleStepId`, `failureMarkerSourcePath`, `failureTransition`, `hiddenFailureSelectionMessage`, `noop`, `renderFailureArchiveResult`, `renderFailureArtifactCleanupResult`, `renderFailureClearResult`, `renderFailureLifecycleResult`, `requestFailureArtifactCleanup`, `requestFailureEvidenceArchive`, `requestFailureEvidenceOpen`, `requestFailureLifecycleTransition`, `requestFailureMarkerClear`, `requestFailureRowClear`
**In-repo imports:** `window.__reportsViewFailureCommandsModule`, `window.confirm`, `window.showPage`
**HTTP routes:** `/api/failures/archive-evidence`, `/api/failures/artifacts/cleanup`, `/api/failures/clear`, `/api/failures/lifecycle`, `/api/failures/open`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/reports/failureCommands.js`._
