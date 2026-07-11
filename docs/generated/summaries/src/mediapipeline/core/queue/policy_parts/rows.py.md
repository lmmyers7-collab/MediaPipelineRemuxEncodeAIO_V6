---
file: src/mediapipeline/core/queue/policy_parts/rows.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 656abfdb22e85fb45dec7c5de8c8e1f767d6794b7731970bc14ad8f548cd7d3e
---
# `src/mediapipeline/core/queue/policy_parts/rows.py`

**Purpose:** Queue row shaping, route evidence, and operator-state policy.

**Public functions:** `queue_preview_library_promotion_fields()`, `queue_preview_rows()`, `queue_preview_runtime_evidence_fields()`, `queue_preview_warnings()`, `queue_record_to_row()`
**In-repo imports:** `mediapipeline.core.queue.contracts`, `mediapipeline.core.queue.policy_parts.file_override_rows`, `mediapipeline.core.queue.policy_parts.operator_guidance`, `mediapipeline.core.queue.policy_parts.route_evidence`, `mediapipeline.core.queue.policy_parts.row_identity`, `mediapipeline.core.queue.policy_parts.rules`, `mediapipeline.core.queue.policy_parts.runtime_outcomes`, `mediapipeline.core.queue.policy_parts.track_metadata`, `mediapipeline.core.subtitles.qa`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/queue/policy_parts/rows.py`._
