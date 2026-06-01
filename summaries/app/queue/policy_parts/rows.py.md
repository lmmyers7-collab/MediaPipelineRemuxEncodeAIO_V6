---
file: app/queue/policy_parts/rows.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: unknown
last_modified: 2026-05-31
last_reviewed: 2026-05-30
sha256: f71f12e1615bd4b8191dd15302e7e9a30187e3aacb25d8d07a357995d476d7de
---
# `app/queue/policy_parts/rows.py`

**Purpose:** Queue row shaping, route evidence, and operator-state policy.

**Public functions:** `queue_apply_runtime_outcomes()`, `queue_preview_library_promotion_fields()`, `queue_preview_rows()`, `queue_preview_runtime_evidence_fields()`, `queue_preview_track_metadata_summary()`, `queue_preview_warnings()`, `queue_record_to_row()`, `queue_row_available_open_targets()`, `queue_row_key()`, `queue_row_operator_guidance()`, `queue_row_operator_status_state()`, `queue_row_route_decision_summary()`, `queue_row_route_evidence_lines()`, `queue_row_trust_fields()`
**In-repo imports:** `app.observability.runtime_outcomes`, `app.queue.file_overrides`, `app.queue.policy_parts.rules`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/queue/policy_parts/rows.py`._
