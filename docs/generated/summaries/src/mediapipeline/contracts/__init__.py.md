---
file: src/mediapipeline/contracts/__init__.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: contracts
token_priority: low
owner_domain: contracts
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 6f5627f3ba5a1f855acaef4c763267ef59cb1db9bcdf32c3e82e868d853518fb
---
# `src/mediapipeline/contracts/__init__.py`

**Purpose:** Canonical pipeline contracts. This package is the single source of truth for: - Pipeline stage I/O shapes (`stages.py`). - Source media facts normalized from probe JSON (`source_media.py`). - Abstract dry-run pipeline plans (`pipeline_plan.py`). - Verification and publish guard results (`verification.py`). - Effective decision policy shared by config and decide (`decision_policy.py`). - Configuration shape (`config.py`, Pydantic v2). - Local API command payload shapes (`api_commands.py`). - File lifecycle/state-machine documentation source (`lifecycle.py`). - Runtime diagnostic evidence (`runtime_evidence.py`). - Subtitle QA evidence (`subtitles.py`). - Local API route metadata (`api_routes.py`). - Backend-owned Run Once monitoring evidence (`run_monitor.py`). - Cross-stage data shapes (jobs, manifests, events) — added in later phases. `config.py` generates `src/mediapipeline/contracts/schemas/config.v1.schema.json`. `stages.py` generates `src/mediapipeline/contracts/schemas/stages.v1.schema.json` and defines the single Python-to-PowerShell stage execution contract. `lifecycle.py` generates `docs/architecture/FILE_LIFECYCLE_MAP.md`.

**State/config identifiers:** `config.v1.schema.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/__init__.py`._
