---
file: src/mediapipeline/core/processes/rerun_control.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-10
last_reviewed: 2026-07-03
sha256: 69d78629f3bf21e693db14d3ce863677874b1de92fbfa247ad268316b6866347
---
# `src/mediapipeline/core/processes/rerun_control.py`

**Purpose:** Backend-owned cooperative control helpers for CSV reruns.

**Public functions:** `build_rerun_continue_pending_request()`, `request_rerun_stop_after_current()`, `rerun_control_root()`, `rerun_stop_marker_path()`
**In-repo imports:** `mediapipeline.core.kernel.contracts`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.active_jobs`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_preview`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_control.py`._
