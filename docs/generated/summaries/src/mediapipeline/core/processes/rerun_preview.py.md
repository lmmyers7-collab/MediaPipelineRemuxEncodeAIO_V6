---
file: src/mediapipeline/core/processes/rerun_preview.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-10
last_reviewed: 2026-07-09
sha256: bc83e328a19bca9ced05a5a3e0ea2e0a1deb44dc560c643abdd279a7a137ffc3
---
# `src/mediapipeline/core/processes/rerun_preview.py`

**Purpose:** CSV rerun preview, scoping, and scoped CSV materialization helpers.

**Classes:** `RerunCsvRow`, `RerunPreviewScope`
**Public functions:** `materialize_scoped_rerun_csv()`, `read_rerun_csv_rows()`, `recent_rerun_csv_candidates()`, `request_needs_scoped_csv()`, `rerun_csv_preview_payload()`, `rerun_import_csv_root()`, `rerun_network_csv_preview_payload()`, `rerun_original_hold_root()`, `rerun_preview_scope_from_request()`, `scoped_rerun_csv_root()`, `scoped_rerun_rows()`
**In-repo imports:** `mediapipeline.core.audit.rerun_csv`, `mediapipeline.core.network.library_roots`, `mediapipeline.core.network.rerun_handoff`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.paths.layout`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_rules`, `mediapipeline.core.processes.rerun_state_correlation`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_preview.py`._
