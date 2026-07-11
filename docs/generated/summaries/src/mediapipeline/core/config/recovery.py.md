---
file: src/mediapipeline/core/config/recovery.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 61500031f57a225a77fd783948d8f77318f1d4e2209df0ce2fdd06832e71504d
---
# `src/mediapipeline/core/config/recovery.py`

**Purpose:** Startup recovery for the live operator config (config hardening #1).

**Classes:** `ConfigRecoveryResult`
**Public functions:** `ensure_canonical_config()`, `restore_verified_last_good_config()`, `seed_user_config()`
**In-repo imports:** `mediapipeline.core.config.identity`, `mediapipeline.core.kernel.config_locations`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/recovery.py`._
