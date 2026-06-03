---
file: app/config/identity.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-06-02
last_reviewed: 2026-06-02
sha256: 157b303770b3da5ea4d21e8d6acb5e2ae037389df1693de370e77c3573db15cb
---
# `app/config/identity.py`

**Purpose:** Config identity, health, and last-known-good snapshot helpers.

**Public functions:** `build_config_identity()`, `config_identity_block_reasons()`, `config_looks_like_template()`, `config_operation_block_data()`, `config_operation_block_message()`, `config_template_candidates()`, `file_sha256()`, `last_good_snapshot_path()`, `path_modified_utc()`, `user_last_good_snapshot_path()`, `write_last_good_config_snapshot()`
**In-repo imports:** `app.kernel.config_locations`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/config/identity.py`._
