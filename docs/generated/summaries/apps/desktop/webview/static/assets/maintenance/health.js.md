---
file: apps/desktop/webview/static/assets/maintenance/health.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: c4d015e3a11ae7b0de05b777834db419b9052b1edb37dfaf95df634df0f0382d
---
# `apps/desktop/webview/static/assets/maintenance/health.js`

**Purpose:** JavaScript implementation for health; exposes activateQuickLink, createMaintenanceHealth, focusMaintenanceQuickLinkTarget.

**Public symbols:** `activateQuickLink`, `createMaintenanceHealth`, `focusMaintenanceQuickLinkTarget`, `maintenanceActiveRows`, `maintenanceDetailLines`, `maintenanceDiagnosticsActionsForRow`, `maintenanceHealthErrorProgress`, `maintenanceOptionalWarningRows`, `maintenanceProgressStatus`, `maintenanceProgressStepLines`, `maintenanceReadinessLines`, `maintenanceReadinessStatus`, `maintenanceRealMediaBoundaryLines`, `maintenanceRequiredMissingRows`, `maintenanceToolchainLines`, `maintenanceToolchainStatus`, `pollMaintenanceProgress`, `renderMaintenance`, `renderMaintenanceDetail`, `renderMaintenanceDiagnosticsActions`, `renderMaintenanceHealthProgress`, `renderMaintenanceReadiness`, `renderMaintenanceReadinessError`, `renderMaintenanceRows`, `renderMaintenanceToolchain`, `requestMaintenanceDiagnosticsAction`, `selectMaintenanceRow`, `startMaintenanceProgressPolling`, `stopMaintenanceProgressPolling`
**In-repo imports:** `window.__maintenanceHealthModule`, `window.clearInterval`, `window.setInterval`
**HTTP routes:** `/api/maintenance`, `/api/maintenance/progress`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/maintenance/health.js`._
