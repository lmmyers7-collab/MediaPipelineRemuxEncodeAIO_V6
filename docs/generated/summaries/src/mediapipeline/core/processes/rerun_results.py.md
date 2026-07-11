---
file: src/mediapipeline/core/processes/rerun_results.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-10
last_reviewed: 2026-06-30
sha256: 6f05b2cc8a89c750ba13e1c8cddb0c14377dda103c61c4f93d119bae29adc79b
---
# `src/mediapipeline/core/processes/rerun_results.py`

**Purpose:** Backend-owned CSV rerun result scanning, open, and promote helpers.

**Public functions:** `apply_network_rerun_destination_policy()`, `rerun_manifest_queue_rows()`, `rerun_open_backend_known_path()`, `rerun_promote_dry_run()`, `rerun_promote_to_pending_publish()`, `rerun_results_payload()`
**In-repo imports:** `mediapipeline.core.final_library.promotion_parts.planning`, `mediapipeline.core.final_library.promotion_parts.transfer`, `mediapipeline.core.kernel.contracts.pending_publish`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.processes.rerun_rules`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_results.py`._
