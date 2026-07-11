---
file: src/mediapipeline/core/config/preset_migration.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 5bc580eda90fbf6ffef6fd781746ae43d3fdc28ae55eba684ed87ad1719369f3
---
# `src/mediapipeline/core/config/preset_migration.py`

**Purpose:** Stable config and PresetV2 display adapters.

**Public functions:** `effective_decision_policy_from_legacy_or_preset()`, `effective_decision_policy_from_preset_v2()`, `legacy_config_patch_from_preset_v2()`, `preset_v2_from_legacy_config()`
**In-repo imports:** `mediapipeline.contracts.config`, `mediapipeline.contracts.decision_policy`, `mediapipeline.core.config.encoding_capabilities`, `mediapipeline.core.config.preset_compatibility`, `mediapipeline.core.config.preset_display_adapter`, `mediapipeline.core.config.preset_migration_models`, `mediapipeline.core.config.preset_policy`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/preset_migration.py`._
