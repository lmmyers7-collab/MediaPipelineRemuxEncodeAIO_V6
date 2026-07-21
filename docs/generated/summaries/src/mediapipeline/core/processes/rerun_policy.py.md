---
file: src/mediapipeline/core/processes/rerun_policy.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-15
last_reviewed: 2026-07-09
sha256: 95a07f4c5a9f2afecddcdfcb48613b81ecc6e8ee490ecebab676049d08b7c20f
---
# `src/mediapipeline/core/processes/rerun_policy.py`

**Purpose:** CSV rerun launch request and result policy helpers.

**Public symbols:** `normalize_rerun_csv_path`, `normalize_rerun_lifecycle_value`, `normalize_rerun_mode`, `rerun_bool_from_request`, `rerun_csv_path_from_request`, `rerun_csv_path_missing_result`, `rerun_destination_replaces_final`, `rerun_dry_run_from_request`, `rerun_effective_output_root_for_source`, `rerun_final_output_for_row`, `rerun_final_output_override`, `rerun_final_output_root_violation`, `rerun_lifecycle_error_result`, `rerun_lifecycle_errors`, `rerun_lifecycle_from_request`, `rerun_mode_error_result`, `rerun_modes_are_supported`, `rerun_modes_from_request`, `rerun_original_policy_from_destination`, `rerun_path_resolves_under_root`, `rerun_paths_resolve_same`, `rerun_plan_flags_are_supported`, `rerun_plan_mode_error_result`, `rerun_plan_only_from_request`, `rerun_run_label`, `rerun_source_path_destination_requested`, `rerun_start_active_work_result`, `rerun_start_config_blocked_result`, `rerun_start_exception_result`, `rerun_start_success_data`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_policy.py`._
