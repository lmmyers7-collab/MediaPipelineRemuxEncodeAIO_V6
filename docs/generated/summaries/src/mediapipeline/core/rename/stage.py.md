---
file: src/mediapipeline/core/rename/stage.py
pipeline_stage: rename
token_priority: medium
owner_domain: rename
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 8047cbc0ab0ee05654f1f7688dcb427ab500e8ed1afc2ea8727413aece247605
---
# `src/mediapipeline/core/rename/stage.py`

**Purpose:** Scratch-only Python executor for the guarded rename pipeline stage.

**Classes:** `RenameStageBoundaryError`, `RenameStageFingerprintError`, `RenameStageRecoveryError`
**Public functions:** `execute_scratch_rename_stage()`
**In-repo imports:** `mediapipeline.contracts.stage_mutation`, `mediapipeline.core.paths.layout`, `mediapipeline.core.rename.apply`, `mediapipeline.core.rename.file_io`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/rename/stage.py`._
