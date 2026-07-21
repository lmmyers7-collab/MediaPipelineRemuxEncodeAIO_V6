---
file: src/mediapipeline/core/processes/rerun_results_promotion.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 35e129bef02471b97b325ec229bcdc4c27ba541893b70cc1fcaf435970cd05fa
---
# `src/mediapipeline/core/processes/rerun_results_promotion.py`

**Purpose:** Backend-owned CSV rerun result scanning, open, and promote helpers.

**Public symbols:** `rerun_open_backend_known_path`, `rerun_promote_dry_run`, `rerun_promote_to_pending_publish`
**In-repo imports:** `mediapipeline.core.final_library.promotion_parts.planning`, `mediapipeline.core.final_library.promotion_parts.transfer`, `mediapipeline.core.kernel.contracts.pending_publish`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.processes.rerun_results_destination_policy`, `mediapipeline.core.processes.rerun_results_support`, `mediapipeline.core.processes.rerun_rules`
**State/config identifiers:** `.manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_results_promotion.py`._
