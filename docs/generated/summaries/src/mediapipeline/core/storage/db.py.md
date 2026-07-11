---
file: src/mediapipeline/core/storage/db.py
pipeline_stage: n/a
token_priority: medium
owner_domain: storage
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 3a8d58d05fb2739301da92fe1e7bdede9899a3faeecc13f68564b50e4a350282
---
# `src/mediapipeline/core/storage/db.py`

**Purpose:** SQLite mirror storage for Phase 4 shadow writes.

**Classes:** `StateDb`, `StateDbError`, `StateDbIncompatibleVersion`
**Public functions:** `maybe_maintain_state_db()`, `open_state_db()`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/storage/db.py`._
