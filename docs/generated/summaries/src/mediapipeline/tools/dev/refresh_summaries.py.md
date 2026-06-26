---
file: src/mediapipeline/tools/dev/refresh_summaries.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-26
last_reviewed: 2026-06-04
sha256: 091d81716fb8e773fdad5f8fb7d093c562807188a377e144b362b1d17997a399
---
# `src/mediapipeline/tools/dev/refresh_summaries.py`

**Purpose:** Generate per-source-file summaries under docs/generated/summaries/.

**Classes:** `OrphanSummary`, `PsSymbols`, `PySymbols`
**Public functions:** `canonical_repo_relative_posix()`, `cmd_check()`, `cmd_generate()`, `collect_sources()`, `existing_last_reviewed()`, `existing_summary_sha()`, `frontmatter_value()`, `git_changed()`, `in_scope_roots()`, `is_excluded_source_path()`, `is_refreshable_source_path()`, `is_source_file()`, `is_volatile_generated_summary_source()`, `iter_existing_summary_sources()`, `iter_known_source_files()`, `iter_source_files()`, `iter_summary_files()`, `main()`, `orphan_summaries()`, `owner_domain_for()`
**In-repo imports:** `mediapipeline.tools.dev.release_package_scope`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/refresh_summaries.py`._
