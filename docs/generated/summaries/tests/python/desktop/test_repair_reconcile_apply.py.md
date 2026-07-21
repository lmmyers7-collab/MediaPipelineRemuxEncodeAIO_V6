---
file: tests/python/desktop/test_repair_reconcile_apply.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-11
last_reviewed: 2026-06-19
sha256: 8003c7f7b08b3cdaa4df137312ba1ee3c0fd60fbd0e6ec794aa7f727eba9ac63
---
# `tests/python/desktop/test_repair_reconcile_apply.py`

**Purpose:** Python implementation for test repair reconcile apply; exposes RepairReconcileApplyTests.

**Public symbols:** `RepairReconcileApplyTests`
**In-repo imports:** `mediapipeline.core.completed.policy`, `mediapipeline.core.kernel.contracts.pending_publish`, `mediapipeline.core.repair_reconcile.apply`, `mediapipeline.core.repair_reconcile.dry_run`, `mediapipeline.core.validation.boundary`, `mediapipeline.desktop.api`, `mediapipeline.desktop.application`, `mediapipeline.desktop.models`, `mediapipeline.tools.paths`
**HTTP routes:** `/api/commands?limit=10`, `/api/completed/reconcile-manifest`, `/api/completed/reconcile-manifest-dry-run`, `/api/completed/repair-sidecar-metadata`, `/api/completed/repair-sidecar-metadata-dry-run`, `/api/pending-publish`, `/api/pending-publish/reconcile-orphan-payloads`, `/api/pending-publish/reconcile-orphan-payloads-dry-run`, `/api/pending-publish/repair-manifest`, `/api/pending-publish/repair-manifest-dry-run`
**State/config identifiers:** `.manifest.json`, `drain_config.psd1`, `pending_drain_summary.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_repair_reconcile_apply.py`._
