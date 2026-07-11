---
file: src/mediapipeline/core/completed/policy_orchestration.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: completed
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 2bfde9429ee80b6e4f272cf9ac7409e913f6cc206ba1aed2a9c05866c3073c7a
---
# `src/mediapipeline/core/completed/policy_orchestration.py`

**Purpose:** Completed-job preview DTO policy.

**Public functions:** `completed_apply_runtime_outcomes()`, `completed_history_read_error_result()`, `completed_history_service_unavailable_result()`, `completed_pending_publish_row()`, `completed_pending_publish_rows()`, `completed_preview_fields()`, `completed_preview_from_records()`, `completed_preview_rows()`, `completed_record_to_row()`
**In-repo imports:** `mediapipeline.core.completed.contracts`, `mediapipeline.core.completed.manifest`, `mediapipeline.core.completed.policy_evidence`, `mediapipeline.core.completed.policy_guidance`, `mediapipeline.core.completed.policy_projection`, `mediapipeline.core.completed.policy_quality`, `mediapipeline.core.completed.trust_fields`, `mediapipeline.core.completed.validation_state`, `mediapipeline.core.files.constants`, `mediapipeline.core.observability.artifact_freshness`, `mediapipeline.core.observability.runtime_outcomes`, `mediapipeline.core.subtitles.qa`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/completed/policy_orchestration.py`._
