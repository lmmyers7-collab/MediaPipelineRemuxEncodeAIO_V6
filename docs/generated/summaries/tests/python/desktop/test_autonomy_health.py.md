---
file: tests/python/desktop/test_autonomy_health.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-02
last_reviewed: 2026-06-17
sha256: d8eb54a2fcba1f8185be509ad7e5810d007dbb55359a8375f479016881798073
---
# `tests/python/desktop/test_autonomy_health.py`

**Purpose:** Python implementation for test autonomy health; exposes AutonomyHealthPayloadTests.

**Public symbols:** `AutonomyHealthPayloadTests`
**In-repo imports:** `mediapipeline.core.diagnostics.autonomy_health`, `mediapipeline.core.processes.path_evidence`, `mediapipeline.core.storage.db`, `mediapipeline.desktop.models`, `mediapipeline.tools.autonomy_health_gate`, `mediapipeline.tools.paths`
**HTTP routes:** `/api/maintenance/archive-state-journals`, `/api/pending-publish/recovery-plan`, `/api/pipeline/start`
**State/config identifiers:** `config.psd1`, `mediapipeline.core.storage.db`, `movie.manifest.json`, `queue_snapshot.json`, `queued.json`, `state_db_maintenance.json`, `worker_state.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_autonomy_health.py`._
