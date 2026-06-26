---
file: src/mediapipeline/contracts/api_commands.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-06-26
last_reviewed: 2026-06-04
sha256: 00d198d5b7f089b8347f141cfb5beb24d417c048a165a8122308ae0bec4e65dd
---
# `src/mediapipeline/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads.

**Classes:** `ApiCommandPayload`, `AuditExportRerunCsvCommandPayload`, `AuditIgnoreCommandPayload`, `AuditScorePolicyCommandPayload`, `AuditStopCommandPayload`, `BackendShutdownCommandPayload`, `DiagnosticsTdarrMatrixAuditCommandPayload`, `DiagnosticsTdarrMatrixEvidenceOpenCommandPayload`, `DiagnosticsTdarrMatrixRerunCommandPayload`, `EmptyCommandPayload`, `FailureArchiveEvidenceCommandPayload`, `FailureCommandPayload`, `FailureLifecycleCommandPayload`, `FinalLibraryPromoteQueueCommandPayload`, `FinalLibraryPromotionRunCommandPayload`
**Public functions:** `command_model_for_route()`, `validate_api_command_payload()`
**In-repo imports:** `mediapipeline.contracts.source_media`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/api_commands.py`._
