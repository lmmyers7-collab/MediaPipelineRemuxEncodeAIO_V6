---
file: src/mediapipeline/core/processes/pipeline_policy.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 30b9f6586242f7c8aa12c4a6485831628665e18e42ef3cd253d93dd6b3b98310
---
# `src/mediapipeline/core/processes/pipeline_policy.py`

**Purpose:** Pipeline launch request and result policy helpers.

**Public symbols:** `configured_network_role`, `coordinator_also_encode_locally_enabled`, `is_supported_pipeline_start_mode`, `network_role_blocks_normal_launch`, `network_role_is_valid`, `normalize_network_role`, `normalize_pipeline_extra_args`, `normalize_pipeline_start_mode`, `parse_pipeline_sleep_seconds`, `pipeline_extra_args_error`, `pipeline_start_active_work_result`, `pipeline_start_autonomy_blocked_result`, `pipeline_start_config_blocked_result`, `pipeline_start_exception_result`, `pipeline_start_extra_args_error_result`, `pipeline_start_network_mode_blocked_result`, `pipeline_start_network_mode_label`, `pipeline_start_network_role_error`, `pipeline_start_queue_scope_blocked_result`, `pipeline_start_schedule_gate_result`, `pipeline_start_single_file_blocked_result`, `pipeline_start_sleep_error_result`, `pipeline_start_success_data`, `pipeline_start_success_message`, `pipeline_start_success_result`, `pipeline_start_unsupported_mode_result`
**HTTP routes:** `/api/run-monitor`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/pipeline_policy.py`._
