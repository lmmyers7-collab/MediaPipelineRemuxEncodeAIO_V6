---
file: src/mediapipeline/contracts/api_commands.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: aed838132b9b8414b8e015221c56ef4be5c6b46626be65fd09d9f8e529a71717
---
# `src/mediapipeline/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads.

**Classes:** `ApiCommandPayload`, `AuditExportRerunCsvCommandPayload`, `AuditIgnoreCommandPayload`, `AuditScorePolicyCommandPayload`, `AuditSourcesCommandPayload`, `AuditSourcesScanCommandPayload`, `AuditStartCommandPayload`, `AuditStopCommandPayload`, `BackendShutdownCommandPayload`, `DiagnosticsTdarrMatrixAuditCommandPayload`, `DiagnosticsTdarrMatrixEvidenceOpenCommandPayload`, `DiagnosticsTdarrMatrixRerunCommandPayload`, `EmptyCommandPayload`, `FailureArchiveEvidenceCommandPayload`, `FailureArtifactCleanupCommandPayload`
**Public functions:** `command_model_for_route()`, `validate_api_command_payload()`
**In-repo imports:** `mediapipeline.contracts.source_media`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/api_commands.py`._
