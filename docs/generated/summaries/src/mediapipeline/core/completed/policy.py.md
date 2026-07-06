---
file: src/mediapipeline/core/completed/policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: completed
last_modified: 2026-07-05
last_reviewed: 2026-06-04
sha256: f2f245aec7af10e14f86073ee12dd59af282ebae2d3baf6aee117cd1b9cc54c0
---
# `src/mediapipeline/core/completed/policy.py`

**Purpose:** Completed-job preview DTO policy.

**Public functions:** `bounded_completed_limit()`, `completed_apply_runtime_outcomes()`, `completed_audio_decision_preview()`, `completed_bitrate_display()`, `completed_bitrate_fields()`, `completed_decision_detail_rows()`, `completed_decision_value()`, `completed_history_read_error_result()`, `completed_history_service_unavailable_result()`, `completed_inventory_progress_payload()`, `completed_path_exists()`, `completed_path_mtime()`, `completed_pending_publish_row()`, `completed_pending_publish_rows()`, `completed_preview_fields()`, `completed_preview_from_records()`, `completed_preview_limit()`, `completed_preview_rows()`, `completed_quality_fields()`, `completed_quality_number_label()`
**In-repo imports:** `mediapipeline.core.completed.contracts`, `mediapipeline.core.completed.manifest`, `mediapipeline.core.completed.trust_fields`, `mediapipeline.core.completed.validation_state`, `mediapipeline.core.files.constants`, `mediapipeline.core.observability.artifact_freshness`, `mediapipeline.core.observability.runtime_outcomes`, `mediapipeline.core.subtitles.qa`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/completed/policy.py`._
