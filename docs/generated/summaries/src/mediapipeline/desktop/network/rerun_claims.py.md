---
file: src/mediapipeline/desktop/network/rerun_claims.py
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-10
last_reviewed: 2026-07-05
sha256: a0ffd27c44acf5a9dfa00046f882520a339dd1dc88f35980d2df912dca7c343d
---
# `src/mediapipeline/desktop/network/rerun_claims.py`

**Purpose:** Coordinator-owned claim state for Network CSV rerun rows.

**Classes:** `NetworkRerunClaimLease`
**Public functions:** `claim_next_network_rerun_row()`, `network_rerun_state_root_for_app()`, `record_late_network_rerun_row_done()`, `rollback_network_rerun_claim()`, `update_network_rerun_row_done()`, `update_network_rerun_row_released()`
**In-repo imports:** `mediapipeline.core.network.url_policy`, `mediapipeline.core.processes.rerun_results`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/rerun_claims.py`._
