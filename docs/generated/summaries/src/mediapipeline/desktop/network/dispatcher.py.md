---
file: src/mediapipeline/desktop/network/dispatcher.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-22
last_reviewed: 2026-06-04
sha256: d75daea722011a88097f00c39ad3a231f2c3a73fa4ed8397ed6c928a7d610639
---
# `src/mediapipeline/desktop/network/dispatcher.py`

**Purpose:** network.dispatcher ================== Abstract base class and shared data types for queue dispatch. All three network modes (Standalone, Coordinator, Worker) implement ``QueueDispatcher``. The rest of the app only ever talks to this interface — it never knows which concrete implementation is active.

**Public symbols:** `ClaimedJob`, `QueueDispatcher`
**HTTP routes:** `/api/done`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/dispatcher.py`._
