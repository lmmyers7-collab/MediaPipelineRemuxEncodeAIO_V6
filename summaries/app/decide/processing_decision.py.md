---
file: app/decide/processing_decision.py
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-06-03
last_reviewed: 2026-05-30
sha256: 991476ed7e072dacab628da93168f5b203333e80257d60f725b1c35567522328
---
# `app/decide/processing_decision.py`

**Purpose:** Strict DTOs for Python-owned copy/remux/encode decisions.

**Classes:** `AudioStreamDecision`, `DecisionModel`, `DecisionReason`, `DecisionRequirement`, `PlannedAudioEncodeOutput`, `PlannedEncodeOutput`, `PlannedSubtitleEncodeOutput`, `PlannedVideoEncodeOutput`, `ProcessingDecision`, `StreamActionSet`, `SubtitleStreamDecision`, `VideoStreamDecision`
**Public functions:** `decision_policy_from_mapping()`, `derive_route_summary()`
**In-repo imports:** `app.contracts.decision_policy`, `app.contracts.verification`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/decide/processing_decision.py`._
