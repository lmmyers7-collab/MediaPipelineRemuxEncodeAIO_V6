---
file: app/queue/policy_parts/preview.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-06-02
last_reviewed: 2026-05-30
sha256: 5cac441350176aa2e2bf1bfd09ba70a041c4441ab87c4272afb572d9b053719d
---
# `app/queue/policy_parts/preview.py`

**Purpose:** Queue preview metadata, excluded-row shaping, and progress policy.

**Public functions:** `queue_completed_collision_fields()`, `queue_excluded_row_key()`, `queue_preview_excluded_rows()`, `queue_preview_metadata()`, `queue_row_has_visible_priority()`, `queue_source_scan_progress_payload()`
**In-repo imports:** `app.observability.artifact_freshness`, `app.observability.status_policy`, `app.queue.policy_parts.metrics`, `app.queue.policy_parts.rows`, `app.queue.policy_parts.rules`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/queue/policy_parts/preview.py`._
