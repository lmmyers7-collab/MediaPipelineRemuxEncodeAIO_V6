---
file: app/failures/policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: failures
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: b9886a83dc7294ee3832eeeb184fce45bc28baecef611f45a88798c7dc14ba63
---
# `app/failures/policy.py`

**Purpose:** Failure preview policy and result helpers.

**Public functions:** `bounded_failure_limit()`, `failure_json_read_error_result()`, `failure_latest_json_resolution_error_result()`, `failure_loader_unavailable_result()`, `failure_marker_lookup()`, `failure_marker_service_unavailable_result()`, `failure_markers_read_error_result()`, `failure_no_json_report_result()`, `failure_preview_fields()`, `failure_preview_from_records()`, `failure_record_to_row()`, `failure_report_service_unavailable_result()`, `normalize_failure_source_kind()`
**In-repo imports:** `app.failures.retry_state`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/failures/policy.py`._
