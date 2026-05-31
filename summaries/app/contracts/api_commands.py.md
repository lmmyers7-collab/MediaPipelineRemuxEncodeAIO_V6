---
file: app/contracts/api_commands.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-05-31
last_reviewed: 2026-05-28
sha256: 468e9fe1a66bf360af60acc87f401a28c783fe735351bcfb17a413eada4429c9
---
# `app/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads.

**Classes:** `ApiCommandPayload`, `BackendShutdownCommandPayload`, `EmptyCommandPayload`, `FailureCommandPayload`, `FinalLibraryPromoteQueueCommandPayload`, `FinalLibraryPromotionRunCommandPayload`, `MaintenanceCommandPayload`, `MaintenanceDependencyAtlasCommandPayload`, `MaintenanceReleaseBuildCommandPayload`, `OpenLocationCommandPayload`, `PipelineControlCommandPayload`, `PipelineStartCommandPayload`, `ProcessControlCommandPayload`, `QueueFileOverridesCommandPayload`, `QueuePriorityCommandPayload`
**Public functions:** `command_model_for_route()`, `validate_api_command_payload()`
**In-repo imports:** `app.contracts.source_media`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/contracts/api_commands.py`._
