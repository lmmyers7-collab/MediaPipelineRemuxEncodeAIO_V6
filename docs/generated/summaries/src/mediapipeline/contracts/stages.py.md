---
file: src/mediapipeline/contracts/stages.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 8b88bbd37f6778255e6ea993629fa73598ae6f622e55fe7b2c30f825731ca406
---
# `src/mediapipeline/contracts/stages.py`

**Purpose:** Canonical Pydantic contracts for pipeline stage execution. Python owns orchestration and sends one versioned request envelope to the PowerShell engine. PowerShell executes the requested stage and writes one versioned result envelope to stdout. Stage-specific payload/data models live here so generated schema, runner validation, and dispatcher tests all share one contract.

**Public symbols:** `build_stage_request`, `make_stage_result`, `stage_contract`, `stage_journal_event_type`, `stage_payload_model`, `stage_result_model`, `StageContract`, `StageContractSchema`, `StageRequest`, `StageResult`, `validate_stage_data`, `validation_error_message`
**In-repo imports:** `mediapipeline.contracts.stage_base`, `mediapipeline.contracts.stage_decide`, `mediapipeline.contracts.stage_mutation`, `mediapipeline.contracts.stage_probe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/stages.py`._
