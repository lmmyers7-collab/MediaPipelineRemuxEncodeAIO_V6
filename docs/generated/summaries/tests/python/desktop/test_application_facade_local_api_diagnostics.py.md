---
file: tests/python/desktop/test_application_facade_local_api_diagnostics.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: tests
last_modified: 2026-07-04
last_reviewed: 2026-06-24
sha256: 66e69822552ac3bd7d3ee292fc788b4b88c3ee20122ef9acb2cd54a04fd1e3a8
---
# `tests/python/desktop/test_application_facade_local_api_diagnostics.py`

**Purpose:** Python implementation for test application facade local api diagnostics; exposes LocalApiDiagnosticsTests.

**Public symbols:** `LocalApiDiagnosticsTests`
**In-repo imports:** `mediapipeline.core.api.commands_process`, `mediapipeline.desktop.api`, `mediapipeline.desktop.api.handler`, `mediapipeline.desktop.application`, `mediapipeline.desktop.local_api_main`, `mediapipeline.desktop.models`, `mediapipeline.tools.paths`
**HTTP routes:** `/api/diagnostics/state-summary`, `/api/diagnostics/tail?target=C`, `/api/diagnostics/tail?target=cluster_log&max_bytes=4096`, `/api/diagnostics/tail?target=pipeline_log&max_bytes=4096`
**State/config identifiers:** `queue_snapshot.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_application_facade_local_api_diagnostics.py`._
