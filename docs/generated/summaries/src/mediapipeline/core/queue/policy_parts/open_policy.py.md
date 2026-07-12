---
file: src/mediapipeline/core/queue/policy_parts/open_policy.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-12
last_reviewed: 2026-06-04
sha256: 6d28778e56f702eae9379b35e8708f8879f26fc27d7e999694c025d73868e1c2
---
# `src/mediapipeline/core/queue/policy_parts/open_policy.py`

**Purpose:** Queue source-open validation and command-result policy.

**Public functions:** `allowed_queue_open_scopes_text()`, `allowed_queue_open_targets_text()`, `normalize_queue_open_scope()`, `normalize_queue_open_target()`, `queue_open_disallowed_scope_result()`, `queue_open_disallowed_target_result()`, `queue_open_exception_result()`, `queue_open_path()`, `queue_open_path_missing_result()`, `queue_open_path_service_unavailable_result()`, `queue_open_requires_row_result()`, `queue_open_result_data()`, `queue_open_row_missing_result()`, `queue_open_scope_label()`, `queue_open_success_result()`, `queue_open_target_label()`
**In-repo imports:** `mediapipeline.core.queue.policy_parts.rules`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/queue/policy_parts/open_policy.py`._
