---
file: src/mediapipeline/tools/dev/check_godfiles.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 6ed4f35ef3117e6441b5d57c343b9a62fe002f1f0cffa86b4b201eff0cb017cd
---
# `src/mediapipeline/tools/dev/check_godfiles.py`

**Purpose:** Warn when source files become too large to refactor safely.

**Classes:** `CandidatePath`, `Finding`, `PolicyFinding`, `Thresholds`
**Public functions:** `analyze_candidate()`, `analyze_candidates()`, `changed_candidates_from_status()`, `collect_candidates()`, `git_all_candidates()`, `git_changed_candidates()`, `git_staged_candidates()`, `is_included()`, `line_count()`, `load_policy()`, `main()`, `normalize_path()`, `parse_porcelain_status_line()`, `previous_head_line_count()`, `render_findings()`, `render_policy_findings()`, `staged_candidates_from_name_status()`, `thresholds_for_path()`, `validate_policy()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_godfiles.py`._
