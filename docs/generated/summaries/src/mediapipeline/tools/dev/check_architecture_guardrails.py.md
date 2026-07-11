---
file: src/mediapipeline/tools/dev/check_architecture_guardrails.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: f973e6106ce107d731fa2034223613c907657fb4ab2e8817760c334925a1b296
---
# `src/mediapipeline/tools/dev/check_architecture_guardrails.py`

**Purpose:** Fail fast on new files that violate the architecture-overhaul layout.

**Classes:** `ChangedPath`, `Finding`
**Public functions:** `collect_candidates()`, `creation_candidates_from_status()`, `findings_for_path()`, `findings_for_paths()`, `git_staged_candidates()`, `git_working_tree_candidates()`, `is_creation_status()`, `main()`, `normalize_path()`, `parse_porcelain_status_line()`, `render_findings()`, `staged_creation_candidates()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_architecture_guardrails.py`._
