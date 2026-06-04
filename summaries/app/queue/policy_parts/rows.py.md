---
file: app/queue/policy_parts/rows.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-06-03
last_reviewed: 2026-05-30
sha256: 3630a35a52838b9dd791c67bfb043dac4b8991b231012094fdcdf2924d0d36c0
---
# `app/queue/policy_parts/rows.py`

**Purpose:** Queue row shaping, route evidence, and operator-state policy.

**Public functions:** `queue_apply_runtime_outcomes()`, `queue_preview_library_promotion_fields()`, `queue_preview_rows()`, `queue_preview_runtime_evidence_fields()`, `queue_preview_track_metadata_summary()`, `queue_preview_warnings()`, `queue_record_to_row()`, `queue_row_available_open_targets()`, `queue_row_key()`, `queue_row_operator_guidance()`, `queue_row_operator_status_state()`, `queue_row_route_decision_summary()`, `queue_row_route_evidence_lines()`, `queue_row_trust_fields()`
**In-repo imports:** `app.observability.runtime_outcomes`, `app.queue.file_overrides`, `app.queue.policy_parts.rules`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/queue/policy_parts/rows.py`._
