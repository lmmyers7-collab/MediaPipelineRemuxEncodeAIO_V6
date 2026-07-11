---
file: src/mediapipeline/tools/dev/check_active_doc_references.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: b0723427c22b832f05e321d9a46e253bf971547aae8d9889cd49395a5e8ef2b7
---
# `src/mediapipeline/tools/dev/check_active_doc_references.py`

**Purpose:** Check active Markdown references for stale moved-doc and legacy-shell names.

**Classes:** `DocFinding`
**Public functions:** `collect_active_markdown_files()`, `findings_for_files()`, `findings_for_text()`, `main()`, `missing_moved_doc_targets()`, `missing_required_active_docs()`, `normalize_path()`, `render_findings()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_active_doc_references.py`._
