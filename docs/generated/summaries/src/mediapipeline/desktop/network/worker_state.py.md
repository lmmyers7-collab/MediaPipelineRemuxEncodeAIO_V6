---
file: src/mediapipeline/desktop/network/worker_state.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-22
last_reviewed: 2026-06-04
sha256: 9b66b63d46170792a38de13e5e8d40088c64c41100a1d956a4439a5cf6fce6df
---
# `src/mediapipeline/desktop/network/worker_state.py`

**Purpose:** Python implementation for worker state; exposes atomic_write_text, clear_worker_state, iter_pending_done_report_files.

**Public symbols:** `atomic_write_text`, `clear_worker_state`, `iter_pending_done_report_files`, `load_pending_done_report`, `load_worker_state`, `pending_done_reports_dir`, `pending_done_reports_review_dir`, `quarantine_pending_done_report`, `quarantine_worker_state`, `queue_pending_done_report`, `save_worker_state`, `worker_state_backup_path`, `worker_state_review_dir`, `WorkerStateMixin`
**In-repo imports:** `.diagnostics`, `.dispatcher`, `.json_policy`, `.worker_done`, `.worker_parts.state_reports`
**HTTP routes:** `/api/done`
**State/config identifiers:** `worker_state.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/worker_state.py`._
