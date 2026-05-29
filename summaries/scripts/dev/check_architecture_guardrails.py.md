---
file: scripts/dev/check_architecture_guardrails.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-29
last_reviewed: 2026-05-28
sha256: a7c2bacda8540a3529870e9fc6460a4e9b1a97ea92c2a26740fcb15f0160facf
---
# `scripts/dev/check_architecture_guardrails.py`

**Purpose:** Fail fast on new files that violate the architecture-overhaul layout.

**Classes:** `ChangedPath`, `Finding`
**Public functions:** `collect_candidates()`, `creation_candidates_from_status()`, `findings_for_path()`, `findings_for_paths()`, `git_staged_candidates()`, `git_working_tree_candidates()`, `is_creation_status()`, `main()`, `normalize_path()`, `parse_porcelain_status_line()`, `render_findings()`, `staged_creation_candidates()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/check_architecture_guardrails.py`._
