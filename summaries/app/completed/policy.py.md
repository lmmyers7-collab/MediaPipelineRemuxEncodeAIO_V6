---
file: app/completed/policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: completed
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: 4f4544e01da713d0533b66a10946b99386116ad8cff8802f5ec2d0719212fe97
---
# `app/completed/policy.py`

**Purpose:** Completed-job preview DTO policy.

**Public functions:** `bounded_completed_limit()`, `completed_apply_runtime_outcomes()`, `completed_audio_decision_preview()`, `completed_decision_value()`, `completed_history_read_error_result()`, `completed_history_service_unavailable_result()`, `completed_inventory_progress_payload()`, `completed_path_exists()`, `completed_path_mtime()`, `completed_preview_fields()`, `completed_preview_from_records()`, `completed_preview_limit()`, `completed_preview_rows()`, `completed_record_key()`, `completed_record_to_row()`, `completed_row_available_open_targets()`, `completed_row_consistency()`, `completed_row_operator_guidance()`, `completed_row_operator_status_state()`, `completed_row_route_decision_summary()`
**In-repo imports:** `app.completed.trust_fields`, `app.completed.validation_state`, `app.observability.artifact_freshness`, `app.observability.runtime_outcomes`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/completed/policy.py`._
