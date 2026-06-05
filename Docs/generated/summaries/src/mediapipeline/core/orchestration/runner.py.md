---
file: src/mediapipeline/core/orchestration/runner.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: orchestration
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: fedba51af399ad534e76435ba12eed6ab13d7409b36ffe4ccb0e9e1ed9579a63
---
# `src/mediapipeline/core/orchestration/runner.py`

**Purpose:** Single Python subprocess boundary for PowerShell stage execution.

**Classes:** `RunnerOptions`, `StageProcessResult`
**Public functions:** `resolve_powershell_path()`, `run_decide_stage()`, `run_probe_stage()`, `run_stage()`
**In-repo imports:** `mediapipeline.contracts.stages`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/orchestration/runner.py`._
