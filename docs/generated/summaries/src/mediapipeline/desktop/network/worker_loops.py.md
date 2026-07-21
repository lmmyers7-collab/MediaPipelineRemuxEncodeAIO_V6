---
file: src/mediapipeline/desktop/network/worker_loops.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-05
last_reviewed: 2026-06-04
sha256: 4103b102bc6be64145482463d9a9536801bacabf0dd6d4cfc2e661204d269266
---
# `src/mediapipeline/desktop/network/worker_loops.py`

**Purpose:** Polling, heartbeat, and shutdown loops for :class:`WorkerDispatcher`.

**Public symbols:** `WorkerLoopMixin`
**In-repo imports:** `.coordinator_policy`, `.diagnostics`, `.library_roots`, `.poll_policy`, `.protocol`, `.worker_parts.reporting`, `.worker_parts.tasks`, `.worker_record`
**HTTP routes:** `/api/claim`, `/api/heartbeat`, `/api/log`
**State/config identifiers:** `worker_state.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/worker_loops.py`._
