---
file: src/mediapipeline/core/processes/rerun_results.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-06-30
last_reviewed: 2026-06-30
sha256: b8120d72585105ea3c7a849d39e5ad5d7f6ea2b16390b11de4bee128df1146f6
---
# `src/mediapipeline/core/processes/rerun_results.py`

**Purpose:** Backend-owned CSV rerun result scanning, open, and promote helpers.

**Public functions:** `rerun_open_backend_known_path()`, `rerun_promote_dry_run()`, `rerun_promote_to_pending_publish()`, `rerun_results_payload()`
**In-repo imports:** `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_preview`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_results.py`._
