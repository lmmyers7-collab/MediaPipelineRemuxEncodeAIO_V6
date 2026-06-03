---
file: app/processes/active_job_runner.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: a6004f62a7bf21f6fda226f0acce6b08d785e700dbb07f39a1a14e11c4e6cf93
---
# `app/processes/active_job_runner.py`

**Purpose:** (no module docstring)

**Classes:** `ActiveJobLaunchRecordService`, `ActiveJobLoggedService`, `InfoWarningLogger`
**Public functions:** `active_job_close_block_messages_for_service()`, `active_job_pid_is_alive_for_service()`, `active_job_record_path_for_proc_for_service()`, `active_jobs_dir_for_service()`, `cleanup_stale_launch_guards_for_service()`, `reconcile_active_job_records_for_service()`, `update_active_job_record_for_service()`, `write_active_job_launch_record_for_service()`, `write_active_job_payload_for_service()`
**In-repo imports:** `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/processes/active_job_runner.py`._
