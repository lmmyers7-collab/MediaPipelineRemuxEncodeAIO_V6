---
file: src/mediapipeline/core/failures/policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: failures
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: c9afae5af0393a571acc2c59dadc38e87d33046480345f82f4543ca20f033e2a
---
# `src/mediapipeline/core/failures/policy.py`

**Purpose:** Failure preview policy and result helpers.

**Public functions:** `allowed_failure_open_targets_text()`, `bounded_failure_limit()`, `failure_json_read_error_result()`, `failure_latest_json_resolution_error_result()`, `failure_loader_unavailable_result()`, `failure_marker_lookup()`, `failure_marker_service_unavailable_result()`, `failure_markers_read_error_result()`, `failure_no_json_report_result()`, `failure_open_path()`, `failure_open_target_label()`, `failure_preview_fields()`, `failure_preview_from_records()`, `failure_record_to_row()`, `failure_report_service_unavailable_result()`, `normalize_failure_open_target()`, `normalize_failure_source_kind()`
**In-repo imports:** `mediapipeline.core.failures.contracts`, `mediapipeline.core.failures.retry_state`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/failures/policy.py`._
