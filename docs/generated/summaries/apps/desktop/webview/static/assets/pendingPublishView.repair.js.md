---
file: apps/desktop/webview/static/assets/pendingPublishView.repair.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-06-20
last_reviewed: 2026-06-19
sha256: e75ecc9969f7be76a424a850099772f188e9895320b62afb23c3c9e609652e6e
---
# `apps/desktop/webview/static/assets/pendingPublishView.repair.js`

**Purpose:** JavaScript implementation for pending publish view repair; exposes clearStaleDryRunIfSelectionChanged, createPendingPublishRepairModule, dryRunIsSafeForSelection.

**Public symbols:** `clearStaleDryRunIfSelectionChanged`, `createPendingPublishRepairModule`, `dryRunIsSafeForSelection`, `initPendingRepairManifestEvents`, `isPendingRepairManifestCommand`, `isPendingRepairOrphanCommand`, `orphanDefaultLines`, `pendingOrphanDryRunIsSafeForSelection`, `pendingRepairDryRunIsSafeForSelection`, `pendingRepairManifestApplyRequest`, `pendingRepairManifestDryRunRequest`, `pendingRepairManifestHistoryLine`, `pendingRepairManifestResultLines`, `pendingRepairManifestStatus`, `pendingRepairOrphanApplyRequest`, `pendingRepairOrphanDryRunRequest`, `pendingRepairOrphanStatus`, `renderPendingRepairManifestControls`, `renderPendingRepairManifestHistory`, `renderPendingRepairOrphanControls`, `renderPendingRepairOrphanHistory`, `repairDefaultLines`, `repairDiffSummaryLines`, `repairMutationGuardrailLine`, `repairResultData`, `repairSelectedKeys`, `repairWouldNotTouchLines`, `requestPendingRepairManifestApply`, `requestPendingRepairManifestDryRun`, `requestPendingRepairOrphanApply`, `requestPendingRepairOrphanDryRun`, `selectedRowKey`, `setPendingRepairManifestBusy`, `setPendingRepairOrphanBusy`
**In-repo imports:** `window.__pendingPublishRepairModule`, `window.apiPost`, `window.confirm`
**HTTP routes:** `/api/pending-publish/reconcile-orphan-payloads`, `/api/pending-publish/reconcile-orphan-payloads-dry-run`, `/api/pending-publish/repair-manifest`, `/api/pending-publish/repair-manifest-dry-run`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/pendingPublishView.repair.js`._
