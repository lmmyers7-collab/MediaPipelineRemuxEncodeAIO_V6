---
file: src/mediapipeline/tools/dev/repository_audit_ledger.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-23
last_reviewed: 2026-07-20
sha256: e300af889b427f11ce53e7771f1effc5c80c7843c2cc7c6cca47d215eecde22d
---
# `src/mediapipeline/tools/dev/repository_audit_ledger.py`

**Purpose:** Build and validate the exhaustive repository-audit coverage ledger. The ledger deliberately starts every reviewable file in a non-terminal state. Automated inventory is evidence about presence, hashes, ownership, and size; it is not evidence that a human or agent semantically reviewed the file.

**Public symbols:** `atomic_write_text`, `atomic_write_text_set`, `audit_owned_untracked_paths`, `baseline_markdown`, `bool_path_marker`, `build_rows`, `canonical_path`, `check_outputs`, `classification_for`, `csv_text`, `current_content_findings`, `error_ledger_markdown`, `error_record_findings`, `evidence_ledger_findings`, `expected_coverage_paths`, `fallback_owner_and_layer`, `fallback_risk_tier`, `finding_record_findings`, `finding_root_cause_fingerprint`, `findings_markdown`, `git_blob_bytes`, `git_blob_map`, `git_tracked_paths`, `git_untracked_paths`, `independent_review_completion_findings`, `is_canonical_reviewer_identity`, `is_historical_finding_id`, `is_probably_text`, `is_probably_text_bytes`, `jsonl_text`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/repository_audit_ledger.py`._
