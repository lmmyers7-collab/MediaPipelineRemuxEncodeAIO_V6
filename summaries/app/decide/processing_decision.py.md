---
file: app/decide/processing_decision.py
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-05-30
last_reviewed: 2026-05-30
sha256: 9912316f6b1027f8bc1ca1289da882980b3411beff794faf6201fa613324368b
---
# `app/decide/processing_decision.py`

**Purpose:** Strict DTOs for Python-owned copy/remux/encode decisions.

**Classes:** `AudioStreamDecision`, `DecisionModel`, `DecisionReason`, `DecisionRequirement`, `EffectiveDecisionPolicy`, `PlannedAudioEncodeOutput`, `PlannedEncodeOutput`, `PlannedSubtitleEncodeOutput`, `PlannedVideoEncodeOutput`, `ProcessingDecision`, `StreamActionSet`, `SubtitleStreamDecision`, `VideoStreamDecision`
**Public functions:** `decision_policy_from_mapping()`, `derive_route_summary()`
**In-repo imports:** `app.contracts.verification`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/decide/processing_decision.py`._
