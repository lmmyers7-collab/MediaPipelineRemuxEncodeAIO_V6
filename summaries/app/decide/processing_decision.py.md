---
file: app/decide/processing_decision.py
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-05-31
last_reviewed: 2026-05-30
sha256: 1746ec22811144e937561f19bb3b736cd71d7ce73ec152f4c226422e72288c55
---
# `app/decide/processing_decision.py`

**Purpose:** Strict DTOs for Python-owned copy/remux/encode decisions.

**Classes:** `AudioStreamDecision`, `DecisionModel`, `DecisionReason`, `DecisionRequirement`, `PlannedAudioEncodeOutput`, `PlannedEncodeOutput`, `PlannedSubtitleEncodeOutput`, `PlannedVideoEncodeOutput`, `ProcessingDecision`, `StreamActionSet`, `SubtitleStreamDecision`, `VideoStreamDecision`
**Public functions:** `decision_policy_from_mapping()`, `derive_route_summary()`
**In-repo imports:** `app.contracts.decision_policy`, `app.contracts.verification`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/decide/processing_decision.py`._
