---
file: src/mediapipeline/core/config/recovery.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 9959d176a4b050e5aa669b7cd6e82f9123e6feb84c563a3cc40af14504900bb9
---
# `src/mediapipeline/core/config/recovery.py`

**Purpose:** Startup recovery for the live operator config (config hardening #1).

**Classes:** `ConfigRecoveryResult`
**Public functions:** `ensure_canonical_config()`, `restore_verified_last_good_config()`, `seed_user_config()`
**In-repo imports:** `mediapipeline.core.config.identity`, `mediapipeline.core.kernel.config_locations`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/recovery.py`._
