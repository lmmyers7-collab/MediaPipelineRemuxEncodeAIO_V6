---
file: app/contracts/stages.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-05-29
last_reviewed: 2026-05-28
sha256: 42f92514475db7fa036d6aa20fa2bd957b4f48801aa7feab5b0aa25d57bae02a
---
# `app/contracts/stages.py`

**Purpose:** Canonical Pydantic contracts for pipeline stage execution.

**Classes:** `AudioMixPayload`, `AudioMixResult`, `DecidePayload`, `DecideResult`, `DrainPayload`, `DrainResult`, `IngestPayload`, `IngestResult`, `ProbePayload`, `ProbeResult`, `PublishPayload`, `PublishResult`, `RenamePayload`, `RenameResult`, `StageContract`
**Public functions:** `build_stage_request()`, `make_stage_result()`, `stage_contract()`, `stage_journal_event_type()`, `stage_payload_model()`, `stage_result_model()`, `validate_stage_data()`, `validation_error_message()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/contracts/stages.py`._
