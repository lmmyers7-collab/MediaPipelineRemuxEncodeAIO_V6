---
file: src/mediapipeline/tools/lint_naming.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 88e9fa2661cadae5249e7d298f691f1f6b211d210fd523dc0cb56e1c5b5ce710
---
# `src/mediapipeline/tools/lint_naming.py`

**Purpose:** Fail on new filenames that recreate deprecated overhaul-era patterns.

**Classes:** `ChangedPath`, `NamingFinding`
**Public functions:** `collect_candidates()`, `creation_candidates_from_name_status()`, `creation_candidates_from_status()`, `findings_for_path()`, `findings_for_paths()`, `git_diff_candidates()`, `git_staged_candidates()`, `git_working_tree_candidates()`, `is_creation_status()`, `main()`, `normalize_path()`, `parse_porcelain_status_line()`, `render_findings()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/lint_naming.py`._
