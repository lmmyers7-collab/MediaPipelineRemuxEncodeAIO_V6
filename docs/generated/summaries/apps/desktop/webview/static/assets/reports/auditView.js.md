---
file: apps/desktop/webview/static/assets/reports/auditView.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: observability
token_priority: medium
owner_domain: webview
last_modified: 2026-07-10
last_reviewed: 2026-06-24
sha256: 7134443b7e9fc60657fd661c1c81c74dc20ccd766289c856777a6f1bb32b78ce
---
# `apps/desktop/webview/static/assets/reports/auditView.js`

**Purpose:** JavaScript implementation for audit view; exposes auditCompletionTimestamp, auditScoreThresholdValue, auditScoreValue.

**Public symbols:** `auditCompletionTimestamp`, `auditScoreThresholdValue`, `auditScoreValue`, `bindReportAuditScoreGroupInputs`, `clearAuditSelection`, `createReportsAuditViewModule`, `formatAuditScoreThreshold`, `getSelectedAuditRow`, `hiddenAuditSelectionMessage`, `hiddenSelectedAuditCount`, `noop`, `renderAuditControls`, `renderAuditDetail`, `renderAuditPreview`, `renderAuditReviewBoard`, `renderAuditRows`, `renderReportAuditIssueRows`, `reportAuditScoreInputId`, `reportAuditScoreIssueValue`, `reportAuditScoreValue`, `reportSyncAuditScoreIssueDefaults`, `runAuditSelectionAction`, `selectAuditRow`, `selectAuditRowsAtOrAboveScore`, `selectedAuditRowKeysList`, `selectVisibleAuditRows`, `setAuditSelectionFromRows`, `toggleAuditRowSelection`, `updateAuditSelectionControls`, `visibleAuditRows`
**In-repo imports:** `,`, `,
      ].join(`, `, count
        ? `${actionLabel}: selected ${count} audit row${count === 1 ?`, `, count ? `${count} selected` :`, `, selectedCount
        ? `${selectedCount} selected${hiddenCount ? `, ${hiddenCount} hidden by filter` :`, `window.__reportsViewAuditViewModule`
**DOM selectors:** `[data-audit-score-threshold-input]`, `[data-audit-selection-action]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/reports/auditView.js`._
