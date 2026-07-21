---
file: src/mediapipeline/tools/dev/check_marketecture.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 7c396f887f3fc42d2c1e26807b627ecd68c68a37acb07609f8e0a7cb37d71a20
---
# `src/mediapipeline/tools/dev/check_marketecture.py`

**Purpose:** Flag marketing buzzwords (marketecture) in docs and source. Keeps project language concrete by failing on clear marketing fluff such as "world-class", "synergy", or "cutting-edge". Ambiguous technical words (robust, leverage, scalable, first-class) are deliberately not listed to avoid false positives. Suppress a justified single line with the inline marker "allow-marketecture". By default this scans the content of changed files in the working tree, so it never blocks on pre-existing wording in files the current task did not touch. Use --all for a full-repository audit, --staged from pre-commit, --git-diff <base> in CI, or --paths in tests.

**Public symbols:** `CandidatePath`, `changed_candidates_from_status`, `collect_candidates`, `compile_terms`, `Finding`, `findings_for_candidates`, `findings_for_text`, `git_all_candidates`, `git_changed_candidates`, `git_diff_candidates`, `git_staged_candidates`, `is_scannable`, `load_exclude_globs`, `load_include_globs`, `load_suppression_marker`, `load_terms`, `main`, `normalize_path`, `parse_porcelain_status_line`, `render_findings`, `staged_candidates_from_name_status`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_marketecture.py`._
