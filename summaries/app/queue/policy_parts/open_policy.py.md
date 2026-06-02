---
file: app/queue/policy_parts/open_policy.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-05-30
last_reviewed: 2026-05-30
sha256: b5d384d58611ef2758d43207f4829110fbcc35ef30692307b588b6569fc86c9a
---
# `app/queue/policy_parts/open_policy.py`

**Purpose:** Queue source-open validation and command-result policy.

**Public functions:** `allowed_queue_open_scopes_text()`, `allowed_queue_open_targets_text()`, `normalize_queue_open_scope()`, `normalize_queue_open_target()`, `queue_open_disallowed_scope_result()`, `queue_open_disallowed_target_result()`, `queue_open_exception_result()`, `queue_open_path()`, `queue_open_path_missing_result()`, `queue_open_path_service_unavailable_result()`, `queue_open_requires_row_result()`, `queue_open_result_data()`, `queue_open_row_missing_result()`, `queue_open_scope_label()`, `queue_open_success_result()`, `queue_open_target_label()`
**In-repo imports:** `app.queue.policy_parts.rules`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/queue/policy_parts/open_policy.py`._
