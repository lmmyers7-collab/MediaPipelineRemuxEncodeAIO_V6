---
file: app/contracts/api_commands.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-05-29
last_reviewed: 2026-05-28
sha256: 5e23c3ec5abed103f0d698e5a6929bf0d49996110512d008f6ddb6d4a951dae1
---
# `app/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads.

**Classes:** `ApiCommandPayload`, `BackendShutdownCommandPayload`, `EmptyCommandPayload`, `FailureCommandPayload`, `FinalLibraryPromoteQueueCommandPayload`, `FinalLibraryPromotionRunCommandPayload`, `MaintenanceCommandPayload`, `MaintenanceReleaseBuildCommandPayload`, `OpenLocationCommandPayload`, `PipelineControlCommandPayload`, `PipelineStartCommandPayload`, `ProcessControlCommandPayload`, `QueueFileOverridesCommandPayload`, `QueuePriorityCommandPayload`, `QueuePriorityItemPayload`
**Public functions:** `command_model_for_route()`, `validate_api_command_payload()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/contracts/api_commands.py`._
