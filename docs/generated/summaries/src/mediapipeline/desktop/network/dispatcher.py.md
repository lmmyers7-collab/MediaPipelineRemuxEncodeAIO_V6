---
file: src/mediapipeline/desktop/network/dispatcher.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: fb1db8d568ececc4682b3a0a397a4589dda6e13354af57b15fca573dbfe957db
---
# `src/mediapipeline/desktop/network/dispatcher.py`

**Purpose:** network.dispatcher ================== Abstract base class and shared data types for queue dispatch. All three network modes (Standalone, Coordinator, Worker) implement ``QueueDispatcher``. The rest of the app only ever talks to this interface — it never knows which concrete implementation is active.

**Public symbols:** `ClaimedJob`, `QueueDispatcher`
**HTTP routes:** `/api/done`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/dispatcher.py`._
