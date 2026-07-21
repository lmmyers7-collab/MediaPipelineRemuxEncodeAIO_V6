---
file: src/mediapipeline/core/queue/policy_parts/preview.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 1ce6094be462503847ca760f0ef0fc386412e6d6284ce9047eb0000fb095b0c1
---
# `src/mediapipeline/core/queue/policy_parts/preview.py`

**Purpose:** Queue preview metadata, excluded-row shaping, and progress policy.

**Public symbols:** `queue_completed_collision_fields`, `queue_excluded_row_key`, `queue_preview_excluded_rows`, `queue_preview_metadata`, `queue_row_has_visible_priority`, `queue_source_scan_progress_payload`
**In-repo imports:** `mediapipeline.core.observability.artifact_freshness`, `mediapipeline.core.observability.status_policy`, `mediapipeline.core.queue.policy_parts.metrics`, `mediapipeline.core.queue.policy_parts.rows`, `mediapipeline.core.queue.policy_parts.rules`
**State/config identifiers:** `queue_snapshot.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/queue/policy_parts/preview.py`._
