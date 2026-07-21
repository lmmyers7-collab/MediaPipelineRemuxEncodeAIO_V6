---
file: src/mediapipeline/core/status/run_monitor.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: observability
last_modified: 2026-07-20
last_reviewed: 2026-07-16
sha256: 712a7a983cac00cc8ff0037855e57e848dd151532f5f0077d53ab9bfc63a747a
---
# `src/mediapipeline/core/status/run_monitor.py`

**Purpose:** Single current-work freshness policy and WebView-facing Run Monitor projection.

**Public symbols:** `backend_activity_state_for_run`, `project_run_monitor`, `read_backend_correlated_run_monitor_projection`, `read_run_monitor_projection`, `seed_starting_run_monitor`, `terminalize_force_stopped_run`, `terminalize_launch_failed_run`, `unavailable_run_monitor_projection`
**In-repo imports:** `mediapipeline.contracts.run_monitor`, `mediapipeline.core.kernel.contracts`, `mediapipeline.core.status.active_jobs`, `mediapipeline.core.status.run_monitor_storage`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/status/run_monitor.py`._
