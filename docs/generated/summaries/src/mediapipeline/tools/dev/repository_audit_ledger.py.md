---
file: src/mediapipeline/tools/dev/repository_audit_ledger.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-20
last_reviewed: 2026-07-20
sha256: a77c3d49abc19da3d1af67c0a85e3a2ccf931af696729cfae1630b62d02b6609
---
# `src/mediapipeline/tools/dev/repository_audit_ledger.py`

**Purpose:** Build and validate the exhaustive repository-audit coverage ledger. The ledger deliberately starts every reviewable file in a non-terminal state. Automated inventory is evidence about presence, hashes, ownership, and size; it is not evidence that a human or agent semantically reviewed the file.

**Public symbols:** `audit_owned_untracked_paths`, `baseline_markdown`, `bool_path_marker`, `build_rows`, `canonical_path`, `check_outputs`, `classification_for`, `csv_text`, `current_content_findings`, `error_ledger_markdown`, `error_record_findings`, `fallback_owner_and_layer`, `fallback_risk_tier`, `finding_record_findings`, `findings_markdown`, `git_blob_map`, `git_tracked_paths`, `git_untracked_paths`, `is_probably_text`, `jsonl_text`, `load_error_fragments`, `load_existing_rows`, `load_finding_fragments`, `load_project_index`, `load_review_fragments`, `load_rows`, `main`, `merge_error_ledgers`, `merge_finding_ledgers`, `merge_review_ledgers`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/repository_audit_ledger.py`._
