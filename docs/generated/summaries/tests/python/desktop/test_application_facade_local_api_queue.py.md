---
file: tests/python/desktop/test_application_facade_local_api_queue.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: orchestration
token_priority: medium
owner_domain: tests
last_modified: 2026-06-26
last_reviewed: 2026-06-24
sha256: de855cb348c8adb0c4398f7d42673defb689060496e1f67e9cc6d228370855f0
---
# `tests/python/desktop/test_application_facade_local_api_queue.py`

**Purpose:** Python implementation for test application facade local api queue; exposes LocalApiQueueTests.

**Public symbols:** `LocalApiQueueTests`
**In-repo imports:** `mediapipeline.core.api.commands_process`, `mediapipeline.desktop.api`, `mediapipeline.desktop.api.handler`, `mediapipeline.desktop.application`, `mediapipeline.desktop.local_api_main`, `mediapipeline.desktop.models`, `mediapipeline.tools.paths`
**HTTP routes:** `/api/commands?limit=10`, `/api/queue/file-overrides`, `/api/queue/file-overrides/effective`, `/api/queue/file-overrides/effective?path={quote`, `/api/queue/file-overrides/route-preview`, `/api/queue/file-overrides?path={quote`, `/api/queue/priority`, `/api/queue/strategy`
**State/config identifiers:** `priority_manifest.json`, `queue_snapshot.json`, `queue_strategy.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_application_facade_local_api_queue.py`._
