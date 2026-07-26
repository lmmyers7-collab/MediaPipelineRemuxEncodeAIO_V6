---
file: src/mediapipeline/tools/dev/suggest_doc_location.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 8246e66815d19475ae505c72f6a39a4978a3867ad0795e503c0d849f59e46019
---
# `src/mediapipeline/tools/dev/suggest_doc_location.py`

**Purpose:** Suggest an active docs/ location for a proposed Markdown document. This helper is advisory. It does not create, move, or edit files. When the classification is uncertain, it exits with status 2 so a human can decide.

**Public symbols:** `existing_docs_folder`, `main`, `normalize_text`, `parse_args`, `Rule`, `score_rule`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/suggest_doc_location.py`._
