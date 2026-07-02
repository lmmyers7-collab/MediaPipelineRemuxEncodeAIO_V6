---
file: src/mediapipeline/core/processes/rerun_results.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-02
last_reviewed: 2026-06-30
sha256: eef95fe710788c418f15169f8278d2919d1478f2a00b5e99a6764446558f1c44
---
# `src/mediapipeline/core/processes/rerun_results.py`

**Purpose:** Backend-owned CSV rerun result scanning, open, and promote helpers.

**Public functions:** `rerun_open_backend_known_path()`, `rerun_promote_dry_run()`, `rerun_promote_to_pending_publish()`, `rerun_results_payload()`
**In-repo imports:** `mediapipeline.core.kernel.contracts.pending_publish`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_preview`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_results.py`._
