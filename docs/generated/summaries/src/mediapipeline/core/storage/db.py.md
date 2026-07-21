---
file: src/mediapipeline/core/storage/db.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: storage
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 3a8d58d05fb2739301da92fe1e7bdede9899a3faeecc13f68564b50e4a350282
---
# `src/mediapipeline/core/storage/db.py`

**Purpose:** SQLite mirror storage for Phase 4 shadow writes. The JSON files under the runtime state tree remain authoritative. This module creates a durable SQLite mirror that can be populated opportunistically by new paths without changing existing reads or operator-visible behavior.

**Public symbols:** `maybe_maintain_state_db`, `open_state_db`, `StateDb`, `StateDbError`, `StateDbIncompatibleVersion`
**State/config identifiers:** `mediapipeline_state.sqlite3`, `state_db_maintenance.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/storage/db.py`._
