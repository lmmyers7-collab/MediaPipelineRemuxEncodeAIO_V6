---
file: apps/desktop/webview/static/assets/completedView.repair.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-06-19
last_reviewed: 2026-06-19
sha256: 69c774aa68d8b4e609b90c16989ea9f00568d4c1dcc52e31cfa80ab1f8fd4747
---
# `apps/desktop/webview/static/assets/completedView.repair.js`

**Purpose:** JavaScript implementation for completed view repair; exposes actionConfig, applyRequest, clearStaleDryRunIfSelectionChanged.

**Public symbols:** `actionConfig`, `applyRequest`, `clearStaleDryRunIfSelectionChanged`, `createCompletedRepairModule`, `defaultLines`, `diffSummaryLines`, `dryRunRequest`, `historyLine`, `initCompletedRepairEvents`, `isCompletedRepairCommand`, `mutationGuardrailLine`, `postApply`, `postDryRun`, `renderAction`, `renderCompletedRepairControls`, `renderCompletedRepairHistory`, `repairDryRunIsSafeForSelection`, `repairResultData`, `requestCompletedRepairApply`, `requestCompletedRepairDryRun`, `resultLines`, `selectedKeys`, `selectedRowKey`, `setBusy`, `statusText`, `wouldNotTouchLines`
**In-repo imports:** `window.__completedViewRepairModule`, `window.apiPost`, `window.confirm`
**HTTP routes:** `/api/completed/reconcile-manifest`, `/api/completed/reconcile-manifest-dry-run`, `/api/completed/repair-sidecar-metadata`, `/api/completed/repair-sidecar-metadata-dry-run`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/completedView.repair.js`._
