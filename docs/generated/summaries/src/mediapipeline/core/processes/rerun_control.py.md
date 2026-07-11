---
file: src/mediapipeline/core/processes/rerun_control.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-10
last_reviewed: 2026-07-03
sha256: 4eb8c94221a606c08336a795f31abd6a6c455fb05929328d59d1da5530dbba78
---
# `src/mediapipeline/core/processes/rerun_control.py`

**Purpose:** Backend-owned cooperative control helpers for CSV reruns.

**Public functions:** `build_rerun_continue_pending_request()`, `request_rerun_stop_after_current()`, `rerun_control_root()`, `rerun_stop_marker_path()`
**In-repo imports:** `mediapipeline.core.kernel.contracts`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.active_jobs`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_preview`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_control.py`._
