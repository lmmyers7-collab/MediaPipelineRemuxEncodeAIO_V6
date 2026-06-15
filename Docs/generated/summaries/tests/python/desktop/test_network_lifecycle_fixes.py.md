---
file: tests/python/desktop/test_network_lifecycle_fixes.py
pipeline_stage: network
token_priority: medium
owner_domain: tests
last_modified: 2026-06-14
last_reviewed: 2026-06-13
sha256: 9fe53e4f06f0a1842a3609dfe7752fdd1f339599c637aa036a9c0a2adc801f0a
---
# `tests/python/desktop/test_network_lifecycle_fixes.py`

**Purpose:** Regression tests for the 2026-06-13 Network Worker/Coordinator review fixes.

**Classes:** `CoordinatorQueueRefreshTests`, `LifecycleProviderPresenceTests`, `QueueRecordFieldCoercionTests`, `RunningWorkerSettingsHotApplyTests`, `StopJournalFailureCommitsStoppedTests`, `WorkerUrlPreconditionParityTests`, `_FakeCoordinatorDispatcher`
**In-repo imports:** `mediapipeline.desktop.application`, `mediapipeline.desktop.application.network_lifecycle_provider`, `mediapipeline.desktop.network.coordinator_queue`, `mediapipeline.desktop.network.coordinator_url`, `mediapipeline.desktop.network.worker`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_network_lifecycle_fixes.py`._
