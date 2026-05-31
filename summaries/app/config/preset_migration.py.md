---
file: app/config/preset_migration.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-05-31
last_reviewed: 2026-05-30
sha256: fb690832ec377c996d873fa31ca5aca224fe4b4bd1b9fa32b6cb2978cc4104c1
---
# `app/config/preset_migration.py`

**Purpose:** Legacy config and PresetV2 adapters for Phase 05.

**Public functions:** `blocked_friendly_label_aliases()`, `effective_decision_policy_from_legacy_or_preset()`, `effective_decision_policy_from_preset_v2()`, `legacy_config_patch_from_preset_v2()`, `migration_status_for_persisted_key()`, `preset_v2_from_legacy_config()`
**In-repo imports:** `app.config.encoding_capabilities`, `app.config.preset_policy`, `app.contracts.config`, `app.contracts.verification`, `app.decide.processing_decision`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/config/preset_migration.py`._
