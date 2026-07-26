---
file: src/mediapipeline/core/processes/active_job_runner.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-01
last_reviewed: 2026-06-04
sha256: 1b72f0e97b03b5907f1633053f65e9bb87261789912af7748e401fe4b4c7c27e
---
# `src/mediapipeline/core/processes/active_job_runner.py`

**Purpose:** Python implementation for active job runner; exposes active_job_pid_is_alive_for_service, active_job_record_path_for_proc_for_service, active_jobs_dir_for_service.

**Public symbols:** `active_job_pid_is_alive_for_service`, `active_job_record_path_for_proc_for_service`, `active_jobs_dir_for_service`, `ActiveJobLaunchRecordService`, `ActiveJobLoggedService`, `cleanup_stale_launch_guards_for_service`, `InfoWarningLogger`, `reconcile_active_job_records_for_service`, `update_active_job_record_for_service`, `write_active_job_launch_record_for_service`, `write_active_job_payload_for_service`
**In-repo imports:** `.active_jobs`, `mediapipeline.core.paths.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/active_job_runner.py`._
