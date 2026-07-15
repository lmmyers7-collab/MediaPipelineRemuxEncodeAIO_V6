---
file: src/mediapipeline/core/processes/rerun_preview_support.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-14
last_reviewed: 2026-07-11
sha256: 1aa2c85679ccf1ee7813dbacd19d78448cd2a1af86bacff46870901e48d517d6
---
# `src/mediapipeline/core/processes/rerun_preview_support.py`

**Purpose:** CSV rerun preview, scoping, and scoped CSV materialization helpers.

**Classes:** `RerunCsvRow`, `RerunPreviewScope`
**Public functions:** `read_rerun_csv_rows()`, `recent_rerun_csv_candidates()`, `rerun_import_csv_root()`, `rerun_original_hold_root()`, `rerun_preview_scope_from_request()`, `scoped_rerun_csv_root()`, `scoped_rerun_rows()`
**In-repo imports:** `mediapipeline.core.audit.rerun_csv`, `mediapipeline.core.network.library_roots`, `mediapipeline.core.network.rerun_handoff`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.paths.layout`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_rules`, `mediapipeline.core.processes.rerun_source_health`, `mediapipeline.core.processes.rerun_state_correlation`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_preview_support.py`._
