---
file: app/contracts/api_commands.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-05-29
last_reviewed: 2026-05-28
sha256: 68886bab1aa7053b2c7ae5394e36d15a88b5c94fcc3d1209fdfb586267341157
---
# `app/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads.

**Classes:** `ApiCommandPayload`, `BackendShutdownCommandPayload`, `EmptyCommandPayload`, `FailureCommandPayload`, `MaintenanceCommandPayload`, `MaintenanceReleaseBuildCommandPayload`, `OpenLocationCommandPayload`, `PipelineControlCommandPayload`, `PipelineStartCommandPayload`, `ProcessControlCommandPayload`, `QueueFileOverridesCommandPayload`, `QueuePriorityCommandPayload`, `QueuePriorityItemPayload`, `QueueStrategyCommandPayload`, `RenameApplyCommandPayload`
**Public functions:** `command_model_for_route()`, `validate_api_command_payload()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/contracts/api_commands.py`._
