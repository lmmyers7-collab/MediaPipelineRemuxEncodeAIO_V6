---
file: src/mediapipeline/tools/dev/check_active_doc_references.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-05
last_reviewed: 2026-06-04
sha256: 59c66ead608d63de8f1b1131f82fef93e92eb696a100db110cb24d7acd79e4f1
---
# `src/mediapipeline/tools/dev/check_active_doc_references.py`

**Purpose:** Check active Markdown references for stale moved-doc and legacy-shell names.

**Classes:** `DocFinding`
**Public functions:** `collect_active_markdown_files()`, `findings_for_files()`, `findings_for_text()`, `main()`, `missing_moved_doc_targets()`, `missing_required_active_docs()`, `normalize_path()`, `render_findings()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_active_doc_references.py`._
