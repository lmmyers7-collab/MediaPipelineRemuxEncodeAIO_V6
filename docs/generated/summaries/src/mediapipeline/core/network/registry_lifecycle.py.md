---
file: src/mediapipeline/core/network/registry_lifecycle.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 9681d8dd6b2c9b73dcfb5f26c24cbaaa4293b950efdad8658290abb1f08d3593
---
# `src/mediapipeline/core/network/registry_lifecycle.py`

**Purpose:** network.registry ================ ``InFlightRegistry`` — coordinator-side tracking of claimed-but-not-yet-done encode jobs. Thread safety: every public method acquires ``_lock`` before touching shared state. Callers must not hold any other lock when calling in here to avoid deadlocks. Phase 1: full implementation.

**Public symbols:** `InFlightRegistryLifecycleMixin`
**In-repo imports:** `.failure_reasons`, `.json_policy`, `.protocol`, `mediapipeline.core.network.registry_support`, `mediapipeline.core.network.url_policy`
**HTTP routes:** `/api/claim`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/network/registry_lifecycle.py`._
