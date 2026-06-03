---
file: app/audit/preview_policy.py
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-06-03
last_reviewed: 2026-05-28
sha256: 5d6b44cf5c642120066f73b4a53191fe5bc9afe531085d4be4a309a0db15e6b1
---
# `app/audit/preview_policy.py`

**Purpose:** Audit preview policy and result helpers.

**Public functions:** `audit_csv_read_error_result()`, `audit_duplicate_group_count()`, `audit_latest_csv_resolution_error_result()`, `audit_loader_unavailable_result()`, `audit_no_csv_report_result()`, `audit_preview_fields()`, `audit_preview_from_records()`, `audit_record_key()`, `audit_record_to_row()`, `audit_records_for_row_keys()`, `audit_report_service_unavailable_result()`, `audit_visible_records()`, `bounded_audit_limit()`
**In-repo imports:** `app.audit.ignore_manifest`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/audit/preview_policy.py`._
