---
file: src/mediapipeline/core/decide/routing_outputs.py
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 0fdcc583c4107bdedda128c8fcef8f12a93832a5bcf2eb9f278ed199ecdc9ba7
---
# `src/mediapipeline/core/decide/routing_outputs.py`

**Purpose:** Output shaping for pure copy/remux/encode decisions.

**Public functions:** `finalize_decision()`, `planned_encode_output()`, `planned_output_summary()`, `planned_verification_result()`, `publish_requirements()`, `source_facts_for_output()`, `verification_guards()`, `verification_requirements()`
**In-repo imports:** `mediapipeline.contracts.source_media`, `mediapipeline.contracts.verification`, `mediapipeline.core.decide.encoding_rules`, `mediapipeline.core.decide.processing_decision`, `mediapipeline.core.decide.routing_facts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/decide/routing_outputs.py`._
