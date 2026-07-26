---
file: src/mediapipeline/core/processes/rerun_results_queue_projection.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: orchestration
token_priority: medium
owner_domain: process
last_modified: 2026-07-23
last_reviewed: 2026-07-11
sha256: 397bb43fdd6c26033612ed3873b4b4290960eeb07f7d7538c61736391871951e
---
# `src/mediapipeline/core/processes/rerun_results_queue_projection.py`

**Purpose:** Backend-owned CSV rerun result scanning, open, and promote helpers.

**Public symbols:** `rerun_manifest_queue_rows`, `rerun_results_payload`
**In-repo imports:** `mediapipeline.core.final_library.promotion_parts.planning`, `mediapipeline.core.final_library.promotion_parts.transfer`, `mediapipeline.core.kernel.contracts`, `mediapipeline.core.kernel.contracts.pending_publish`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.network.facade_connectivity`, `mediapipeline.core.network.registry`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.active_jobs`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_control`, `mediapipeline.core.processes.rerun_lifecycle`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.processes.rerun_results_network_projection`, `mediapipeline.core.processes.rerun_results_support`, `mediapipeline.core.processes.rerun_rules`, `mediapipeline.core.rerun.evidence`
**HTTP routes:** `/api/rerun/continue`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_results_queue_projection.py`._
