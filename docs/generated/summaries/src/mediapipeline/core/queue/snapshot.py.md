---
file: src/mediapipeline/core/queue/snapshot.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 46bc978229b210e6112f094098356ca2ccdd7dac8c8d8b333a8cd4a7ad6783cd
---
# `src/mediapipeline/core/queue/snapshot.py`

**Purpose:** Python implementation for snapshot; exposes queue_dry_run_tail, queue_record_from_snapshot_row, queue_snapshot_is_current_for_request.

**Public symbols:** `queue_dry_run_tail`, `queue_record_from_snapshot_row`, `queue_snapshot_is_current_for_request`, `queue_snapshot_path`, `queue_snapshot_write_path`, `read_queue_snapshot`
**In-repo imports:** `mediapipeline.core.kernel.contracts`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.queue.contracts`
**State/config identifiers:** `queue_snapshot.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/queue/snapshot.py`._
