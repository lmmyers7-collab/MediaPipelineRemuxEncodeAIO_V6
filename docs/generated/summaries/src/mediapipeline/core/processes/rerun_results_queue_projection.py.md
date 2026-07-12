---
file: src/mediapipeline/core/processes/rerun_results_queue_projection.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: process
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: e7e16479a6d685ec0c8b951644ba9c179444ae0c60609836c335fe5d451617d9
---
# `src/mediapipeline/core/processes/rerun_results_queue_projection.py`

**Purpose:** Backend-owned CSV rerun result scanning, open, and promote helpers.

**Public functions:** `rerun_manifest_queue_rows()`, `rerun_results_payload()`
**In-repo imports:** `mediapipeline.core.final_library.promotion_parts.planning`, `mediapipeline.core.final_library.promotion_parts.transfer`, `mediapipeline.core.kernel.contracts.pending_publish`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.processes.rerun_results_support`, `mediapipeline.core.processes.rerun_rules`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_results_queue_projection.py`._
