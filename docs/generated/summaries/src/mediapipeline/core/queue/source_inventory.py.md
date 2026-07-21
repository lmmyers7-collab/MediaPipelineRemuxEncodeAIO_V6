---
file: src/mediapipeline/core/queue/source_inventory.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 5738d645fb7b46d19ff68d2e6c8f069a16aa1d33e2e7a89850ddc76e2b712a92
---
# `src/mediapipeline/core/queue/source_inventory.py`

**Purpose:** Python implementation for source inventory; exposes build_queue_source_inventory, preview_queue_source_inventory, queue_inventory_source_roots.

**Public symbols:** `build_queue_source_inventory`, `preview_queue_source_inventory`, `queue_inventory_source_roots`, `queue_scan_progress_bars`, `queue_scan_status_path`, `queue_scan_status_payload`, `queue_source_inventory_path`, `QueueInventoryRoot`, `read_json_artifact`, `read_queue_scan_status`, `utc_now_iso`, `write_json_artifact`
**In-repo imports:** `mediapipeline.core.config.library_profiles`, `mediapipeline.core.files.constants`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.queue.file_io`
**State/config identifiers:** `queue_scan_status.json`, `queue_source_inventory.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/queue/source_inventory.py`._
