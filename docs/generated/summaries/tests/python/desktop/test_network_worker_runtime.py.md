---
file: tests/python/desktop/test_network_worker_runtime.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: tests
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 70f61c0448b79802d0aa4979c05749c9692ee0ecbe7474b8d443531d4375a9de
---
# `tests/python/desktop/test_network_worker_runtime.py`

**Purpose:** Python implementation for test network worker runtime; exposes NetworkWorkerRuntimeTests, WorkerEncodeStartTests.

**Public symbols:** `NetworkWorkerRuntimeTests`, `WorkerEncodeStartTests`
**In-repo imports:** `mediapipeline.desktop.network.auth`, `mediapipeline.desktop.network.cluster_log`, `mediapipeline.desktop.network.coordinator`, `mediapipeline.desktop.network.coordinator_http`, `mediapipeline.desktop.network.coordinator_policy`, `mediapipeline.desktop.network.coordinator_url`, `mediapipeline.desktop.network.diagnostics`, `mediapipeline.desktop.network.encode_config_snapshot`, `mediapipeline.desktop.network.failure_policy`, `mediapipeline.desktop.network.firewall`, `mediapipeline.desktop.network.http_json`, `mediapipeline.desktop.network.identity`, `mediapipeline.desktop.network.path_map`, `mediapipeline.desktop.network.poll_policy`, `mediapipeline.desktop.network.probe`, `mediapipeline.desktop.network.protocol`, `mediapipeline.desktop.network.registry`, `mediapipeline.desktop.network.share_block`, `mediapipeline.desktop.network.threading_helpers`, `mediapipeline.desktop.network.worker`, `mediapipeline.desktop.network.worker_done`, `mediapipeline.desktop.network.worker_record`, `mediapipeline.desktop.network.worker_state`, `mediapipeline.tools.paths`
**HTTP routes:** `/api/claim:`, `/api/done`, `/api/heartbeat`, `/api/log`, `/api/log?token=url-secret`
**State/config identifiers:** `app_state.json`, `worker_state.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_network_worker_runtime.py`._
