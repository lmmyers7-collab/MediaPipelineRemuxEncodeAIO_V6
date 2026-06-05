---
file: src/mediapipeline/tools/dev/refresh_summaries.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: e5e13621d0af0408b13b7e5232eb5e6831795be35765abd3caf75532593d7b72
---
# `src/mediapipeline/tools/dev/refresh_summaries.py`

**Purpose:** Generate per-source-file summaries under docs/generated/summaries/.

**Classes:** `OrphanSummary`, `PsSymbols`, `PySymbols`
**Public functions:** `cmd_check()`, `cmd_generate()`, `collect_sources()`, `existing_last_reviewed()`, `existing_summary_sha()`, `frontmatter_value()`, `git_changed()`, `in_scope_roots()`, `is_excluded_source_path()`, `is_refreshable_source_path()`, `is_source_file()`, `is_volatile_generated_summary_source()`, `iter_existing_summary_sources()`, `iter_known_source_files()`, `iter_source_files()`, `iter_summary_files()`, `main()`, `orphan_summaries()`, `owner_domain_for()`, `parse_powershell()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/refresh_summaries.py`._
