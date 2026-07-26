---
file: src/mediapipeline/desktop/network/registry_snapshots.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 367985dd6994e5b343c6eff9e93d751d256fb24ab71c33e9f9a74a2967269929
---
# `src/mediapipeline/desktop/network/registry_snapshots.py`

**Purpose:** network.registry ================ ``InFlightRegistry`` — coordinator-side tracking of claimed-but-not-yet-done encode jobs. Thread safety: every public method acquires ``_lock`` before touching shared state. Callers must not hold any other lock when calling in here to avoid deadlocks. Phase 1: full implementation.

**Public symbols:** `InFlightRegistrySnapshotsMixin`
**In-repo imports:** `.failure_reasons`, `.json_policy`, `.protocol`, `mediapipeline.core.network.url_policy`, `mediapipeline.desktop.network.registry_support`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/registry_snapshots.py`._
