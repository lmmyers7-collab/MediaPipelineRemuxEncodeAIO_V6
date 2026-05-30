---
file: app/queue/policy_parts/preview.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: unknown
last_modified: 2026-05-30
last_reviewed: 2026-05-30
sha256: fd0ffd4b2924bc06d26fb9ecc1f1efbfbcd208ca6f388aa6e5bd513f054788bb
---
# `app/queue/policy_parts/preview.py`

**Purpose:** Queue preview metadata, excluded-row shaping, and progress policy.

**Public functions:** `queue_completed_collision_fields()`, `queue_excluded_row_key()`, `queue_preview_excluded_rows()`, `queue_preview_metadata()`, `queue_source_scan_progress_payload()`
**In-repo imports:** `app.observability.artifact_freshness`, `app.observability.status_policy`, `app.queue.policy_parts.metrics`, `app.queue.policy_parts.rows`, `app.queue.policy_parts.rules`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/queue/policy_parts/preview.py`._
