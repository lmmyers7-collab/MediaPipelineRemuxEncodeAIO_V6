---
file: app/queue/policy.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: unknown
last_modified: 2026-05-28
last_reviewed: 2026-05-28
sha256: 895253a292cfb7c8b832f42505f39d498e17b4030d28d2effb4e3229da1b01c4
---
# `app/queue/policy.py`

**Purpose:** Queue preview and source-open policy.

**Public functions:** `allowed_queue_open_scopes_text()`, `allowed_queue_open_targets_text()`, `format_queue_size_gb()`, `normalize_queue_open_scope()`, `normalize_queue_open_target()`, `queue_apply_runtime_outcomes()`, `queue_completed_collision_fields()`, `queue_count_by_key()`, `queue_count_list_values()`, `queue_counts_text()`, `queue_excluded_row_key()`, `queue_media_type_label()`, `queue_open_disallowed_scope_result()`, `queue_open_disallowed_target_result()`, `queue_open_exception_result()`, `queue_open_path()`, `queue_open_path_missing_result()`, `queue_open_path_service_unavailable_result()`, `queue_open_requires_row_result()`, `queue_open_result_data()`
**In-repo imports:** `app.observability.artifact_freshness`, `app.observability.runtime_outcomes`, `app.observability.status_policy`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/queue/policy.py`._
