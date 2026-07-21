---
file: src/mediapipeline/core/publish/pending_rows.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 839d370cc670d73434a40db55ccce8f346ed9edb18b281dca58565de5f217542
---
# `src/mediapipeline/core/publish/pending_rows.py`

**Purpose:** Python implementation for pending rows; exposes count_pending_publish_row_targets, count_pending_publish_rows, pending_publish_error_warning.

**Public symbols:** `count_pending_publish_row_targets`, `count_pending_publish_rows`, `pending_publish_error_warning`, `pending_publish_file_inventory_payload`, `pending_publish_inventory_progress_payload`, `pending_publish_preview_fields`, `pending_publish_preview_result`, `pending_publish_recovery_summary`, `pending_publish_retry_budget_payload`, `pending_publish_row_available_open_targets`, `pending_publish_row_dead_letter_status`, `pending_publish_row_diagnostic_severity`, `pending_publish_row_diagnostic_status`, `pending_publish_row_diagnostic_status_state`, `pending_publish_row_diagnostics`, `pending_publish_row_drain_recommendation`, `pending_publish_row_evidence_fields`, `pending_publish_row_is_recovery_blocker`, `pending_publish_row_issue_summary`, `pending_publish_row_key`, `pending_publish_row_operator_guidance`, `pending_publish_row_ready_to_drain`, `pending_publish_row_recommended_open_targets`, `pending_publish_row_recovery_action`, `pending_publish_row_recovery_class`, `pending_publish_row_retry_count`, `pending_publish_row_retry_exhausted`, `pending_publish_row_retry_limit`, `pending_publish_row_trust_fields`, `pending_publish_rows`
**In-repo imports:** `.pending_contracts`, `.pending_policy_parts.status_rules`, `.pending_policy_parts.trust_fields`, `mediapipeline.core.files.constants`, `mediapipeline.core.kernel.contracts.pending_publish`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/publish/pending_rows.py`._
