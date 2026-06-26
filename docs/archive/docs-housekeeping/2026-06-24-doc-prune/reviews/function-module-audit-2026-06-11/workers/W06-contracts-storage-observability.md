# Worker Review: W06-contracts-storage-observability

## Scope
- Assigned domain: contracts-storage-observability
- Assigned files: 117 files listed below
- Explicit exclusions: none by assignment. Coverage is partial because the user issued a time-box update and requested the worker file be written immediately.
- Summary compliance: generated summaries were checked before opening assigned source files. The review then prioritized high-risk contract, storage, mutation, cleanup, diagnostics, failure, and observability paths.

## Assigned File List

- `ops/pipeline/engine/audit/policy.ps1` (audit, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/audit/probe.ps1` (audit, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/audit/progress.ps1` (audit, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/audit/reports.ps1` (audit, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/audit/rerun_source_identity.ps1` (audit, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/audit/scanner.ps1` (audit, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/failures/failure_state.ps1` (failures, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/naming/destination_plan.ps1` (naming, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/naming/movie_cleanup.ps1` (naming, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/naming/naming.ps1` (naming, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/naming/rename_overrides.ps1` (naming, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/naming/tv_parsing.ps1` (naming, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/observability/logging.ps1` (observability, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/paths/effective_settings.ps1` (paths, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/paths/library_profiles.ps1` (paths, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/paths/output_evidence.ps1` (paths, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/paths/output_path_planning.ps1` (paths, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/paths/path_capability.ps1` (paths, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/shared/executable_resolution.ps1` (shared, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/shared/failure_codes.ps1` (shared, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/shared/media_constants.ps1` (shared, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/shared/native.ps1` (shared, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/shared/native_process_contracts.ps1` (shared, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/shared/path_helpers.ps1` (shared, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/shared/source_identity.ps1` (shared, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/shared/temp_cleanup.ps1` (shared, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/shared/versioning.ps1` (shared, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/storage/disk.ps1` (storage, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/storage/scratch_copy.ps1` (storage, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/storage/state_store.ps1` (storage, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/__init__.py` (contracts, low, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/api_commands.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/config.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/config_coercion.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/config_defaults.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/config_schema_extras.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/config_validators.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/decision_policy.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/height_tolerance.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/lifecycle.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/pipeline_plan.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/runtime_evidence.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/schemas/stages.v1.schema.json` (contracts, medium, contract/config-review, summary=yes)
- `src/mediapipeline/contracts/source_media.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/source_media_adapters.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/source_media_derived.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/source_media_models.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/source_media_streams.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/source_media_values.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/stage_base.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/stage_decide.py` (contracts, high, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/stage_mutation.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/stage_probe.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/stages.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/contracts/verification.py` (contracts, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/__init__.py` (audit, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/facade.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/ignore_manifest.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/preview_policy.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/rerun_contracts.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/rerun_csv.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/rerun_export.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/rerun_file_io.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/rerun_io.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/rerun_metadata.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/rerun_records.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/rerun_service.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/audit/score_policy.py` (audit, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/diagnostics/__init__.py` (diagnostics, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/diagnostics/facade.py` (diagnostics, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/diagnostics/open_policy.py` (diagnostics, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/diagnostics/policy.py` (diagnostics, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/diagnostics/state_summary.py` (diagnostics, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/failures/__init__.py` (failures, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/failures/cleanup_service.py` (failures, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/failures/constants.py` (failures, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/failures/facade.py` (failures, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/failures/file_io.py` (failures, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/failures/markers.py` (failures, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/failures/policy.py` (failures, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/failures/retry_state.py` (failures, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/observability/__init__.py` (observability, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/observability/artifact_freshness.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/observability/logging.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/observability/runtime_outcomes.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/observability/status_files.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/observability/status_policy.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/__init__.py` (observability, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/active_jobs.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/contracts.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/errors.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/eta.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/events.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/facade.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/ffmpeg_progress.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/file_io.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/presentation.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/presentation_labels.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/presentation_lifecycle.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/presentation_progress.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/progress.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/readers.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/service.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/snapshot_runner.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/summary.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/status/summary_sections.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/storage/__init__.py` (storage, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/storage/constants.py` (storage, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/storage/contracts.py` (storage, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/storage/db.py` (storage, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/storage/state_migration.py` (storage, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/telemetry/__init__.py` (observability, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/telemetry/gpu_usage.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/telemetry/health.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/telemetry/nvidia.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/telemetry/service.py` (observability, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/telemetry/system_metrics.py` (observability, medium, code-symbol-review, summary=yes)

## Coverage Ledger

| File | Symbols reviewed | Coverage | Notes |
|---|---:|---|---|
| `ops/pipeline/engine/audit/policy.ps1` | targeted | partial | Reviewed policy normalization/import-ignore persistence symbols only; no finding in reviewed symbols. |
| `ops/pipeline/engine/audit/probe.ps1` | all listed | reviewed | Finding W06-03. |
| `ops/pipeline/engine/audit/progress.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/audit/reports.ps1` | targeted | partial | Reviewed `Export-CsvAtomic` and `Write-AuditReportBundle`; no finding in reviewed symbols. |
| `ops/pipeline/engine/audit/rerun_source_identity.ps1` | all listed | reviewed | Reviewed: no findings. |
| `ops/pipeline/engine/audit/scanner.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/failures/failure_state.ps1` | targeted | partial | Reviewed failure JSON atomic write, marker index, clear failure state, and scratch artifact move paths; no finding in reviewed symbols. |
| `ops/pipeline/engine/naming/destination_plan.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/naming/movie_cleanup.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/naming/naming.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/naming/rename_overrides.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/naming/tv_parsing.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/observability/logging.ps1` | all listed | reviewed | Reviewed: no findings. |
| `ops/pipeline/engine/paths/effective_settings.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/paths/library_profiles.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/paths/output_evidence.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/paths/output_path_planning.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/paths/path_capability.ps1` | all listed | reviewed | Reviewed: no findings. |
| `ops/pipeline/engine/shared/executable_resolution.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/shared/failure_codes.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/shared/media_constants.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/shared/native.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/shared/native_process_contracts.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/shared/path_helpers.ps1` | all listed | reviewed | Reviewed: no findings. |
| `ops/pipeline/engine/shared/source_identity.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/shared/temp_cleanup.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/shared/versioning.ps1` | 0 | pending | Not reviewed due time-box. |
| `ops/pipeline/engine/storage/disk.ps1` | all listed | reviewed | Finding W06-01. |
| `ops/pipeline/engine/storage/scratch_copy.ps1` | all listed | reviewed | Finding W06-04. |
| `ops/pipeline/engine/storage/state_store.ps1` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/__init__.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/contracts/api_commands.py` | targeted | partial | Reviewed high-risk command confirmation and strict payload symbols; Finding W06-02. |
| `src/mediapipeline/contracts/config.py` | targeted | partial | Reviewed schema fields and cross-field validators relevant to storage/subtitle/OCR paths; no finding in reviewed symbols. |
| `src/mediapipeline/contracts/config_coercion.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/config_defaults.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/config_schema_extras.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/config_validators.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/decision_policy.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/contracts/height_tolerance.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/lifecycle.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/contracts/pipeline_plan.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/runtime_evidence.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/schemas/stages.v1.schema.json` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/contracts/source_media.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/source_media_adapters.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/source_media_derived.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/source_media_models.py` | all listed | reviewed | Finding W06-06. |
| `src/mediapipeline/contracts/source_media_streams.py` | all listed | reviewed | Finding W06-06. |
| `src/mediapipeline/contracts/source_media_values.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/stage_base.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/stage_decide.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/stage_mutation.py` | all listed | reviewed | Finding W06-05. |
| `src/mediapipeline/contracts/stage_probe.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/contracts/stages.py` | all listed | reviewed | Finding W06-05. |
| `src/mediapipeline/contracts/verification.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/audit/__init__.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/facade.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/ignore_manifest.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/preview_policy.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/rerun_contracts.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/rerun_csv.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/rerun_export.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/rerun_file_io.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/audit/rerun_io.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/rerun_metadata.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/rerun_records.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/rerun_service.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/audit/score_policy.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/diagnostics/__init__.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/diagnostics/facade.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/diagnostics/open_policy.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/diagnostics/policy.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/diagnostics/state_summary.py` | targeted | partial | Reviewed bounded file/JSON/JSONL/text/optional-path summary symbols and directory scan bounds; no finding in reviewed symbols. |
| `src/mediapipeline/core/failures/__init__.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/failures/cleanup_service.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/failures/constants.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/failures/facade.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/failures/file_io.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/failures/markers.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/failures/policy.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/failures/retry_state.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/observability/__init__.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/observability/artifact_freshness.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/observability/logging.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/observability/runtime_outcomes.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/observability/status_files.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/observability/status_policy.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/__init__.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/active_jobs.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/status/contracts.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/errors.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/status/eta.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/events.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/facade.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/ffmpeg_progress.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/file_io.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/status/presentation.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/presentation_labels.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/presentation_lifecycle.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/presentation_progress.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/progress.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/readers.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/status/service.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/snapshot_runner.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/summary.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/status/summary_sections.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/storage/__init__.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/storage/constants.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/storage/contracts.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/storage/db.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/storage/state_migration.py` | all listed | reviewed | Reviewed: no findings. |
| `src/mediapipeline/core/telemetry/__init__.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/telemetry/gpu_usage.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/telemetry/health.py` | targeted | partial | Reviewed runtime state health, SQLite read-only health, API contract health, and bundle layout health rows; no finding in reviewed symbols. |
| `src/mediapipeline/core/telemetry/nvidia.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/telemetry/service.py` | 0 | pending | Not reviewed due time-box. |
| `src/mediapipeline/core/telemetry/system_metrics.py` | 0 | pending | Not reviewed due time-box. |

## Findings

| ID | Severity | File | Symbol | Problem | Suggested validation |
|---|---|---|---|---|---|
| W06-01 | Medium | `ops/pipeline/engine/storage/disk.ps1` | `Copy-FileRobocopy` | The helper creates the destination parent and later validates the destination against that same parent, so the helper-level guard does not enforce a configured scratch/output root and runs after an initial filesystem mutation. | Add a PowerShell unit test that calls the helper with a destination outside the allowed root and asserts no parent/staging directory is created and the copy is rejected. |
| W06-02 | Medium | `src/mediapipeline/contracts/api_commands.py` | `RenameApplyCommandPayload.confirm_apply`, `RenameApplyCommandPayload.allow_outside_configured_roots`, `FinalLibraryPromoteQueueCommandPayload.confirm_promote` | High-risk command confirmations are typed as `Any`, unlike other command contracts that use `StrictBool`, so route-level payload validation can accept string/int confirmation values and rely on later handlers to fail closed. | Add contract tests proving non-bool confirmation values are rejected for rename apply and final library promote; then type the fields as strict booleans where appropriate. |
| W06-03 | Medium | `ops/pipeline/engine/audit/probe.ps1` | `Clear-ProbeCache` | Probe cache cleanup recursively deletes every child of `$script:ProbeCacheRoot` without first proving the root is the intended probe-cache directory or within an allowed state/cache boundary. | Add a PowerShell test with a misconfigured probe cache root outside the expected cache directory and assert cleanup refuses to delete children. |
| W06-04 | Low | `ops/pipeline/engine/storage/scratch_copy.ps1` | `Remove-EmptyScratchContainer` | The helper deletes an empty parent whose leaf starts with `src_`, but it does not prove that parent is under `$script:processingDir`; current callers pass generated scratch paths, but the helper itself is unsafe for unexpected inputs. | Add a unit test for an empty external `src_*` directory and require the helper to leave it untouched. |
| W06-05 | Low | `src/mediapipeline/contracts/stages.py`; `src/mediapipeline/contracts/stage_mutation.py` | `StageName.ingest`, `IngestPayload` | The stage registry marks ingest as mutation-capable while `IngestPayload` uses only `intent: Literal["copy_to_scratch"]` and has no `MutationIntent`, dry-run mode, or execute confirmation contract. | Add stage-contract tests that mutation-capable stages expose dry-run/execute semantics or explicitly document and enforce why ingest is exempt before enabling it. |
| W06-06 | Low | `src/mediapipeline/contracts/source_media_models.py`; `src/mediapipeline/contracts/source_media_streams.py` | `SourceSubtitleStream.drop_candidate`, `subtitle_stream` | `drop_candidate` defaults to true and the subtitle stream builder never overrides it, so every normalized subtitle is simultaneously marked as a drop candidate even when it is also a passthrough, convert, or burn candidate. | Add source-media contract tests for text and image subtitles and set or remove `drop_candidate` to match the actual subtitle preservation policy. |

## Detailed Findings

### W06-01 - Medium - Copy helper mutates destination before an effective destination-root guard

- File: `ops/pipeline/engine/storage/disk.ps1`
- Symbol: `Copy-FileRobocopy`
- Problem: The helper creates `$dstDir` before checking destination safety, then calls `Test-MediaPipelinePathBoundarySafe -Path $Destination -Root $dstDir -AllowMissingLeaf`. Because the root is the destination parent, this verifies the destination is under its own parent rather than under an independently configured scratch/output root.
- Impact: If an upstream caller passes an unsafe or out-of-policy destination, this helper can create that directory and later create `.mediapipeline-staging` there. That weakens the source/scratch/output boundary that should fail before mutation.
- Evidence: Line 352 creates `$dstDir`; line 361 validates the destination with `-Root $dstDir`; line 369 creates `$stagingRoot`.
- Fix direction: Require an explicit allowed destination root, validate the destination against that root before any `CreateDirectory`, and only then create the destination parent and staging directory.
- Validation: PowerShell unit test for an unsafe destination outside the configured root, asserting rejection plus no created parent directory and no `.mediapipeline-staging`.

### W06-02 - Medium - High-risk command confirmation fields are not strict contract booleans

- File: `src/mediapipeline/contracts/api_commands.py`
- Symbol: `RenameApplyCommandPayload.confirm_apply`, `RenameApplyCommandPayload.allow_outside_configured_roots`, `FinalLibraryPromoteQueueCommandPayload.confirm_promote`
- Problem: Rename and final-library promote confirmation fields are typed as `Any`, unlike other high-risk command payloads that use strict boolean fields.
- Impact: Strict JSON route handling is a release-critical safety mechanism. These contracts allow route validation to accept `"true"`, `1`, or other non-bool values and rely on later command handlers to reject them, which creates contract drift at the API boundary.
- Evidence: Lines 187-211 define `RenameApplyCommandPayload` with `confirm_apply: Any = None` and `allow_outside_configured_roots: Any = None`; lines 361-362 define `FinalLibraryPromoteQueueCommandPayload.confirm_promote: Any = None`.
- Fix direction: Type confirmation and explicit boundary-override fields as strict booleans or a constrained strict model that preserves existing optional semantics.
- Validation: Contract tests should assert that non-bool values for rename apply and final-library promote are rejected by payload validation before command dispatch.

### W06-03 - Medium - Probe cache cleanup lacks a root boundary check

- File: `ops/pipeline/engine/audit/probe.ps1`
- Symbol: `Clear-ProbeCache`
- Problem: `Clear-ProbeCache` trusts `$script:ProbeCacheRoot` and pipes all children to recursive `Remove-Item` without verifying the root is the expected probe-cache location.
- Impact: A misconfigured probe-cache root can delete unrelated files under the configured directory. This is a destructive cleanup path in audit tooling and should fail closed when the cache root is outside the expected state/cache boundary.
- Evidence: Lines 86-90 check only that `$script:ProbeCacheRoot` is non-empty and exists, then recursively remove all children.
- Fix direction: Validate the cache root with the existing path boundary helper against the expected LocalBase/state cache root and optionally require the expected leaf name before deleting children.
- Validation: PowerShell unit test with `$script:ProbeCacheRoot` pointed at an external temp directory containing children; cleanup should refuse and leave files intact.

### W06-04 - Low - Empty scratch container cleanup lacks a processing-root containment check

- File: `ops/pipeline/engine/storage/scratch_copy.ps1`
- Symbol: `Remove-EmptyScratchContainer`
- Problem: The helper deletes the parent of a supplied scratch path when that parent leaf starts with `src_`, but it does not verify that the parent is equal to or under `$script:processingDir`.
- Impact: Current in-file callers pass scratch paths produced by `Get-ScratchInputPath`, so reachable risk appears limited. As a reusable helper, though, an unexpected path could remove an unrelated empty `src_*` directory outside the pipeline processing tree.
- Evidence: Lines 49-54 compute `$processingFull` and `$parentFull`, reject only equality with processing root and non-`src_` leaf names, then call `Remove-Item`.
- Fix direction: Require `Test-MediaPipelinePathIsEqualOrChild` or equivalent containment proof that the parent is under `$script:processingDir` before deleting it.
- Validation: Unit test an external empty `src_*` directory and assert it remains after calling the helper with a child path.

### W06-05 - Low - Ingest is mutation-capable but lacks dry-run/execute confirmation contract

- File: `src/mediapipeline/contracts/stages.py`; `src/mediapipeline/contracts/stage_mutation.py`
- Symbol: `StageName.ingest`, `IngestPayload`
- Problem: The registry marks ingest as `mutation_capable=True`, but `IngestPayload` has only `intent: Literal["copy_to_scratch"]`, not the shared `MutationIntent` pattern or execute confirmation fields used by other mutation-capable stages.
- Impact: If ingest is enabled in an entrypoint or invoked through the generic stage runner, the mutation contract does not expose the same dry-run/execute safety boundary as transcode, subtitle, audio, publish, drain, or rename stages.
- Evidence: `stages.py` lines 108-114 mark ingest mutation-capable; `stage_mutation.py` lines 12-15 define `IngestPayload` with source path, scratch root, and `copy_to_scratch` intent only.
- Fix direction: Either add dry-run/execute semantics and an execute confirmation to ingest, or explicitly encode an exemption that prevents generic mutation execution until the contract is extended.
- Validation: Stage contract tests should assert each mutation-capable stage supports dry-run and refuses execute without confirmation, or list ingest as a deliberately disabled exception.

### W06-06 - Low - Subtitle normalization marks every subtitle as a drop candidate

- File: `src/mediapipeline/contracts/source_media_models.py`; `src/mediapipeline/contracts/source_media_streams.py`
- Symbol: `SourceSubtitleStream.drop_candidate`, `subtitle_stream`
- Problem: `SourceSubtitleStream.drop_candidate` defaults to true and `subtitle_stream` never sets it, even when it sets passthrough, convert, or burn candidates.
- Impact: The normalized source-media contract can represent preserved subtitles as drop candidates. Current reviewed code did not show a downstream consumer in assigned files, so this is a contract correctness risk rather than an observed publish bug.
- Evidence: `source_media_models.py` line 127 sets `drop_candidate: bool = True`; `source_media_streams.py` lines 146-159 construct subtitle streams without overriding the field. A targeted search within `src/mediapipeline/contracts` found no other `drop_candidate` use.
- Fix direction: Define the intended policy: set `drop_candidate=False` when passthrough/convert/burn is true, or remove/rename the field if it is not part of the active decision contract.
- Validation: Contract tests for representative text and image subtitle codecs should assert the expected candidate flags.

## Test Coverage Gaps

- Review-only audit: no tests were run and no runtime/media state was mutated.
- Missing or needed tests identified during reviewed scope:
  - `Copy-FileRobocopy` destination-root rejection before any directory or staging creation.
  - API command contract rejection of non-bool rename/final-promote confirmation values.
  - `Clear-ProbeCache` refusal to delete children when cache root is outside the expected probe-cache boundary.
  - `Remove-EmptyScratchContainer` refusal to remove an external empty `src_*` directory.
  - Stage mutation contract coverage for ingest dry-run/execute semantics or a documented exemption.
  - Source-media subtitle candidate flag tests for text and image subtitle streams.

## Boundary Risks

- Destination copy boundary: `Copy-FileRobocopy` currently validates against the destination parent and does so after creating the parent.
- Audit cache cleanup boundary: `Clear-ProbeCache` performs recursive deletion under a script variable without an explicit allowed-root proof.
- Scratch cleanup boundary: `Remove-EmptyScratchContainer` relies on current caller shape and a `src_` leaf check rather than a processing-root containment check.
- Mutation stage boundary: ingest is modeled as mutation-capable without the shared dry-run/execute confirmation contract.
- Strict JSON command boundary: rename and final-library promote confirmations are not strict booleans at the contract layer.

## Files With No Findings

- `ops/pipeline/engine/audit/rerun_source_identity.ps1`
- `ops/pipeline/engine/observability/logging.ps1`
- `ops/pipeline/engine/paths/path_capability.ps1`
- `ops/pipeline/engine/shared/path_helpers.ps1`
- `ops/pipeline/engine/storage/state_store.ps1`
- `src/mediapipeline/contracts/config_coercion.py`
- `src/mediapipeline/contracts/config_defaults.py`
- `src/mediapipeline/contracts/config_schema_extras.py`
- `src/mediapipeline/contracts/config_validators.py`
- `src/mediapipeline/contracts/height_tolerance.py`
- `src/mediapipeline/contracts/pipeline_plan.py`
- `src/mediapipeline/contracts/runtime_evidence.py`
- `src/mediapipeline/contracts/source_media.py`
- `src/mediapipeline/contracts/source_media_adapters.py`
- `src/mediapipeline/contracts/source_media_derived.py`
- `src/mediapipeline/contracts/source_media_values.py`
- `src/mediapipeline/contracts/stage_base.py`
- `src/mediapipeline/contracts/stage_decide.py`
- `src/mediapipeline/contracts/stage_probe.py`
- `src/mediapipeline/contracts/verification.py`
- `src/mediapipeline/core/audit/rerun_file_io.py`
- `src/mediapipeline/core/diagnostics/open_policy.py`
- `src/mediapipeline/core/failures/cleanup_service.py`
- `src/mediapipeline/core/failures/facade.py`
- `src/mediapipeline/core/observability/status_files.py`
- `src/mediapipeline/core/status/active_jobs.py`
- `src/mediapipeline/core/status/errors.py`
- `src/mediapipeline/core/status/file_io.py`
- `src/mediapipeline/core/status/readers.py`
- `src/mediapipeline/core/storage/db.py`
- `src/mediapipeline/core/storage/state_migration.py`

## Incomplete Coverage

Coverage is partial because the user issued a time-box instruction to write this worker file immediately. Exact remaining coverage is:

- Fully unreviewed assigned files, all symbols unreviewed: `ops/pipeline/engine/audit/progress.ps1`, `ops/pipeline/engine/audit/scanner.ps1`, `ops/pipeline/engine/naming/destination_plan.ps1`, `ops/pipeline/engine/naming/movie_cleanup.ps1`, `ops/pipeline/engine/naming/naming.ps1`, `ops/pipeline/engine/naming/rename_overrides.ps1`, `ops/pipeline/engine/naming/tv_parsing.ps1`, `ops/pipeline/engine/paths/effective_settings.ps1`, `ops/pipeline/engine/paths/library_profiles.ps1`, `ops/pipeline/engine/paths/output_evidence.ps1`, `ops/pipeline/engine/paths/output_path_planning.ps1`, `ops/pipeline/engine/shared/executable_resolution.ps1`, `ops/pipeline/engine/shared/failure_codes.ps1`, `ops/pipeline/engine/shared/media_constants.ps1`, `ops/pipeline/engine/shared/native.ps1`, `ops/pipeline/engine/shared/native_process_contracts.ps1`, `ops/pipeline/engine/shared/source_identity.ps1`, `ops/pipeline/engine/shared/temp_cleanup.ps1`, `ops/pipeline/engine/shared/versioning.ps1`, `src/mediapipeline/contracts/__init__.py`, `src/mediapipeline/contracts/decision_policy.py`, `src/mediapipeline/contracts/lifecycle.py`, `src/mediapipeline/contracts/schemas/stages.v1.schema.json`, `src/mediapipeline/core/audit/__init__.py`, `src/mediapipeline/core/audit/facade.py`, `src/mediapipeline/core/audit/ignore_manifest.py`, `src/mediapipeline/core/audit/preview_policy.py`, `src/mediapipeline/core/audit/rerun_contracts.py`, `src/mediapipeline/core/audit/rerun_csv.py`, `src/mediapipeline/core/audit/rerun_export.py`, `src/mediapipeline/core/audit/rerun_io.py`, `src/mediapipeline/core/audit/rerun_metadata.py`, `src/mediapipeline/core/audit/rerun_records.py`, `src/mediapipeline/core/audit/rerun_service.py`, `src/mediapipeline/core/audit/score_policy.py`, `src/mediapipeline/core/diagnostics/__init__.py`, `src/mediapipeline/core/diagnostics/facade.py`, `src/mediapipeline/core/diagnostics/policy.py`, `src/mediapipeline/core/failures/__init__.py`, `src/mediapipeline/core/failures/constants.py`, `src/mediapipeline/core/failures/file_io.py`, `src/mediapipeline/core/failures/markers.py`, `src/mediapipeline/core/failures/policy.py`, `src/mediapipeline/core/failures/retry_state.py`, `src/mediapipeline/core/observability/__init__.py`, `src/mediapipeline/core/observability/artifact_freshness.py`, `src/mediapipeline/core/observability/logging.py`, `src/mediapipeline/core/observability/runtime_outcomes.py`, `src/mediapipeline/core/observability/status_policy.py`, `src/mediapipeline/core/status/__init__.py`, `src/mediapipeline/core/status/contracts.py`, `src/mediapipeline/core/status/eta.py`, `src/mediapipeline/core/status/events.py`, `src/mediapipeline/core/status/facade.py`, `src/mediapipeline/core/status/ffmpeg_progress.py`, `src/mediapipeline/core/status/presentation.py`, `src/mediapipeline/core/status/presentation_labels.py`, `src/mediapipeline/core/status/presentation_lifecycle.py`, `src/mediapipeline/core/status/presentation_progress.py`, `src/mediapipeline/core/status/progress.py`, `src/mediapipeline/core/status/service.py`, `src/mediapipeline/core/status/snapshot_runner.py`, `src/mediapipeline/core/status/summary.py`, `src/mediapipeline/core/status/summary_sections.py`, `src/mediapipeline/core/storage/__init__.py`, `src/mediapipeline/core/storage/constants.py`, `src/mediapipeline/core/storage/contracts.py`, `src/mediapipeline/core/telemetry/__init__.py`, `src/mediapipeline/core/telemetry/gpu_usage.py`, `src/mediapipeline/core/telemetry/nvidia.py`, `src/mediapipeline/core/telemetry/service.py`, `src/mediapipeline/core/telemetry/system_metrics.py`.
- Partially reviewed assigned files and unreviewed symbol groups: `ops/pipeline/engine/audit/policy.ps1` beyond policy normalization/import-ignore persistence; `ops/pipeline/engine/audit/reports.ps1` beyond `Export-CsvAtomic` and `Write-AuditReportBundle`; `ops/pipeline/engine/failures/failure_state.ps1` beyond failure JSON atomic write, marker index, clear failure state, and scratch artifact move paths; `src/mediapipeline/contracts/api_commands.py` beyond high-risk command confirmation payloads; `src/mediapipeline/contracts/config.py` beyond reviewed schema fields and cross-field validators; `src/mediapipeline/core/diagnostics/state_summary.py` beyond bounded file/JSON/JSONL/text/optional-path and directory summary symbols; `src/mediapipeline/core/telemetry/health.py` beyond runtime state, SQLite read-only, API contract, and bundle layout health rows.
