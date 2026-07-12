---
file: src/mediapipeline/tools/dev/generate_project_index.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-12
last_reviewed: 2026-06-04
sha256: ab322e42dacfeebee725e4acc9c72e1ea8981b773c9db6e948e47608186cd9a8
---
# `src/mediapipeline/tools/dev/generate_project_index.py`

**Purpose:** Generate docs/generated/PROJECT_INDEX.md and docs/generated/DEPENDENCY_GRAPH.md from docs/generated/summaries/.

**Classes:** `OrphanSummaryFinding`
**Public functions:** `canonical_path_sort_key()`, `check_file()`, `expected_summary_path_for_file()`, `iter_summaries()`, `main()`, `orphan_summary_findings()`, `parse_first()`, `parse_frontmatter()`, `render_graph()`, `render_index()`, `render_orphan_summary_findings()`, `short_purpose()`
**In-repo imports:** `mediapipeline.tools.dev.release_package_scope`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_project_index.py`._
