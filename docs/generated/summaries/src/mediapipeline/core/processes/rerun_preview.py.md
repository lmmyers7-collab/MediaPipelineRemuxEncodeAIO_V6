---
file: src/mediapipeline/core/processes/rerun_preview.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-06-29
last_reviewed: 2026-06-29
sha256: 816d71e4549677a96adb51801e4bd2b0e201a4a461be68132cdb0d55d7d1ff74
---
# `src/mediapipeline/core/processes/rerun_preview.py`

**Purpose:** CSV rerun preview, scoping, and scoped CSV materialization helpers.

**Classes:** `RerunCsvRow`, `RerunPreviewScope`
**Public functions:** `materialize_scoped_rerun_csv()`, `read_rerun_csv_rows()`, `recent_rerun_csv_candidates()`, `request_needs_scoped_csv()`, `rerun_csv_preview_payload()`, `rerun_preview_scope_from_request()`, `scoped_rerun_rows()`
**In-repo imports:** `mediapipeline.core.kernel.models`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.rerun_policy`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_preview.py`._
