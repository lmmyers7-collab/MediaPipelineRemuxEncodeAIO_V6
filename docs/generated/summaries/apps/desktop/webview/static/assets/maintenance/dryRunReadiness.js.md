---
file: apps/desktop/webview/static/assets/maintenance/dryRunReadiness.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-07-11
sha256: 31931eecdefa6d786ff9b5f424deaec8c8ec2841bf4d39670a7bdb6e0030c124
---
# `apps/desktop/webview/static/assets/maintenance/dryRunReadiness.js`

**Purpose:** JavaScript implementation for dry run readiness; exposes createMaintenanceDryRunReadiness, formatMaintenanceDryRunHistoryLine, isMaintenanceDryRunCommand.

**Public symbols:** `createMaintenanceDryRunReadiness`, `formatMaintenanceDryRunHistoryLine`, `isMaintenanceDryRunCommand`, `maintenanceDryRunConfidenceLines`, `maintenanceDryRunConfidenceStatus`, `maintenanceDryRunDetailLine`, `maintenanceDryRunLabel`, `maintenanceLatestDryRun`, `maintenanceReleaseOptionReviewLines`, `refreshChangeLedger`, `refreshMaintenance`, `renderMaintenanceDryRunConfidence`, `renderMaintenanceDryRunHistory`
**In-repo imports:** `window.__maintenanceDryRunReadinessModule`, `window.setTimeout`
**HTTP routes:** `/api/maintenance`, `/api/maintenance/change-ledger?limit=`, `/api/maintenance/progress`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/maintenance/dryRunReadiness.js`._
