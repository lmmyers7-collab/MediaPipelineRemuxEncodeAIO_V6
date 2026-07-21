---
file: src/mediapipeline/tools/dev/refresh_summaries.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 1adfa425f599a2f2df55e31c615dd57985d867e3935e19d4b35d6da203ed9260
---
# `src/mediapipeline/tools/dev/refresh_summaries.py`

**Purpose:** Generate per-source-file summaries under docs/generated/summaries/. One summary file per source file in the configured roots, plus existing summary records whose source files still exist. Summaries carry YAML frontmatter (file path, sha256, last_modified, token_priority, owner_domain) and a short Markdown body listing module purpose plus public symbols when the file type can be parsed cheaply. Modes: --all Regenerate summaries for every in-scope source file. --changed Regenerate only for files changed vs HEAD. --staged Regenerate only for files staged for commit (use in pre-commit hook). --check Exit 1 if any summary's recorded sha256 differs from the source file. Print stale paths. --paths PATH ... Regenerate the named paths (relative to repo root). The script avoids any third-party dependency; stdlib only. PowerShell parsing is regex-based and intentionally shallow.

**Public symbols:** `canonical_repo_relative_posix`, `cmd_check`, `cmd_generate`, `collect_sources`, `existing_generator_fingerprint`, `existing_last_reviewed`, `existing_summary_schema`, `existing_summary_sha`, `frontmatter_value`, `git_changed`, `in_scope_roots`, `is_excluded_source_path`, `is_refreshable_source_path`, `is_source_file`, `is_volatile_generated_summary_source`, `iter_existing_summary_sources`, `iter_known_source_files`, `iter_source_files`, `iter_summary_files`, `main`, `orphan_summaries`, `OrphanSummary`, `owner_domain_for`, `parse_powershell`, `parse_python`, `pipeline_stage_for`, `prune_orphan_summaries`, `PsSymbols`, `PySymbols`, `render_summary`
**In-repo imports:** `mediapipeline.tools.dev.context_extractors`, `mediapipeline.tools.dev.release_package_scope`, `mediapipeline.tools.paths`
**State/config identifiers:** `config.v1.schema.json`, `MediaPipeline_config_template.psd1`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/refresh_summaries.py`._
