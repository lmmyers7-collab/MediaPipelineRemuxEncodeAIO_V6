---
file: src/mediapipeline/contracts/stages.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 920291fe5148f59d74898884d7ea120b99609c3891ec741c59ff98b892227d5a
---
# `src/mediapipeline/contracts/stages.py`

**Purpose:** Canonical Pydantic contracts for pipeline stage execution.

**Classes:** `StageContract`, `StageContractSchema`, `StageRequest`, `StageResult`
**Public functions:** `build_stage_request()`, `make_stage_result()`, `stage_contract()`, `stage_journal_event_type()`, `stage_payload_model()`, `stage_result_model()`, `validate_stage_data()`, `validation_error_message()`
**In-repo imports:** `mediapipeline.contracts.stage_base`, `mediapipeline.contracts.stage_decide`, `mediapipeline.contracts.stage_mutation`, `mediapipeline.contracts.stage_probe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/stages.py`._
