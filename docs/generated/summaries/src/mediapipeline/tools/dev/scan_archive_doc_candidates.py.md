---
file: src/mediapipeline/tools/dev/scan_archive_doc_candidates.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-20
last_reviewed: 2026-06-16
sha256: 430f831c221e1cc50f86b5265a8990b4748080ef690a6d7c712be8469f8b67cf
---
# `src/mediapipeline/tools/dev/scan_archive_doc_candidates.py`

**Purpose:** Dry-run scan for active documents that may be ready for archive. The scan is advisory. It does not move files. It classifies active documents and reports which active architecture/control files would need link updates before a candidate is archived.

**Public symbols:** `collect_document_paths`, `collect_reference_index`, `collect_reference_paths`, `DocumentScanResult`, `main`, `normalize_path`, `parse_args`, `Reference`, `render_json`, `render_markdown`, `scan_documents`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/scan_archive_doc_candidates.py`._
