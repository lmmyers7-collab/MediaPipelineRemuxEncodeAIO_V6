---
file: src/mediapipeline/core/completed/policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: completed
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: d8aec0fed811e157506c2be69e5b3c889d7c819cfa0ce3781683b036e4484f5c
---
# `src/mediapipeline/core/completed/policy.py`

**Purpose:** Completed-job preview DTO policy.

**Public functions:** `bounded_completed_limit()`, `completed_apply_runtime_outcomes()`, `completed_audio_decision_preview()`, `completed_decision_value()`, `completed_history_read_error_result()`, `completed_history_service_unavailable_result()`, `completed_inventory_progress_payload()`, `completed_path_exists()`, `completed_path_mtime()`, `completed_preview_fields()`, `completed_preview_from_records()`, `completed_preview_limit()`, `completed_preview_rows()`, `completed_record_key()`, `completed_record_to_row()`, `completed_row_available_open_targets()`, `completed_row_consistency()`, `completed_row_operator_guidance()`, `completed_row_operator_status_state()`, `completed_row_route_decision_summary()`
**In-repo imports:** `mediapipeline.core.completed.manifest`, `mediapipeline.core.completed.trust_fields`, `mediapipeline.core.completed.validation_state`, `mediapipeline.core.observability.artifact_freshness`, `mediapipeline.core.observability.runtime_outcomes`, `mediapipeline.desktop.models`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/completed/policy.py`._
