---
file: src/mediapipeline/core/orchestration/planner.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: orchestration
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 0d2ba5319a30b9ab985820e33421718cb684241b959c8da773993f266480388c
---
# `src/mediapipeline/core/orchestration/planner.py`

**Purpose:** Dry-run PipelinePlan builder for Python-owned routing decisions.

**Public functions:** `build_pipeline_plan()`, `build_pipeline_plan_from_preset()`
**In-repo imports:** `mediapipeline.contracts.pipeline_plan`, `mediapipeline.contracts.source_media`, `mediapipeline.core.config.preset_migration`, `mediapipeline.core.config.preset_policy`, `mediapipeline.core.decide.processing_decision`, `mediapipeline.core.decide.routing`, `mediapipeline.core.decide.routing_facts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/orchestration/planner.py`._
