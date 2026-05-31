---
file: app/decide/routing_outputs.py
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-05-30
last_reviewed: 2026-05-30
sha256: 9899fda4161a20bd2531084a8954cdaab34bfd82964da13b889202618d22f2d7
---
# `app/decide/routing_outputs.py`

**Purpose:** Output shaping for pure copy/remux/encode decisions.

**Public functions:** `finalize_decision()`, `planned_encode_output()`, `planned_output_summary()`, `planned_verification_result()`, `publish_requirements()`, `source_facts_for_output()`, `verification_guards()`, `verification_requirements()`
**In-repo imports:** `app.contracts.source_media`, `app.contracts.verification`, `app.decide.encoding_rules`, `app.decide.processing_decision`, `app.decide.routing_facts`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/decide/routing_outputs.py`._
