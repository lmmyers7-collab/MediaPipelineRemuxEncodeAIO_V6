---
file: app/queue/policy_parts/rows.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: unknown
last_modified: 2026-05-30
last_reviewed: 2026-05-30
sha256: e489f25a3dfe7ce68a811d88ce855f6b4303c3d832faa327b91b6e66536c3eab
---
# `app/queue/policy_parts/rows.py`

**Purpose:** Queue row shaping, route evidence, and operator-state policy.

**Public functions:** `queue_apply_runtime_outcomes()`, `queue_preview_rows()`, `queue_preview_warnings()`, `queue_record_to_row()`, `queue_row_available_open_targets()`, `queue_row_key()`, `queue_row_operator_guidance()`, `queue_row_operator_status_state()`, `queue_row_route_decision_summary()`, `queue_row_route_evidence_lines()`, `queue_row_trust_fields()`
**In-repo imports:** `app.observability.runtime_outcomes`, `app.queue.policy_parts.rules`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/queue/policy_parts/rows.py`._
