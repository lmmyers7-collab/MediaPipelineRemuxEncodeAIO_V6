---
file: app/processes/active_jobs.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: 26241f80e33a3a71e0892d91f51768f5e9c3cff357357fbe0eb43a92df4e780f
---
# `app/processes/active_jobs.py`

**Purpose:** (no module docstring)

**Classes:** `InfoWarningLogger`, `WarningLogger`
**Public functions:** `active_job_close_block_messages()`, `active_job_pid_is_alive()`, `active_job_pid_matches_record()`, `active_job_record_path_for_proc()`, `active_jobs_dir_for_resolved()`, `reconcile_active_job_records()`, `update_active_job_record()`, `write_active_job_launch_record()`, `write_active_job_payload()`
**In-repo imports:** `app.processes.constants`, `app.processes.file_io`, `mediapipeline_desktop_app.contracts`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/processes/active_jobs.py`._
