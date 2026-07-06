---
file: src/mediapipeline/core/processes/rerun_policy.py
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-04
last_reviewed: 2026-06-04
sha256: dee66340ff700dd97787660af4d69fed041742a18510f70470b6257325a054f4
---
# `src/mediapipeline/core/processes/rerun_policy.py`

**Purpose:** CSV rerun launch request and result policy helpers.

**Classes:** `RerunLifecyclePolicy`
**Public functions:** `normalize_rerun_csv_path()`, `normalize_rerun_lifecycle_value()`, `normalize_rerun_mode()`, `rerun_bool_from_request()`, `rerun_csv_path_from_request()`, `rerun_csv_path_missing_result()`, `rerun_dry_run_from_request()`, `rerun_effective_output_root_for_source()`, `rerun_final_output_override()`, `rerun_final_output_root_violation()`, `rerun_lifecycle_error_result()`, `rerun_lifecycle_errors()`, `rerun_lifecycle_from_request()`, `rerun_mode_error_result()`, `rerun_modes_are_supported()`, `rerun_modes_from_request()`, `rerun_original_policy_from_destination()`, `rerun_path_resolves_under_root()`, `rerun_paths_resolve_same()`, `rerun_plan_flags_are_supported()`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_policy.py`._
