---
file: app/contracts/api_commands.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: 5d8a5f967f2f75a22647594323efaf1ff5adefd2d40194421f8c10c093f4ba7c
---
# `app/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads.

**Classes:** `ApiCommandPayload`, `BackendShutdownCommandPayload`, `EmptyCommandPayload`, `FailureCommandPayload`, `FinalLibraryPromoteQueueCommandPayload`, `FinalLibraryPromotionRunCommandPayload`, `MaintenanceCompletedBackfillDryRunCommandPayload`, `MaintenanceDependencyAtlasCommandPayload`, `MaintenanceReleaseBuildCommandPayload`, `MaintenanceReleaseDryRunCommandPayload`, `OpenLocationCommandPayload`, `PipelineBrowseFileCommandPayload`, `PipelineControlCommandPayload`, `PipelineStartCommandPayload`, `ProcessControlCommandPayload`
**Public functions:** `command_model_for_route()`, `validate_api_command_payload()`
**In-repo imports:** `app.contracts.source_media`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/contracts/api_commands.py`._
