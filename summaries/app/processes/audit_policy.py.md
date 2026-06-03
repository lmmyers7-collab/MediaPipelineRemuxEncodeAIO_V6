---
file: app/processes/audit_policy.py
pipeline_stage: observability
token_priority: medium
owner_domain: process
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: 556c1c42f57966bebbdcae9ca49b740e1ab3367a496c83959299db4117b2878f
---
# `app/processes/audit_policy.py`

**Purpose:** Audit launch policy helpers for process routes.

**Public functions:** `audit_missing_library_root_result()`, `audit_start_active_work_result()`, `audit_start_config_blocked_result()`, `audit_start_exception_result()`, `audit_start_success_data()`, `audit_start_success_message()`, `audit_start_success_result()`, `resolve_audit_library_root()`
**In-repo imports:** `mediapipeline_desktop_app.config_keys`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/processes/audit_policy.py`._
