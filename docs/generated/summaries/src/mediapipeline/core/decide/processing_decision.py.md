---
file: src/mediapipeline/core/decide/processing_decision.py
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 14621ab4b1bcb9f7859d025e4733480e16fc6f77aa385fe5394f435e30d49e61
---
# `src/mediapipeline/core/decide/processing_decision.py`

**Purpose:** Strict DTOs for Python-owned copy/remux/encode decisions.

**Classes:** `AudioStreamDecision`, `DecisionModel`, `DecisionReason`, `DecisionRequirement`, `PlannedAudioEncodeOutput`, `PlannedEncodeOutput`, `PlannedSubtitleEncodeOutput`, `PlannedVideoEncodeOutput`, `ProcessingDecision`, `StreamActionSet`, `SubtitleStreamDecision`, `VideoStreamDecision`
**Public functions:** `decision_policy_from_mapping()`, `derive_route_summary()`
**In-repo imports:** `mediapipeline.contracts.decision_policy`, `mediapipeline.contracts.verification`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/decide/processing_decision.py`._
