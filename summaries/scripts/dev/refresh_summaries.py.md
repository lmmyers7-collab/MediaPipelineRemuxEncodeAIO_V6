---
file: scripts/dev/refresh_summaries.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-30
last_reviewed: 2026-05-28
sha256: 810ea981113b308c734f5e4bae921c491f922cd8771ff5f9ad045f10e46ebdf8
---
# `scripts/dev/refresh_summaries.py`

**Purpose:** Generate per-source-file summaries under summaries/.

**Classes:** `OrphanSummary`, `PsSymbols`, `PySymbols`
**Public functions:** `cmd_check()`, `cmd_generate()`, `collect_sources()`, `existing_last_reviewed()`, `existing_summary_sha()`, `frontmatter_value()`, `git_changed()`, `in_scope_roots()`, `is_source_file()`, `iter_existing_summary_sources()`, `iter_known_source_files()`, `iter_source_files()`, `iter_summary_files()`, `main()`, `orphan_summaries()`, `owner_domain_for()`, `parse_powershell()`, `parse_python()`, `pipeline_stage_for()`, `prune_orphan_summaries()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/refresh_summaries.py`._
