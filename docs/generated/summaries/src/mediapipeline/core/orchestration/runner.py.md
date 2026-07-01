---
file: src/mediapipeline/core/orchestration/runner.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: orchestration
last_modified: 2026-06-30
last_reviewed: 2026-06-04
sha256: ed9c4821ae3c1b9eb076adf8e131d2966487b867ac695afc89ea7339876d27e9
---
# `src/mediapipeline/core/orchestration/runner.py`

**Purpose:** Single Python subprocess boundary for PowerShell stage execution.

**Classes:** `RunnerOptions`, `StageProcessResult`
**Public functions:** `resolve_powershell_path()`, `run_decide_stage()`, `run_ingest_stage()`, `run_probe_stage()`, `run_stage()`
**In-repo imports:** `mediapipeline.contracts.stages`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/orchestration/runner.py`._
