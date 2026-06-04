---
file: app/decide/routing_outputs.py
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-06-03
last_reviewed: 2026-05-30
sha256: 16a2eedca274017431b7749487cc7fd443365dca4d8d9d343e1c6aec72ccd0f1
---
# `app/decide/routing_outputs.py`

**Purpose:** Output shaping for pure copy/remux/encode decisions.

**Public functions:** `finalize_decision()`, `planned_encode_output()`, `planned_output_summary()`, `planned_verification_result()`, `publish_requirements()`, `source_facts_for_output()`, `verification_guards()`, `verification_requirements()`
**In-repo imports:** `app.contracts.source_media`, `app.contracts.verification`, `app.decide.encoding_rules`, `app.decide.processing_decision`, `app.decide.routing_facts`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/decide/routing_outputs.py`._
