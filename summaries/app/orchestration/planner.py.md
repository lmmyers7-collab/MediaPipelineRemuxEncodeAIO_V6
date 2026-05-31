---
file: app/orchestration/planner.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: orchestration
last_modified: 2026-05-30
last_reviewed: 2026-05-30
sha256: 1282afef50e1a64ad460baf1a73188d132ed9bd07701ded402dfc1e176324e6c
---
# `app/orchestration/planner.py`

**Purpose:** Dry-run PipelinePlan builder for Python-owned routing decisions.

**Public functions:** `build_pipeline_plan()`, `build_pipeline_plan_from_preset()`
**In-repo imports:** `app.config.preset_migration`, `app.config.preset_policy`, `app.contracts.pipeline_plan`, `app.contracts.source_media`, `app.decide.processing_decision`, `app.decide.routing`, `app.decide.routing_facts`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/orchestration/planner.py`._
