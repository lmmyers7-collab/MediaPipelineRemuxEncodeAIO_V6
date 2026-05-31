---
file: app/config/rollout.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-05-30
last_reviewed: 2026-05-30
sha256: fc247154b2a962da728a5c57d36dbacb4cfa836752a248caa3ec98679b2f61a8
---
# `app/config/rollout.py`

**Purpose:** Controlled rollout helpers for the HandBrake/remux planner.

**Classes:** `PlannerComparisonRecord`, `PlannerRolloutState`, `RolloutModel`
**Public functions:** `planner_comparison_from_decision_snapshot()`, `resolve_planner_rollout_config()`
**In-repo imports:** `app.config.preset_policy`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/config/rollout.py`._
