---
file: src/mediapipeline/core/config/recovery.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-06-13
last_reviewed: 2026-06-04
sha256: d1495242800771a857c06d446eb48baf11c7e5be6bbb57cfa2cc779b23592293
---
# `src/mediapipeline/core/config/recovery.py`

**Purpose:** Startup recovery for the live operator config (config hardening #1).

**Classes:** `ConfigRecoveryResult`
**Public functions:** `ensure_canonical_config()`, `restore_verified_last_good_config()`, `seed_user_config()`
**In-repo imports:** `mediapipeline.core.config.identity`, `mediapipeline.core.kernel.config_locations`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/recovery.py`._
