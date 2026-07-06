---
file: src/mediapipeline/contracts/api_commands.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-07-05
last_reviewed: 2026-06-04
sha256: 25c6efe7fd157800abaa15200376658c7c4a0d4b6e3e63e6e497eb268100273e
---
# `src/mediapipeline/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads.

**Classes:** `ApiCommandPayload`, `AuditExportRerunCsvCommandPayload`, `AuditIgnoreCommandPayload`, `AuditScorePolicyCommandPayload`, `AuditSourcesCommandPayload`, `AuditSourcesScanCommandPayload`, `AuditStartCommandPayload`, `AuditStopCommandPayload`, `BackendShutdownCommandPayload`, `DiagnosticsTdarrMatrixAuditCommandPayload`, `DiagnosticsTdarrMatrixEvidenceOpenCommandPayload`, `DiagnosticsTdarrMatrixRerunCommandPayload`, `EmptyCommandPayload`, `FailureArchiveEvidenceCommandPayload`, `FailureArtifactCleanupCommandPayload`
**Public functions:** `command_model_for_route()`, `validate_api_command_payload()`
**In-repo imports:** `mediapipeline.contracts.source_media`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/api_commands.py`._
