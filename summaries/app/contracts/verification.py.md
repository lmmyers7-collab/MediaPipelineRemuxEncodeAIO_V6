---
file: app/contracts/verification.py
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-05-30
last_reviewed: 2026-05-30
sha256: 7c2f50e79bd2cc0fc3ab4a1befba06686b28d4212915fd4ec77f9a509a0da1e9
---
# `app/contracts/verification.py`

**Purpose:** Verification and publish guard contracts for pipeline plans.

**Classes:** `OutputSizeCheck`, `VerificationGuard`, `VerificationModel`, `VerificationResult`
**Public functions:** `evaluate_output_size_check()`, `output_size_check_action_from_settings()`, `planned_output_size_check()`, `verification_result_from_size_check()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/contracts/verification.py`._
