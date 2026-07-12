---
file: src/mediapipeline/tools/dev/generate_project_index.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-12
last_reviewed: 2026-06-04
sha256: 7f7357d9229b08f5f56d033bbdaff84d62807c2e419d5fffa84e3e4771bec962
---
# `src/mediapipeline/tools/dev/generate_project_index.py`

**Purpose:** Generate docs/generated/PROJECT_INDEX.md and docs/generated/DEPENDENCY_GRAPH.md from docs/generated/summaries/.

**Classes:** `OrphanSummaryFinding`
**Public functions:** `check_file()`, `expected_summary_path_for_file()`, `iter_summaries()`, `main()`, `orphan_summary_findings()`, `parse_first()`, `parse_frontmatter()`, `render_graph()`, `render_index()`, `render_orphan_summary_findings()`, `short_purpose()`
**In-repo imports:** `mediapipeline.tools.dev.release_package_scope`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_project_index.py`._
