---
file: scripts/lint-naming.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-28
last_reviewed: 2026-05-28
sha256: e46ce494d28e03afc6907159753d9ed70950cdbb78290718f426e4cffa34cd1f
---
# `scripts/lint-naming.py`

**Purpose:** Fail on new filenames that recreate deprecated overhaul-era patterns.

**Classes:** `ChangedPath`, `NamingFinding`
**Public functions:** `collect_candidates()`, `creation_candidates_from_name_status()`, `creation_candidates_from_status()`, `findings_for_path()`, `findings_for_paths()`, `git_diff_candidates()`, `git_staged_candidates()`, `git_working_tree_candidates()`, `is_creation_status()`, `main()`, `normalize_path()`, `parse_porcelain_status_line()`, `render_findings()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/lint-naming.py`._
