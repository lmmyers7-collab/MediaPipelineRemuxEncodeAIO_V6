---
file: scripts/dev/refresh_summaries.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-28
last_reviewed: 2026-05-28
sha256: e52b75e0158f3e2966c1920aabadc7ed2b352b73eacb8b9bfd17572853201b54
---
# `scripts/dev/refresh_summaries.py`

**Purpose:** Generate per-source-file summaries under summaries/.

**Classes:** `PsSymbols`, `PySymbols`
**Public functions:** `cmd_check()`, `cmd_generate()`, `collect_sources()`, `existing_last_reviewed()`, `existing_summary_sha()`, `git_changed()`, `in_scope_roots()`, `is_source_file()`, `iter_source_files()`, `main()`, `owner_domain_for()`, `parse_powershell()`, `parse_python()`, `pipeline_stage_for()`, `render_summary()`, `sha256_of()`, `token_priority_for()`, `write_summary()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/refresh_summaries.py`._
