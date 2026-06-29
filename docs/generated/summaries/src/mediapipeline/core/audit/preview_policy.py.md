---
file: src/mediapipeline/core/audit/preview_policy.py
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-06-28
last_reviewed: 2026-06-04
sha256: 357f6778348a86842df76d3b65aabc4dfe45e8af313566c6266070d9368f2755
---
# `src/mediapipeline/core/audit/preview_policy.py`

**Purpose:** Audit preview policy and result helpers.

**Public functions:** `audit_csv_read_error_result()`, `audit_duplicate_group_count()`, `audit_latest_csv_resolution_error_result()`, `audit_loader_unavailable_result()`, `audit_no_csv_report_result()`, `audit_preview_fields()`, `audit_preview_from_records()`, `audit_record_key()`, `audit_record_to_row()`, `audit_records_for_row_keys()`, `audit_report_service_unavailable_result()`, `audit_visible_records()`, `bounded_audit_limit()`
**In-repo imports:** `mediapipeline.core.audit.ignore_manifest`, `mediapipeline.desktop.models`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/audit/preview_policy.py`._
