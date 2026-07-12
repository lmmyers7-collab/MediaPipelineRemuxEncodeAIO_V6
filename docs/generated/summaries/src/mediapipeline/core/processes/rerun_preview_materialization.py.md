---
file: src/mediapipeline/core/processes/rerun_preview_materialization.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-12
last_reviewed: 2026-07-11
sha256: f9517c8326eb98a3eda80590f73144d1977199bd45627da34b13835cc7688eb8
---
# `src/mediapipeline/core/processes/rerun_preview_materialization.py`

**Purpose:** CSV rerun preview, scoping, and scoped CSV materialization helpers.

**Public functions:** `materialize_scoped_rerun_csv()`, `request_needs_scoped_csv()`
**In-repo imports:** `mediapipeline.core.audit.rerun_csv`, `mediapipeline.core.network.library_roots`, `mediapipeline.core.network.rerun_handoff`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.paths.layout`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview_presentation`, `mediapipeline.core.processes.rerun_preview_support`, `mediapipeline.core.processes.rerun_rules`, `mediapipeline.core.processes.rerun_state_correlation`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_preview_materialization.py`._
