---
file: tests/python/desktop/test_lifecycle_reconciliation_api.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-12
last_reviewed: 2026-07-13
sha256: 9a6693d033c1688a30f6b4a2d030f4fb7738deae07edce7e0b19a7cb880dc567
---
# `tests/python/desktop/test_lifecycle_reconciliation_api.py`

**Purpose:** Python implementation for test lifecycle reconciliation api; exposes LifecycleReconciliationApiContractTests, LifecycleReconciliationFacadeTests, LifecycleReconciliationLocalApiTests.

**Public symbols:** `LifecycleReconciliationApiContractTests`, `LifecycleReconciliationFacadeTests`, `LifecycleReconciliationLocalApiTests`
**In-repo imports:** `mediapipeline.core.api.commands`, `mediapipeline.core.processes.lifecycle_lease`, `mediapipeline.core.validation.boundary`, `mediapipeline.desktop.api`, `mediapipeline.desktop.api.contract`, `mediapipeline.desktop.api.handler_policy`, `mediapipeline.desktop.api.routes_command`, `mediapipeline.desktop.application`
**HTTP routes:** `/api/audit/start`, `/api/backend/lifecycle/reconcile`, `/api/backend/lifecycle/reconcile-dry-run`, `/api/backend/recovery-status`, `/api/commands?limit=20`
**State/config identifiers:** `recovery-pending.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_lifecycle_reconciliation_api.py`._
