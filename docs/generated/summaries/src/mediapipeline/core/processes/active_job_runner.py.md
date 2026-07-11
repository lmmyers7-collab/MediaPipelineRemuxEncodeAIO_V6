---
file: src/mediapipeline/core/processes/active_job_runner.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 966e1e00eb1d8167e1eff97635919712f37647559d416ad71028aacd76009869
---
# `src/mediapipeline/core/processes/active_job_runner.py`

**Purpose:** (no module docstring)

**Classes:** `ActiveJobLaunchRecordService`, `ActiveJobLoggedService`, `InfoWarningLogger`
**Public functions:** `active_job_pid_is_alive_for_service()`, `active_job_record_path_for_proc_for_service()`, `active_jobs_dir_for_service()`, `cleanup_stale_launch_guards_for_service()`, `reconcile_active_job_records_for_service()`, `update_active_job_record_for_service()`, `write_active_job_launch_record_for_service()`, `write_active_job_payload_for_service()`
**In-repo imports:** `mediapipeline.core.paths.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/active_job_runner.py`._
