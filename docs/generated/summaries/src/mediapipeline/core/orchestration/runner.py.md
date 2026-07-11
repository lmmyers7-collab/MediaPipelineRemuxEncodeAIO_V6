---
file: src/mediapipeline/core/orchestration/runner.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: orchestration
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 7e2325d1fc6daa9e4f3de99c39cc3146001b88c13afdce7355faff3793194dab
---
# `src/mediapipeline/core/orchestration/runner.py`

**Purpose:** Single Python subprocess boundary for PowerShell stage execution.

**Classes:** `RunnerOptions`, `StageProcessResult`
**Public functions:** `resolve_powershell_path()`, `run_decide_stage()`, `run_ingest_stage()`, `run_probe_stage()`, `run_stage()`
**In-repo imports:** `mediapipeline.contracts.stages`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/orchestration/runner.py`._
