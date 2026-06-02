---
file: app/orchestration/runner.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: orchestration
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: 31e5868bd184bba541dc1b628256afa4e1f76711031da863302a6559b5c90a5d
---
# `app/orchestration/runner.py`

**Purpose:** Single Python subprocess boundary for PowerShell stage execution.

**Classes:** `RunnerOptions`, `StageProcessResult`
**Public functions:** `resolve_powershell_path()`, `run_decide_stage()`, `run_probe_stage()`, `run_stage()`
**In-repo imports:** `app.contracts.stages`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/orchestration/runner.py`._
