---
file: scripts/dev/check_marketecture.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-30
last_reviewed: 2026-05-30
sha256: e1d02e17b49533e6dbcddb434f89e5f4841637aa84ca78fb6d52258a52a7f394
---
# `scripts/dev/check_marketecture.py`

**Purpose:** Flag marketing buzzwords (marketecture) in docs and source.

**Classes:** `CandidatePath`, `Finding`
**Public functions:** `changed_candidates_from_status()`, `collect_candidates()`, `compile_terms()`, `findings_for_candidates()`, `findings_for_text()`, `git_all_candidates()`, `git_changed_candidates()`, `git_diff_candidates()`, `git_staged_candidates()`, `is_scannable()`, `load_exclude_globs()`, `load_include_globs()`, `load_suppression_marker()`, `load_terms()`, `main()`, `normalize_path()`, `parse_porcelain_status_line()`, `render_findings()`, `staged_candidates_from_name_status()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/check_marketecture.py`._
