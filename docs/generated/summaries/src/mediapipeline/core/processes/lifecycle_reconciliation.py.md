---
file: src/mediapipeline/core/processes/lifecycle_reconciliation.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-13
last_reviewed: 2026-07-13
sha256: 945cfeccac1d62e5870848543b561818dba8a43e4628dc1fa370e4d15f76eec4
---
# `src/mediapipeline/core/processes/lifecycle_reconciliation.py`

**Purpose:** Fail-closed reconciliation for terminal lifecycle recovery evidence.

**Public symbols:** `LifecycleReconciliationService`
**In-repo imports:** `mediapipeline.core.processes.lifecycle_lease`
**HTTP routes:** `/api/audit/start`, `/api/pipeline/start`, `/api/rerun/start`
**State/config identifiers:** `reconciliation-manifest.json`, `recovery-pending.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/lifecycle_reconciliation.py`._
