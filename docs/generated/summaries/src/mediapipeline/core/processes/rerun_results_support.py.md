---
file: src/mediapipeline/core/processes/rerun_results_support.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-15
last_reviewed: 2026-07-11
sha256: c82c4a4fa2652592ebdb0fc937ffddcead216baf6e24ed826a200052b4def44e
---
# `src/mediapipeline/core/processes/rerun_results_support.py`

**Purpose:** Backend-owned CSV rerun result scanning, open, and promote helpers.

**In-repo imports:** `mediapipeline.core.final_library.promotion_parts.planning`, `mediapipeline.core.final_library.promotion_parts.transfer`, `mediapipeline.core.kernel.contracts.pending_publish`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.processes.rerun_rules`
**HTTP routes:** `/api/rerun/open`, `/api/rerun/promote`, `/api/rerun/promote-dry-run`
**State/config identifiers:** `.manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_results_support.py`._
