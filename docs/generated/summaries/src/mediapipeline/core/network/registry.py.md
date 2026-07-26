---
file: src/mediapipeline/core/network/registry.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-11
last_reviewed: 2026-06-29
sha256: 0886ea5b27668b01e64a36c472df78808953ed2432b557bd65d070a041864180
---
# `src/mediapipeline/core/network/registry.py`

**Purpose:** network.registry ================ ``InFlightRegistry`` — coordinator-side tracking of claimed-but-not-yet-done encode jobs. Thread safety: every public method acquires ``_lock`` before touching shared state. Callers must not hold any other lock when calling in here to avoid deadlocks. Phase 1: full implementation.

**Public symbols:** `InFlightRegistry`
**In-repo imports:** `.failure_reasons`, `.json_policy`, `.protocol`, `mediapipeline.core.network.registry_lifecycle`, `mediapipeline.core.network.registry_persistence`, `mediapipeline.core.network.registry_recovery`, `mediapipeline.core.network.registry_snapshots`, `mediapipeline.core.network.registry_support`, `mediapipeline.core.network.url_policy`
**HTTP routes:** `/api/claim`, `/api/done`, `/api/heartbeat`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/network/registry.py`._
