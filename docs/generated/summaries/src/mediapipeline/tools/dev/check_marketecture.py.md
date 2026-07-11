---
file: src/mediapipeline/tools/dev/check_marketecture.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 7c396f887f3fc42d2c1e26807b627ecd68c68a37acb07609f8e0a7cb37d71a20
---
# `src/mediapipeline/tools/dev/check_marketecture.py`

**Purpose:** Flag marketing buzzwords (marketecture) in docs and source.

**Classes:** `CandidatePath`, `Finding`
**Public functions:** `changed_candidates_from_status()`, `collect_candidates()`, `compile_terms()`, `findings_for_candidates()`, `findings_for_text()`, `git_all_candidates()`, `git_changed_candidates()`, `git_diff_candidates()`, `git_staged_candidates()`, `is_scannable()`, `load_exclude_globs()`, `load_include_globs()`, `load_suppression_marker()`, `load_terms()`, `main()`, `normalize_path()`, `parse_porcelain_status_line()`, `render_findings()`, `staged_candidates_from_name_status()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_marketecture.py`._
