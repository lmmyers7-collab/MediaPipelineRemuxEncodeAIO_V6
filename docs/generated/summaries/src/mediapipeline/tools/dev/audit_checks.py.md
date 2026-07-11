---
file: src/mediapipeline/tools/dev/audit_checks.py
pipeline_stage: observability
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-10
last_reviewed: 2026-07-01
sha256: 909dca292301e8710aa31fc966b9cfab592c2f2c3c2c3fbf78fa52ac11b92c5e
---
# `src/mediapipeline/tools/dev/audit_checks.py`

**Purpose:** Shared audit/check definitions for local hooks, CI, and release gates.

**Classes:** `AuditCheck`, `AuditCheckResult`
**Public functions:** `check_to_dict()`, `command_for_check()`, `main()`, `result_to_dict()`, `run_check()`, `run_suite()`, `subprocess_environment()`, `suite_checks()`, `suite_names()`, `suite_to_dict()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/audit_checks.py`._
