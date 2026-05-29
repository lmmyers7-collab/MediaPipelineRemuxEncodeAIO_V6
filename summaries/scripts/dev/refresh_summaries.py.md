---
file: scripts/dev/refresh_summaries.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-29
last_reviewed: 2026-05-28
sha256: f8c99de44d59514a8e91a8800d55c3c86f4035da3f01f78b0c56135bbda424a2
---
# `scripts/dev/refresh_summaries.py`

**Purpose:** Generate per-source-file summaries under summaries/.

**Classes:** `OrphanSummary`, `PsSymbols`, `PySymbols`
**Public functions:** `cmd_check()`, `cmd_generate()`, `collect_sources()`, `existing_last_reviewed()`, `existing_summary_sha()`, `frontmatter_value()`, `git_changed()`, `in_scope_roots()`, `is_source_file()`, `iter_source_files()`, `iter_summary_files()`, `main()`, `orphan_summaries()`, `owner_domain_for()`, `parse_powershell()`, `parse_python()`, `pipeline_stage_for()`, `prune_orphan_summaries()`, `render_summary()`, `sha256_of()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/refresh_summaries.py`._
