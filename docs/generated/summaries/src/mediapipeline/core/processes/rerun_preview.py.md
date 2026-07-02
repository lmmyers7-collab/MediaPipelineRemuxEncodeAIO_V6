---
file: src/mediapipeline/core/processes/rerun_preview.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-02
last_reviewed: 2026-06-29
sha256: e34ea91179ff19d2349955023cbb23290e28e08e303aa7be740d0ffa8098d72b
---
# `src/mediapipeline/core/processes/rerun_preview.py`

**Purpose:** CSV rerun preview, scoping, and scoped CSV materialization helpers.

**Classes:** `RerunCsvRow`, `RerunPreviewScope`
**Public functions:** `materialize_scoped_rerun_csv()`, `read_rerun_csv_rows()`, `recent_rerun_csv_candidates()`, `request_needs_scoped_csv()`, `rerun_csv_preview_payload()`, `rerun_import_csv_root()`, `rerun_original_hold_root()`, `rerun_preview_scope_from_request()`, `scoped_rerun_csv_root()`, `scoped_rerun_rows()`
**In-repo imports:** `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_policy`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_preview.py`._
