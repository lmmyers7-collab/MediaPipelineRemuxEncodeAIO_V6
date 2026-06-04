---
file: app/contracts/stages.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-06-03
last_reviewed: 2026-05-28
sha256: 7ac57dfd2eaf0216e7116322ac38051d80680414bc649cd692aca723c22d8a45
---
# `app/contracts/stages.py`

**Purpose:** Canonical Pydantic contracts for pipeline stage execution.

**Classes:** `AudioMixPayload`, `AudioMixResult`, `DecidePayload`, `DecideResult`, `DrainPayload`, `DrainResult`, `IngestPayload`, `IngestResult`, `ProbePayload`, `ProbeResult`, `PublishPayload`, `PublishResult`, `RenamePayload`, `RenameResult`, `StageContract`
**Public functions:** `build_stage_request()`, `make_stage_result()`, `stage_contract()`, `stage_journal_event_type()`, `stage_payload_model()`, `stage_result_model()`, `validate_stage_data()`, `validation_error_message()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/contracts/stages.py`._
