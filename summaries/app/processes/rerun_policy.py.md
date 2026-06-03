---
file: app/processes/rerun_policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: f7ca408b237a3b5a494622b8f279983b977d8df304328d03f3921207c0c556d3
---
# `app/processes/rerun_policy.py`

**Purpose:** CSV rerun launch request and result policy helpers.

**Public functions:** `normalize_rerun_csv_path()`, `normalize_rerun_mode()`, `rerun_csv_path_from_request()`, `rerun_csv_path_missing_result()`, `rerun_mode_error_result()`, `rerun_modes_are_supported()`, `rerun_modes_from_request()`, `rerun_run_label()`, `rerun_start_active_work_result()`, `rerun_start_config_blocked_result()`, `rerun_start_exception_result()`, `rerun_start_success_data()`, `rerun_start_success_message()`, `rerun_start_success_result()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/processes/rerun_policy.py`._
