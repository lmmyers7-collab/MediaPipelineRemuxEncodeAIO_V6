---
file: src/mediapipeline/core/decide/routing_outputs.py
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-06-05
last_reviewed: 2026-06-04
sha256: 0116ff04af581c83bc186bd50774057747d3f57033ff840b53f287276cf62e61
---
# `src/mediapipeline/core/decide/routing_outputs.py`

**Purpose:** Output shaping for pure copy/remux/encode decisions.

**Public functions:** `finalize_decision()`, `planned_encode_output()`, `planned_output_summary()`, `planned_verification_result()`, `publish_requirements()`, `source_facts_for_output()`, `verification_guards()`, `verification_requirements()`
**In-repo imports:** `mediapipeline.contracts.source_media`, `mediapipeline.contracts.verification`, `mediapipeline.core.decide.encoding_rules`, `mediapipeline.core.decide.processing_decision`, `mediapipeline.core.decide.routing_facts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/decide/routing_outputs.py`._
