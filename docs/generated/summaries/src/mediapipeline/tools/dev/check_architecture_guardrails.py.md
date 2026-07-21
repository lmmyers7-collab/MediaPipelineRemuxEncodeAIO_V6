---
file: src/mediapipeline/tools/dev/check_architecture_guardrails.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 78dca764c4432af6b503b731def34b41a305b88bfd9c3703b85201aa5c206ab6
---
# `src/mediapipeline/tools/dev/check_architecture_guardrails.py`

**Purpose:** Fail fast on new files that violate the architecture-overhaul layout. The current tree still contains grandfathered legacy files. This guard is therefore creation-only by default: it checks added, renamed/copied, and untracked paths from the working tree, while allowing edits to existing legacy files until their owning domain is migrated.

**Public symbols:** `ChangedPath`, `collect_candidates`, `creation_candidates_from_status`, `Finding`, `findings_for_path`, `findings_for_paths`, `git_staged_candidates`, `git_working_tree_candidates`, `is_creation_status`, `main`, `normalize_path`, `parse_porcelain_status_line`, `render_findings`, `staged_creation_candidates`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_architecture_guardrails.py`._
