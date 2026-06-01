---
file: app/config/preset_migration.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-05-31
last_reviewed: 2026-05-30
sha256: ae518826f8f804e6750f3ebcfe4a8238055c490317782e1a43b3d137dd8c9b0a
---
# `app/config/preset_migration.py`

**Purpose:** Stable V6 config and PresetV2 display adapters.

**Public functions:** `effective_decision_policy_from_legacy_or_preset()`, `effective_decision_policy_from_preset_v2()`, `legacy_config_patch_from_preset_v2()`, `preset_v2_from_legacy_config()`
**In-repo imports:** `app.config.encoding_capabilities`, `app.config.preset_policy`, `app.contracts.config`, `app.contracts.decision_policy`, `app.contracts.verification`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/config/preset_migration.py`._
