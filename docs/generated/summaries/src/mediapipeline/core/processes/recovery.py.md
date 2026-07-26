---
file: src/mediapipeline/core/processes/recovery.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-15
last_reviewed: 2026-07-10
sha256: b1c8621fe5799271c3fcd2da41fa003a593d15d962d7edce68e2c59cf8446021
---
# `src/mediapipeline/core/processes/recovery.py`

**Purpose:** Backend-only lifecycle recovery classification and one-shot resumption.

**Public symbols:** `initial_recovery_status`, `LifecycleRecoveryCoordinator`
**In-repo imports:** `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.lifecycle_lease`
**HTTP routes:** `/api/audit/start`, `/api/pipeline/start`, `/api/rerun/start`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/recovery.py`._
