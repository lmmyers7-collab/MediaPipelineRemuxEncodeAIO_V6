---
file: src/mediapipeline/desktop/network/rerun_claims.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-15
last_reviewed: 2026-07-05
sha256: 6edb11218e9d84f565e0b0cdc32a45ce0d1c8697f3092af1c6a8a0f340f897bc
---
# `src/mediapipeline/desktop/network/rerun_claims.py`

**Purpose:** Coordinator-owned claim state for Network CSV rerun rows.

**Public symbols:** `claim_next_network_rerun_row`, `network_rerun_state_root_for_app`, `NetworkRerunClaimLease`, `reconcile_orphaned_network_rerun_destination_policies`, `record_late_network_rerun_row_done`, `request_network_rerun_row_retry`, `rollback_network_rerun_claim`, `update_network_rerun_row_done`, `update_network_rerun_row_released`
**In-repo imports:** `.protocol`, `.registry`, `mediapipeline.core.kernel.config_key_groups`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.network.url_policy`, `mediapipeline.core.processes.rerun_results`, `mediapipeline.core.processes.source_probe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/rerun_claims.py`._
