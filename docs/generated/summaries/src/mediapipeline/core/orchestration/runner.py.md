---
file: src/mediapipeline/core/orchestration/runner.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: orchestration
token_priority: medium
owner_domain: orchestration
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 23ce090ddb61275b07d7c7c234a5f6aea33c49a4918b2a7dc6376311202da21b
---
# `src/mediapipeline/core/orchestration/runner.py`

**Purpose:** Python dispatcher for bounded Python stages and PowerShell stage execution.

**Public symbols:** `resolve_powershell_path`, `run_decide_stage`, `run_ingest_stage`, `run_probe_stage`, `run_rename_stage`, `run_stage`, `run_subtitle_convert_stage`, `RunnerOptions`, `StageProcessResult`
**In-repo imports:** `mediapipeline.contracts.stages`, `mediapipeline.tools.paths`
**State/config identifiers:** `mediapipeline.core.storage.db`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/orchestration/runner.py`._
