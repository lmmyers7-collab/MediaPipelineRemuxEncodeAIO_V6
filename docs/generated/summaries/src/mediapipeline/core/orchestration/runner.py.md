---
file: src/mediapipeline/core/orchestration/runner.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: orchestration
last_modified: 2026-06-24
last_reviewed: 2026-06-04
sha256: 4da361996b9881aa0ad087375035c28ad6ea9ff4154008baa2811c2f806efe8f
---
# `src/mediapipeline/core/orchestration/runner.py`

**Purpose:** Single Python subprocess boundary for PowerShell stage execution.

**Classes:** `RunnerOptions`, `StageProcessResult`
**Public functions:** `resolve_powershell_path()`, `run_decide_stage()`, `run_ingest_stage()`, `run_probe_stage()`, `run_stage()`
**In-repo imports:** `mediapipeline.contracts.stages`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/orchestration/runner.py`._
