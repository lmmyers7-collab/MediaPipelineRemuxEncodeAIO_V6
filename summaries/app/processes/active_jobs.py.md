---
file: app/processes/active_jobs.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: ae443c6b777602de4382c44da9df16d36d78036d36595291e29304e55db29893
---
# `app/processes/active_jobs.py`

**Purpose:** (no module docstring)

**Classes:** `InfoWarningLogger`, `WarningLogger`, `_NullWarningLogger`
**Public functions:** `active_job_close_block_messages()`, `active_job_pid_is_alive()`, `active_job_pid_matches_record()`, `active_job_record_path_for_proc()`, `active_jobs_dir_for_resolved()`, `cleanup_stale_validate_active_jobs()`, `reconcile_active_job_records()`, `update_active_job_record()`, `write_active_job_launch_record()`, `write_active_job_payload()`
**In-repo imports:** `app.processes.constants`, `app.processes.file_io`, `app.processes.kill`, `mediapipeline_desktop_app.contracts`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/processes/active_jobs.py`._
