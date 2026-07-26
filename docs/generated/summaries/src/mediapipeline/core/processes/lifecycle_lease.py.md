---
file: src/mediapipeline/core/processes/lifecycle_lease.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-15
last_reviewed: 2026-07-10
sha256: 41f69e67841d7a739c3a36d094a275f092834648ac5ab27d89dd78fc2431d545
---
# `src/mediapipeline/core/processes/lifecycle_lease.py`

**Purpose:** Durable, fail-closed lifecycle lease for backend-owned work.

**Public symbols:** `LifecycleLease`, `LifecycleLeaseError`, `LifecycleLeaseStore`
**In-repo imports:** `mediapipeline.core.processes.active_jobs`
**State/config identifiers:** `LifecycleReconciliationPending.json`, `recovery-pending.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/lifecycle_lease.py`._
