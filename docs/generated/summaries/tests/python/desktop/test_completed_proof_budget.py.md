---
file: tests/python/desktop/test_completed_proof_budget.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-06-26
last_reviewed: 2026-06-04
sha256: 71d56ee8add03e6b476d30474b0f64653e29d832417fa41cf6ab68f478b2ef17
---
# `tests/python/desktop/test_completed_proof_budget.py`

**Purpose:** Packet 1 (backend-load-performance): completed-job live-proof budgeting. These tests pin the contract that broad completed reads no longer perform a synchronous Path.exists()/stat() sweep for every manifest row, while keeping the evidence explicit (live vs deferred) and leaving full live proof available on demand.

**Public symbols:** `CompletedManifestProofBudgetTests`, `CompletedProofCacheKeyTests`, `CompletedRouteProofDefaultTests`, `CompletedRowProofDtoTests`
**In-repo imports:** `mediapipeline.core.completed.manifest`, `mediapipeline.core.completed.policy`, `mediapipeline.desktop.api.read_payloads_inventory`, `mediapipeline.desktop.application`, `mediapipeline.desktop.models`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_completed_proof_budget.py`._
