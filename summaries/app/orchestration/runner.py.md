---
file: app/orchestration/runner.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: orchestration
last_modified: 2026-05-28
last_reviewed: 2026-05-28
sha256: c1ca3645331eb7b468f981aea481b403452670fccf9ff37df0315fe19af4e65f
---
# `app/orchestration/runner.py`

**Purpose:** Single Python subprocess boundary for PowerShell stage execution.

**Classes:** `RunnerOptions`, `StageProcessResult`
**Public functions:** `resolve_powershell_path()`, `run_decide_stage()`, `run_probe_stage()`, `run_stage()`
**In-repo imports:** `app.contracts.stages`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/orchestration/runner.py`._
