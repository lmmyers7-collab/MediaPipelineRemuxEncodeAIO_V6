---
file: app/rename/policy.py
pipeline_stage: rename
token_priority: medium
owner_domain: rename
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: fb4d15c4382772d94d7ead9b568bfed7e9fd9c6827cd89d03cf09cb441e7d3ce
---
# `app/rename/policy.py`

**Purpose:** Rename preview and guarded apply policy.

**Public functions:** `annotate_rename_plan_path_authority()`, `dict_bool()`, `dict_str()`, `dict_terms()`, `missing_rename_selection_warnings()`, `remove_terms_from_request()`, `rename_apply_blockers_result()`, `rename_apply_busy_result()`, `rename_apply_confirmation_required_result()`, `rename_apply_exception_result()`, `rename_apply_missing_selection_result()`, `rename_apply_no_selection_result()`, `rename_apply_outside_configured_roots_result()`, `rename_apply_progress_payload()`, `rename_apply_service_unavailable_result()`, `rename_apply_success_result()`, `rename_authority_fields_for_source()`, `rename_blocker_error_lines()`, `rename_clean_filename_preview_from_request()`, `rename_configured_media_roots_from_request()`
**In-repo imports:** `app.files.constants`, `app.paths.layout`, `app.rename.movie`, `app.rename.plan_policy`, `mediapipeline_desktop_app.config_keys`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/rename/policy.py`._
