---
file: src/mediapipeline/contracts/api_commands.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-06-05
last_reviewed: 2026-06-04
sha256: 912d94fe2d71b98d1e4e87c140bc9c42a0a9e1702ef31e6e0e47f906f8ac02a8
---
# `src/mediapipeline/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads.

**Classes:** `ApiCommandPayload`, `AuditExportRerunCsvCommandPayload`, `AuditIgnoreCommandPayload`, `AuditScorePolicyCommandPayload`, `BackendShutdownCommandPayload`, `EmptyCommandPayload`, `FailureCommandPayload`, `FinalLibraryPromoteQueueCommandPayload`, `FinalLibraryPromotionRunCommandPayload`, `MaintenanceCompletedBackfillDryRunCommandPayload`, `MaintenanceDependencyAtlasCommandPayload`, `MaintenanceReleaseBuildCommandPayload`, `MaintenanceReleaseDryRunCommandPayload`, `MetricsBackfillCommandPayload`, `MetricsSourcesCommandPayload`
**Public functions:** `command_model_for_route()`, `validate_api_command_payload()`
**In-repo imports:** `mediapipeline.contracts.source_media`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/api_commands.py`._
