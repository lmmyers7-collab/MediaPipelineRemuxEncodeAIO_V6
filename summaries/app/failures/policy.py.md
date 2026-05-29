---
file: app/failures/policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: failures
last_modified: 2026-05-29
last_reviewed: 2026-05-28
sha256: 04f55207516d2b7a7ef2e51bb824d64a593292a186669a5aeaa82fa9f6aa3e03
---
# `app/failures/policy.py`

**Purpose:** Failure preview policy and result helpers.

**Public functions:** `bounded_failure_limit()`, `failure_json_read_error_result()`, `failure_latest_json_resolution_error_result()`, `failure_loader_unavailable_result()`, `failure_marker_service_unavailable_result()`, `failure_markers_read_error_result()`, `failure_no_json_report_result()`, `failure_preview_fields()`, `failure_preview_from_records()`, `failure_record_to_row()`, `failure_report_service_unavailable_result()`, `normalize_failure_source_kind()`
**In-repo imports:** `app.failures.retry_state`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/failures/policy.py`._
