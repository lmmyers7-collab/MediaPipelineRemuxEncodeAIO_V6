---
file: tests/python/desktop/test_network_lifecycle_fixes.py
pipeline_stage: network
token_priority: medium
owner_domain: tests
last_modified: 2026-07-10
last_reviewed: 2026-06-13
sha256: afedeb5d6c69080c6a52bfbf724b8403082ab4dd0607dd94ba7c91852a145890
---
# `tests/python/desktop/test_network_lifecycle_fixes.py`

**Purpose:** Regression tests for the 2026-06-13 Network Worker/Coordinator review fixes.

**Classes:** `CoordinatorQueueRefreshTests`, `LifecycleProviderPresenceTests`, `QueueRecordFieldCoercionTests`, `RunningWorkerSettingsHotApplyTests`, `StopJournalFailureCommitsStoppedTests`, `WorkerUrlPreconditionParityTests`, `_FakeCoordinatorDispatcher`
**In-repo imports:** `mediapipeline.desktop.application`, `mediapipeline.desktop.application.network_lifecycle_provider`, `mediapipeline.desktop.network.coordinator_queue`, `mediapipeline.desktop.network.coordinator_url`, `mediapipeline.desktop.network.worker`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_network_lifecycle_fixes.py`._
