---
file: scripts/dev/check_godfiles.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-29
last_reviewed: 2026-05-29
sha256: d4c11078820afe19bc7ea7ee2b7a180d00fd8cbef7171152556bbaa3a9bbc26c
---
# `scripts/dev/check_godfiles.py`

**Purpose:** Warn when source files become too large to refactor safely.

**Classes:** `CandidatePath`, `Finding`, `PolicyFinding`, `Thresholds`
**Public functions:** `analyze_candidate()`, `analyze_candidates()`, `changed_candidates_from_status()`, `collect_candidates()`, `git_all_candidates()`, `git_changed_candidates()`, `git_staged_candidates()`, `is_included()`, `line_count()`, `load_policy()`, `main()`, `normalize_path()`, `parse_porcelain_status_line()`, `previous_head_line_count()`, `render_findings()`, `render_policy_findings()`, `staged_candidates_from_name_status()`, `thresholds_for_path()`, `validate_policy()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/check_godfiles.py`._
