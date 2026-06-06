---
file: src/mediapipeline/core/failures/policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: failures
last_modified: 2026-06-05
last_reviewed: 2026-06-04
sha256: c7a1013537b69333bf19b402630174043aed01a7f45faab36a315933989a0ba6
---
# `src/mediapipeline/core/failures/policy.py`

**Purpose:** Failure preview policy and result helpers.

**Public functions:** `bounded_failure_limit()`, `failure_json_read_error_result()`, `failure_latest_json_resolution_error_result()`, `failure_loader_unavailable_result()`, `failure_marker_lookup()`, `failure_marker_service_unavailable_result()`, `failure_markers_read_error_result()`, `failure_no_json_report_result()`, `failure_preview_fields()`, `failure_preview_from_records()`, `failure_record_to_row()`, `failure_report_service_unavailable_result()`, `normalize_failure_source_kind()`
**In-repo imports:** `mediapipeline.core.failures.retry_state`, `mediapipeline.desktop.models`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/failures/policy.py`._
