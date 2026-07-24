---
file: src/mediapipeline/contracts/api_commands.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-07-23
last_reviewed: 2026-06-04
sha256: 2cb56cb52e556bef6a0ef46d40c456320482fe573d65994117488d91402a7335
---
# `src/mediapipeline/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads. The Local API wire shape remains owned by the existing routes. These models describe the known per-route fields while allowing existing additive fields so the command-handler migration can proceed without breaking WebView callers.

**Public symbols:** `ApiCommandPayload`, `AuditExportRerunCsvCommandPayload`, `AuditIgnoreCommandPayload`, `AuditScorePolicyCommandPayload`, `AuditSourcesCommandPayload`, `AuditSourcesScanCommandPayload`, `AuditStartCommandPayload`, `AuditStopCommandPayload`, `BackendShutdownCommandPayload`, `command_model_for_route`, `DiagnosticsTdarrMatrixAuditCommandPayload`, `DiagnosticsTdarrMatrixEvidenceOpenCommandPayload`, `DiagnosticsTdarrMatrixRerunCommandPayload`, `EmptyCommandPayload`, `FailureArchiveEvidenceCommandPayload`, `FailureArtifactCleanupCommandPayload`, `FailureCommandPayload`, `FailureLifecycleCommandPayload`, `FailureOpenCommandPayload`, `FinalLibraryPromoteQueueCommandPayload`, `FinalLibraryPromotionRunCommandPayload`, `LifecycleReconciliationApplyCommandPayload`, `LifecycleReconciliationDryRunCommandPayload`, `MaintenanceCompletedBackfillDryRunCommandPayload`, `MaintenanceDependencyAtlasCommandPayload`, `MaintenanceDependencyAtlasOpenFolderCommandPayload`, `MaintenanceReleaseBuildCommandPayload`, `MaintenanceReleaseDryRunCommandPayload`, `MaintenanceRetentionDryRunCommandPayload`, `MaintenanceStateJournalArchiveCommandPayload`
**In-repo imports:** `mediapipeline.contracts.source_media`
**HTTP routes:** `/api/audit/export-rerun-csv`, `/api/audit/ignore`, `/api/audit/score-policy`, `/api/audit/sources`, `/api/audit/sources/scan`, `/api/audit/start`, `/api/audit/stop`, `/api/backend/lifecycle/reconcile`, `/api/backend/lifecycle/reconcile-dry-run`, `/api/backend/shutdown`, `/api/completed/open`, `/api/completed/reconcile-manifest`, `/api/completed/reconcile-manifest-dry-run`, `/api/completed/repair-sidecar-metadata`, `/api/completed/repair-sidecar-metadata-dry-run`, `/api/diagnostics/encoder-capabilities/refresh`, `/api/diagnostics/open`, `/api/diagnostics/tdarr-matrix-audit`, `/api/diagnostics/tdarr-matrix/evidence/open`, `/api/diagnostics/tdarr-matrix/rerun`, `/api/failures/archive-evidence`, `/api/failures/artifacts/cleanup`, `/api/failures/clear`, `/api/failures/lifecycle`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/api_commands.py`._
