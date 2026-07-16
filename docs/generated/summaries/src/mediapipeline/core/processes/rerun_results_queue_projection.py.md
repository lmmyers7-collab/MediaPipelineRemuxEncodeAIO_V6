---
file: src/mediapipeline/core/processes/rerun_results_queue_projection.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: process
last_modified: 2026-07-16
last_reviewed: 2026-07-11
sha256: 3701ffe7ae6b2ff474f1b93b99d44a0f38e11ef858964215f53b3c92cc799108
---
# `src/mediapipeline/core/processes/rerun_results_queue_projection.py`

**Purpose:** Backend-owned CSV rerun result scanning, open, and promote helpers.

**Public functions:** `rerun_manifest_queue_rows()`, `rerun_results_payload()`
**In-repo imports:** `mediapipeline.core.final_library.promotion_parts.planning`, `mediapipeline.core.final_library.promotion_parts.transfer`, `mediapipeline.core.kernel.contracts`, `mediapipeline.core.kernel.contracts.pending_publish`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.network.facade_connectivity`, `mediapipeline.core.network.registry`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.active_jobs`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_control`, `mediapipeline.core.processes.rerun_lifecycle`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.processes.rerun_results_support`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_results_queue_projection.py`._
