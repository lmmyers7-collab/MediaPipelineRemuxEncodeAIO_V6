---
file: app/contracts/api_commands.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-06-03
last_reviewed: 2026-05-28
sha256: 641a0c7ab6b8b2e4ec14fb45424bb1536e946e1698078e20288d9f9395bd03fe
---
# `app/contracts/api_commands.py`

**Purpose:** Pydantic contracts for Local API command request payloads.

**Classes:** `ApiCommandPayload`, `AuditExportRerunCsvCommandPayload`, `AuditIgnoreCommandPayload`, `AuditScorePolicyCommandPayload`, `BackendShutdownCommandPayload`, `EmptyCommandPayload`, `FailureCommandPayload`, `FinalLibraryPromoteQueueCommandPayload`, `FinalLibraryPromotionRunCommandPayload`, `MaintenanceCompletedBackfillDryRunCommandPayload`, `MaintenanceDependencyAtlasCommandPayload`, `MaintenanceReleaseBuildCommandPayload`, `MaintenanceReleaseDryRunCommandPayload`, `OpenLocationCommandPayload`, `PipelineBrowseFileCommandPayload`
**Public functions:** `command_model_for_route()`, `validate_api_command_payload()`
**In-repo imports:** `app.contracts.source_media`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/contracts/api_commands.py`._
