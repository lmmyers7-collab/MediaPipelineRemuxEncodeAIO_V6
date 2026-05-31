---
file: app/observability/status_policy.py
pipeline_stage: observability
token_priority: medium
owner_domain: observability
last_modified: 2026-05-31
last_reviewed: 2026-05-28
sha256: 40f1fb91e2c8da993cdd4135526ce307b504a60d1cecb21b6b497dc8b5419567
---
# `app/observability/status_policy.py`

**Purpose:** Application status, telemetry, and progress-bar policy helpers.

**Public functions:** `application_capabilities()`, `audit_progress_bars()`, `audit_report_progress_bar()`, `bool_from_mapping()`, `float_from_mapping()`, `format_bytes()`, `int_from_mapping()`, `nullable_int_from_mapping()`, `optional_path_text()`, `pipeline_progress_bars()`, `progress_bar()`, `progress_mode()`, `progress_state_status()`, `snapshot_counts()`, `snapshot_latest_paths()`, `snapshot_progress_bars()`, `snapshot_recent_events()`, `snapshot_warnings()`, `string_list_from_mapping()`, `subtitle_progress_bars()`
**In-repo imports:** `app.telemetry.gpu_usage`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/observability/status_policy.py`._
