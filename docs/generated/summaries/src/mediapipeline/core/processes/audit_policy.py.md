---
file: src/mediapipeline/core/processes/audit_policy.py
pipeline_stage: observability
token_priority: medium
owner_domain: process
last_modified: 2026-06-28
last_reviewed: 2026-06-04
sha256: 73d3671ed5a9d311cfd6119e3fd4d266a8d19e8d0dd2e8e4f56ace9b51db5a8d
---
# `src/mediapipeline/core/processes/audit_policy.py`

**Purpose:** Audit launch policy helpers for process routes.

**Public functions:** `audit_missing_library_root_result()`, `audit_start_active_work_result()`, `audit_start_config_blocked_result()`, `audit_start_exception_result()`, `audit_start_success_data()`, `audit_start_success_message()`, `audit_start_success_result()`, `audit_stop_active_work_result()`, `audit_stop_confirm_required_result()`, `audit_stop_exception_result()`, `audit_stop_success_result()`, `resolve_audit_library_root()`, `resolve_audit_library_roots()`
**In-repo imports:** `mediapipeline.core.kernel.config_keys`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/audit_policy.py`._
