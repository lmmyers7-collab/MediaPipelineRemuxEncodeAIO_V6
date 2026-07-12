---
file: src/mediapipeline/tools/dev/ai_guardrail.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 05bdeb80e354a6f41ea5df9abf573ac3e3372c4e249092193870659ddf31f2e9
---
# `src/mediapipeline/tools/dev/ai_guardrail.py`

**Purpose:** AI preflight/postflight guardrail checks for repository safety work.

**Classes:** `CheckResult`, `CommandCheck`
**Public functions:** `build_check_plan()`, `git_status_paths()`, `git_status_summary()`, `main()`, `risk_classification()`, `run_command_check()`, `run_guardrail()`
**In-repo imports:** `mediapipeline.tools.dev`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/ai_guardrail.py`._
