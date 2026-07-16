---
file: src/mediapipeline/core/processes/rerun_results_queue_projection.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: process
last_modified: 2026-07-15
last_reviewed: 2026-07-11
sha256: 4e14b5ed97d1d011648c15476147ce57226ad0b67ab79c59eb2cdd23e39a93d7
---
# `src/mediapipeline/core/processes/rerun_results_queue_projection.py`

**Purpose:** Backend-owned CSV rerun result scanning, open, and promote helpers.

**Public functions:** `rerun_manifest_queue_rows()`, `rerun_results_payload()`
**In-repo imports:** `mediapipeline.core.final_library.promotion_parts.planning`, `mediapipeline.core.final_library.promotion_parts.transfer`, `mediapipeline.core.kernel.contracts`, `mediapipeline.core.kernel.contracts.pending_publish`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.active_jobs`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_control`, `mediapipeline.core.processes.rerun_lifecycle`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.processes.rerun_results_support`, `mediapipeline.core.processes.rerun_rules`, `mediapipeline.core.processes.source_probe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_results_queue_projection.py`._
