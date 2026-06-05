---
file: src/mediapipeline/tools/dev/ai_guardrail.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 7ce3ea77eba966960dd28a690cb2b5eab1c5133e38ed2310e825b09f154b681b
---
# `src/mediapipeline/tools/dev/ai_guardrail.py`

**Purpose:** AI preflight/postflight guardrail checks for repository safety work.

**Classes:** `CheckResult`, `CommandCheck`
**Public functions:** `build_check_plan()`, `git_status_paths()`, `git_status_summary()`, `main()`, `risk_classification()`, `run_command_check()`, `run_guardrail()`
**In-repo imports:** `mediapipeline.tools.dev`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/ai_guardrail.py`._
