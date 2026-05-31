---
file: app/config/settings_patch_policy.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-05-31
last_reviewed: 2026-05-28
sha256: e8d56a9c2b726794f9d17072cca6fca753e3789952c825d09022c8a3c307dbc7
---
# `app/config/settings_patch_policy.py`

**Purpose:** Settings patch preview/save policy.

**Public functions:** `settings_diff_truncated()`, `settings_patch_changes_from_request()`, `settings_patch_missing_changes_result()`, `settings_patch_preview_message()`, `settings_patch_preview_progress_payload()`, `settings_patch_preview_result()`, `settings_patch_remove_keys_from_request()`, `settings_patch_remove_keys_type_error_result()`, `settings_patch_severity()`, `settings_save_busy_result()`, `settings_save_confirmation_required_result()`, `settings_save_exception_result()`, `settings_save_no_changes_result()`, `settings_save_progress_bar()`, `settings_save_progress_payload()`, `settings_save_progress_step_status_counts()`, `settings_save_service_unavailable_result()`, `settings_save_success_result()`, `settings_save_validation_error_result()`, `settings_save_written_progress_payload()`
**In-repo imports:** `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/config/settings_patch_policy.py`._
