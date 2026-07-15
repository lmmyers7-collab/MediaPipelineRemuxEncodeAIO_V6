---
file: src/mediapipeline/core/processes/active_jobs.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-14
last_reviewed: 2026-06-04
sha256: 08f486e1d4e37a1f0c4844d66ce8d909cc16e62350e6f01713cd7dd799faeb3f
---
# `src/mediapipeline/core/processes/active_jobs.py`

**Purpose:** (no module docstring)

**Classes:** `InfoWarningLogger`, `WarningLogger`, `_NullWarningLogger`
**Public functions:** `active_job_pid_is_alive()`, `active_job_pid_matches_record()`, `active_job_record_path_for_proc()`, `active_jobs_dir_for_resolved()`, `cleanup_stale_validate_active_jobs()`, `reconcile_active_job_records()`, `update_active_job_record()`, `write_active_job_launch_record()`, `write_active_job_payload()`
**In-repo imports:** `mediapipeline.core.kernel.contracts`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.constants`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.kill`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/active_jobs.py`._
