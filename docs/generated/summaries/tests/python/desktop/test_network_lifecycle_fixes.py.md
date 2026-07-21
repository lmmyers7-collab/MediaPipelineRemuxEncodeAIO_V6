---
file: tests/python/desktop/test_network_lifecycle_fixes.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: tests
last_modified: 2026-07-09
last_reviewed: 2026-06-13
sha256: 40fe86c7536b2a15bf36b0ea3774f0c082a917d091c62a62a2f258a1f6940af8
---
# `tests/python/desktop/test_network_lifecycle_fixes.py`

**Purpose:** Regression tests for the 2026-06-13 Network Worker/Coordinator review fixes. Covers the integration seams the older suite stubbed over: * D1 - the desktop facade actually exposes the four lifecycle providers. * D2 - the coordinator re-scans the source queue instead of draining only the start-time snapshot. * D3 - claim metadata reads the real ``QueueRecord`` fields (``is_priority`` / ``size_gb``) with back-compat fallback to the legacy names. * D4 - the lifecycle worker-URL precondition requires a port (parity with the dispatcher-level ``validate_coordinator_url``). * D5 - a stop whose provider ran but whose journal write failed commits the stopped state instead of leaving a phantom ``running``.

**Public symbols:** `CoordinatorQueueRefreshTests`, `LifecycleProviderPresenceTests`, `QueueRecordFieldCoercionTests`, `RunningWorkerSettingsHotApplyTests`, `StopJournalFailureCommitsStoppedTests`, `WorkerUrlPreconditionParityTests`
**In-repo imports:** `mediapipeline.desktop.application`, `mediapipeline.desktop.application.network_lifecycle_provider`, `mediapipeline.desktop.network.coordinator_queue`, `mediapipeline.desktop.network.coordinator_url`, `mediapipeline.desktop.network.worker`, `mediapipeline.tools.paths`
**State/config identifiers:** `config.psd1`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_network_lifecycle_fixes.py`._
