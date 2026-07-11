---
file: src/mediapipeline/core/failures/policy_orchestration.py
pipeline_stage: orchestration
token_priority: medium
owner_domain: failures
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 1f116b3ce7c2e4614446e9f146792a3175653297e33c39bce98b4a98f683becb
---
# `src/mediapipeline/core/failures/policy_orchestration.py`

**Purpose:** Failure preview policy and result helpers.

**Public functions:** `failure_json_read_error_result()`, `failure_latest_json_resolution_error_result()`, `failure_loader_unavailable_result()`, `failure_marker_service_unavailable_result()`, `failure_markers_read_error_result()`, `failure_no_json_report_result()`, `failure_preview_fields()`, `failure_preview_from_records()`, `failure_record_to_row()`, `failure_report_service_unavailable_result()`
**In-repo imports:** `mediapipeline.core.failures.contracts`, `mediapipeline.core.failures.policy_evidence`, `mediapipeline.core.failures.policy_markers`, `mediapipeline.core.failures.policy_resolution`, `mediapipeline.core.failures.policy_support`, `mediapipeline.core.failures.retry_state`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/failures/policy_orchestration.py`._
