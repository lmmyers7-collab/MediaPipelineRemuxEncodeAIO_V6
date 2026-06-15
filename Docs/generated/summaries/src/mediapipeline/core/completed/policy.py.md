---
file: src/mediapipeline/core/completed/policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: completed
last_modified: 2026-06-11
last_reviewed: 2026-06-04
sha256: b90d1b7313f6c44263542c3dc63d1fea96b5ee95049a8efbe886f63c32009541
---
# `src/mediapipeline/core/completed/policy.py`

**Purpose:** Completed-job preview DTO policy.

**Public functions:** `bounded_completed_limit()`, `completed_apply_runtime_outcomes()`, `completed_audio_decision_preview()`, `completed_bitrate_display()`, `completed_bitrate_fields()`, `completed_decision_value()`, `completed_history_read_error_result()`, `completed_history_service_unavailable_result()`, `completed_inventory_progress_payload()`, `completed_path_exists()`, `completed_path_mtime()`, `completed_preview_fields()`, `completed_preview_from_records()`, `completed_preview_limit()`, `completed_preview_rows()`, `completed_quality_fields()`, `completed_quality_number_label()`, `completed_record_key()`, `completed_record_to_row()`, `completed_row_available_open_targets()`
**In-repo imports:** `mediapipeline.core.completed.manifest`, `mediapipeline.core.completed.trust_fields`, `mediapipeline.core.completed.validation_state`, `mediapipeline.core.files.constants`, `mediapipeline.core.observability.artifact_freshness`, `mediapipeline.core.observability.runtime_outcomes`, `mediapipeline.core.subtitles.qa`, `mediapipeline.desktop.models`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/completed/policy.py`._
