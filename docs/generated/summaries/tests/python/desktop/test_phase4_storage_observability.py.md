---
file: tests/python/desktop/test_phase4_storage_observability.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: tests
last_modified: 2026-07-23
last_reviewed: 2026-06-04
sha256: 5bf10ff871a288c7d04648546b4bd9598596c5ecd91529e2555d983758ecf9c8
---
# `tests/python/desktop/test_phase4_storage_observability.py`

**Purpose:** Python implementation for test phase4 storage observability; exposes Phase4StorageObservabilityTests.

**Public symbols:** `Phase4StorageObservabilityTests`
**In-repo imports:** `mediapipeline.core.completed.service`, `mediapipeline.core.observability.logging`, `mediapipeline.core.orchestration.runner`, `mediapipeline.core.queue.dry_run_runner`, `mediapipeline.core.queue.snapshot`, `mediapipeline.core.storage.db`, `mediapipeline.core.validation.boundary`, `mediapipeline.desktop.api`, `mediapipeline.desktop.api.command_journal`, `mediapipeline.desktop.api.command_journal_policy`, `mediapipeline.desktop.models`, `mediapipeline.desktop.subprocess_runner`, `mediapipeline.tools.paths`
**HTTP routes:** `/api/settings/reload`
**State/config identifiers:** `config.psd1`, `mediapipeline.core.storage.db`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_phase4_storage_observability.py`._
