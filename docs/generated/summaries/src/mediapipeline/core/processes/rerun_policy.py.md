---
file: src/mediapipeline/core/processes/rerun_policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-10
last_reviewed: 2026-07-09
sha256: 2f2d2cf043d286568c702282f0d8937ed693c523b97ee9cb0648ce129916c579
---
# `src/mediapipeline/core/processes/rerun_policy.py`

**Purpose:** CSV rerun launch request and result policy helpers.

**Classes:** `RerunLifecyclePolicy`
**Public functions:** `normalize_rerun_csv_path()`, `normalize_rerun_lifecycle_value()`, `normalize_rerun_mode()`, `rerun_bool_from_request()`, `rerun_csv_path_from_request()`, `rerun_csv_path_missing_result()`, `rerun_destination_replaces_final()`, `rerun_dry_run_from_request()`, `rerun_effective_output_root_for_source()`, `rerun_final_output_for_row()`, `rerun_final_output_override()`, `rerun_final_output_root_violation()`, `rerun_lifecycle_error_result()`, `rerun_lifecycle_errors()`, `rerun_lifecycle_from_request()`, `rerun_mode_error_result()`, `rerun_modes_are_supported()`, `rerun_modes_from_request()`, `rerun_original_policy_from_destination()`, `rerun_path_resolves_under_root()`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_policy.py`._
