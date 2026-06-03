---
file: app/config/recovery.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-06-02
last_reviewed: 2026-06-02
sha256: a599d2befbc1dcbfe4cd843a66278ad88e20f04dd79699c4cb617566aaa4c635
---
# `app/config/recovery.py`

**Purpose:** Startup recovery for the live operator config (config hardening #1).

**Classes:** `ConfigRecoveryResult`
**Public functions:** `ensure_canonical_config()`, `restore_verified_last_good_config()`, `seed_user_config()`
**In-repo imports:** `app.config.identity`, `app.kernel.config_locations`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/config/recovery.py`._
