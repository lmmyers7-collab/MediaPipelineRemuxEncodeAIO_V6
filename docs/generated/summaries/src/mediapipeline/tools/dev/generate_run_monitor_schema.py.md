---
file: src/mediapipeline/tools/dev/generate_run_monitor_schema.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-20
last_reviewed: 2026-07-16
sha256: 2302b37883842b6e5ce8b56c8a7750454468ef525f6239c37661e9ab4acb2041
---
# `src/mediapipeline/tools/dev/generate_run_monitor_schema.py`

**Purpose:** Generate Run Monitor schemas from the authoritative ``RunMonitorRecord``. The contracts artifact and PowerShell-facing mirror intentionally differ only by their consumer-specific ``$id``. Use ``--check`` in CI/pre-commit/release validation to fail when either shipped artifact is stale. Schema consumers use the committed artifacts; production runtime code never imports this developer-only generator.

**Public symbols:** `main`, `render_schema`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_run_monitor_schema.py`._
