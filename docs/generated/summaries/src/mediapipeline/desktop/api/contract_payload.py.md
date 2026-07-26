---
file: src/mediapipeline/desktop/api/contract_payload.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: api
token_priority: medium
owner_domain: api
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 5bcf2b891b3481e186bb8ca9dc60861cfc63f7bf6cd5e9fba31fef9fa866d35c
---
# `src/mediapipeline/desktop/api/contract_payload.py`

**Purpose:** Python implementation for contract payload; exposes local_api_contract_payload.

**Public symbols:** `local_api_contract_payload`
**In-repo imports:** `.contract`, `.contract_shared`
**HTTP routes:** `/api/completed/reconcile-manifest`, `/api/completed/reconcile-manifest-dry-run`, `/api/completed/repair-sidecar-metadata`, `/api/completed/repair-sidecar-metadata-dry-run`, `/api/pending-publish/reconcile-orphan-payloads`, `/api/pending-publish/reconcile-orphan-payloads-dry-run`, `/api/pending-publish/repair-manifest`, `/api/pending-publish/repair-manifest-dry-run`, `/api/startup/reconcile-dry-run`
**State/config identifiers:** `worker_state.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/api/contract_payload.py`._
