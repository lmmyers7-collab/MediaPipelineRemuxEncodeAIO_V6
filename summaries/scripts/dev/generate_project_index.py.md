---
file: scripts/dev/generate_project_index.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-28
last_reviewed: 2026-05-28
sha256: 5ddbba0e8f4a933be723f0c5122e59d27ae3c82693d415bccb16c5c911d3ec4f
---
# `scripts/dev/generate_project_index.py`

**Purpose:** Generate Docs/generated/PROJECT_INDEX.md and Docs/generated/DEPENDENCY_GRAPH.md from summaries/.

**Classes:** `OrphanSummaryFinding`
**Public functions:** `check_file()`, `expected_summary_path_for_file()`, `iter_summaries()`, `main()`, `orphan_summary_findings()`, `parse_first()`, `parse_frontmatter()`, `render_graph()`, `render_index()`, `render_orphan_summary_findings()`, `short_purpose()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/generate_project_index.py`._
