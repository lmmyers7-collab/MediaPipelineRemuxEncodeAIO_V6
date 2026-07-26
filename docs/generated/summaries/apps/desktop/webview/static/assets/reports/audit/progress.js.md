---
file: apps/desktop/webview/static/assets/reports/audit/progress.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: observability
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-07-11
sha256: b8a6ef8ecf4d7ed501482e12dbb60edaec015fcde680e77b551c5da003258021
---
# `apps/desktop/webview/static/assets/reports/audit/progress.js`

**Purpose:** JavaScript implementation for progress; exposes clearReportAuditRefreshTimers, createReportsAuditProgressModule, ensureReportAuditTimer.

**Public symbols:** `clearReportAuditRefreshTimers`, `createReportsAuditProgressModule`, `ensureReportAuditTimer`, `formatReportAuditElapsed`, `parseReportAuditTimestamp`, `renderReportAuditActiveState`, `renderReportAuditProgressPanel`, `renderReportAuditRunningState`, `renderReportAuditStaleState`, `reportAuditAcceptedRunEvidence`, `reportAuditActiveWorkerRows`, `reportAuditCurrentRunEvidence`, `reportAuditHasBackendActiveRunEvidence`, `reportAuditOperationIsBusy`, `reportAuditPriorityCsvPath`, `reportAuditProgressBars`, `reportAuditProgressIsActive`, `reportAuditProgressIsTerminal`, `reportAuditProgressPayload`, `reportAuditProgressSucceeded`, `reportAuditSnapshotCoversAcceptedRun`, `reportAuditSnapshotIsFreshForUi`, `reportAuditSnapshotRunEvidence`, `reportAuditSnapshotTimestampMs`, `reportAuditStaleProgressEvidence`, `reportAuditSyntheticSnapshot`, `scheduleReportAuditRefreshes`, `selectReportAuditPriorityTable`, `settleReportAuditTerminalState`, `stopReportAuditTimerIfIdle`, `updateReportAuditStartButtonState`
**In-repo imports:** `window.__reportsAuditProgressModule`, `window.clearInterval`, `window.clearTimeout`, `window.refreshAll`, `window.setInterval`, `window.setTimeout`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/reports/audit/progress.js`._
