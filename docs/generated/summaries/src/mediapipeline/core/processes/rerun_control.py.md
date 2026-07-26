---
file: src/mediapipeline/core/processes/rerun_control.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-15
last_reviewed: 2026-07-03
sha256: 87d729965c8a60c97d1f2b50c1e29811fe4e6705de3856f93398ac89352d7e9c
---
# `src/mediapipeline/core/processes/rerun_control.py`

**Purpose:** Backend-owned cooperative control helpers for CSV reruns.

**Public symbols:** `build_rerun_continue_pending_request`, `request_rerun_stop_after_current`, `rerun_control_root`, `rerun_pending_recovery_posture`, `rerun_retry_exhausted_recovery_posture`, `rerun_stop_marker_path`, `rerun_waiting_restart_posture`
**In-repo imports:** `mediapipeline.core.kernel.contracts`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.active_jobs`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_lifecycle`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.rerun.evidence`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_control.py`._
