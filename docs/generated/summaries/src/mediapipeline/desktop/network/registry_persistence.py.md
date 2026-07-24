---
file: src/mediapipeline/desktop/network/registry_persistence.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-22
last_reviewed: 2026-07-11
sha256: 94576d65622f36782835ec96cf5bca51a508a1c397c15f82665e8f2694098dc3
---
# `src/mediapipeline/desktop/network/registry_persistence.py`

**Purpose:** network.registry ================ ``InFlightRegistry`` — coordinator-side tracking of claimed-but-not-yet-done encode jobs. Thread safety: every public method acquires ``_lock`` before touching shared state. Callers must not hold any other lock when calling in here to avoid deadlocks. Phase 1: full implementation.

**Public symbols:** `InFlightRegistryPersistenceMixin`
**In-repo imports:** `.failure_reasons`, `.json_policy`, `.protocol`, `mediapipeline.core.network.url_policy`, `mediapipeline.desktop.network.registry_support`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/registry_persistence.py`._
