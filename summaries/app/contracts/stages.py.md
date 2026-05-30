---
file: app/contracts/stages.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-05-29
last_reviewed: 2026-05-28
sha256: 55ae4097a685faa2636889eadb4a0da6b294932032e3a4b1959cf00469fd329e
---
# `app/contracts/stages.py`

**Purpose:** Canonical Pydantic contracts for pipeline stage execution.

**Classes:** `AudioMixPayload`, `AudioMixResult`, `DecidePayload`, `DecideResult`, `DrainPayload`, `DrainResult`, `IngestPayload`, `IngestResult`, `ProbePayload`, `ProbeResult`, `PublishPayload`, `PublishResult`, `RenamePayload`, `RenameResult`, `StageContract`
**Public functions:** `build_stage_request()`, `make_stage_result()`, `stage_contract()`, `stage_journal_event_type()`, `stage_payload_model()`, `stage_result_model()`, `validate_stage_data()`, `validation_error_message()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/contracts/stages.py`._
