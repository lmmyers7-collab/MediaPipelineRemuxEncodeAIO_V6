---
file: src/mediapipeline/core/status/run_monitor.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: observability
last_modified: 2026-07-19
last_reviewed: 2026-07-16
sha256: e6a765935d9ad36ed7f8a1ca120d3b0339fbb4167a7508178bec4769bf095c36
---
# `src/mediapipeline/core/status/run_monitor.py`

**Purpose:** Single current-work freshness policy and WebView-facing Run Monitor projection.

**Public symbols:** `backend_activity_state_for_run`, `project_run_monitor`, `read_backend_correlated_run_monitor_projection`, `read_run_monitor_projection`, `seed_starting_run_monitor`, `terminalize_force_stopped_run`, `terminalize_launch_failed_run`, `unavailable_run_monitor_projection`
**In-repo imports:** `mediapipeline.contracts.run_monitor`, `mediapipeline.core.kernel.contracts`, `mediapipeline.core.status.active_jobs`, `mediapipeline.core.status.run_monitor_storage`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/status/run_monitor.py`._
