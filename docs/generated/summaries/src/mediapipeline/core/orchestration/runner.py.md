---
file: src/mediapipeline/core/orchestration/runner.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: orchestration
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 23ce090ddb61275b07d7c7c234a5f6aea33c49a4918b2a7dc6376311202da21b
---
# `src/mediapipeline/core/orchestration/runner.py`

**Purpose:** Python dispatcher for bounded Python stages and PowerShell stage execution.

**Classes:** `RunnerOptions`, `StageProcessResult`
**Public functions:** `resolve_powershell_path()`, `run_decide_stage()`, `run_ingest_stage()`, `run_probe_stage()`, `run_rename_stage()`, `run_stage()`, `run_subtitle_convert_stage()`
**In-repo imports:** `mediapipeline.contracts.stages`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/orchestration/runner.py`._
