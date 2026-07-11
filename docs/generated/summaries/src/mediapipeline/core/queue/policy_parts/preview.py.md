---
file: src/mediapipeline/core/queue/policy_parts/preview.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 1a2bffb24df267a980e03ef4d980ecf8380549358bcea3267559c1287131c1ed
---
# `src/mediapipeline/core/queue/policy_parts/preview.py`

**Purpose:** Queue preview metadata, excluded-row shaping, and progress policy.

**Public functions:** `queue_completed_collision_fields()`, `queue_excluded_row_key()`, `queue_preview_excluded_rows()`, `queue_preview_metadata()`, `queue_row_has_visible_priority()`, `queue_source_scan_progress_payload()`
**In-repo imports:** `mediapipeline.core.observability.artifact_freshness`, `mediapipeline.core.observability.status_policy`, `mediapipeline.core.queue.policy_parts.metrics`, `mediapipeline.core.queue.policy_parts.rows`, `mediapipeline.core.queue.policy_parts.rules`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/queue/policy_parts/preview.py`._
