---
file: src/mediapipeline/contracts/api_commands.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-06-19
last_reviewed: 2026-06-04
sha256: 44e0718f99e288d67816ffd8a74fc7f43755f3cf553d0e0c61c4519cb409635e
---
# `src/mediapipeline/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads.

**Classes:** `ApiCommandPayload`, `AuditExportRerunCsvCommandPayload`, `AuditIgnoreCommandPayload`, `AuditScorePolicyCommandPayload`, `BackendShutdownCommandPayload`, `DiagnosticsTdarrMatrixAuditCommandPayload`, `DiagnosticsTdarrMatrixEvidenceOpenCommandPayload`, `DiagnosticsTdarrMatrixRerunCommandPayload`, `EmptyCommandPayload`, `FailureCommandPayload`, `FinalLibraryPromoteQueueCommandPayload`, `FinalLibraryPromotionRunCommandPayload`, `MaintenanceCompletedBackfillDryRunCommandPayload`, `MaintenanceDependencyAtlasCommandPayload`, `MaintenanceDependencyAtlasOpenFolderCommandPayload`
**Public functions:** `command_model_for_route()`, `validate_api_command_payload()`
**In-repo imports:** `mediapipeline.contracts.source_media`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/api_commands.py`._
