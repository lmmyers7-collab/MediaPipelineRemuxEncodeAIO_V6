---
file: src/mediapipeline/desktop/network/worker.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 8cf8b420055193948ad55d061c35cbfa3a29384318697e50510ead95041fca7a
---
# `src/mediapipeline/desktop/network/worker.py`

**Purpose:** network.worker ============== ``WorkerDispatcher`` — polls a remote coordinator for jobs and executes them by launching the PowerShell pipeline with ``-SingleFile <path>``. Phase 2 implementation.

**Public symbols:** `WorkerDispatcher`
**In-repo imports:** `..config_keys`, `.coordinator_url`, `.diagnostics`, `.dispatcher`, `.http_json`, `.library_roots`, `.path_map`, `.poll_policy`, `.processing_policy`, `.protocol`, `.worker_claims`, `.worker_http`, `.worker_loops`, `.worker_parts.reporting`, `.worker_record`, `.worker_state`, `mediapipeline.core.network.url_policy`
**HTTP routes:** `/api/claim`, `/api/heartbeat`, `/api/libraries`, `/api/log`
**State/config identifiers:** `worker_state.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/worker.py`._
