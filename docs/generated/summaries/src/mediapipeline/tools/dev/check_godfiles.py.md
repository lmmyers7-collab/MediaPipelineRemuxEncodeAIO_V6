---
file: src/mediapipeline/tools/dev/check_godfiles.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 0b67448460dee6f3aaa5099e6be075a7ee47a63767e113428291d859db697c0f
---
# `src/mediapipeline/tools/dev/check_godfiles.py`

**Purpose:** Warn when source files become too large to refactor safely.

**Public symbols:** `analyze_candidate`, `analyze_candidates`, `CandidatePath`, `changed_candidates_from_status`, `collect_candidates`, `Finding`, `git_all_candidates`, `git_changed_candidates`, `git_staged_candidates`, `is_included`, `line_count`, `load_policy`, `main`, `normalize_path`, `parse_porcelain_status_line`, `PolicyFinding`, `previous_head_line_count`, `render_findings`, `render_policy_findings`, `staged_candidates_from_name_status`, `Thresholds`, `thresholds_for_path`, `validate_policy`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_godfiles.py`._
