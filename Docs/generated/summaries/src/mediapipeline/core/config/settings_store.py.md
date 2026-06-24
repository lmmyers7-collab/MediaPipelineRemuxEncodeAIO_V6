---
file: src/mediapipeline/core/config/settings_store.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-06-23
last_reviewed: 2026-06-23
sha256: 1aa00954f0c1c2235fdc7f3d098e4fdeb7ac1c0926f4a39f4cd24a08b70cee27
---
# `src/mediapipeline/core/config/settings_store.py`

**Purpose:** Versioned JSON authority for desktop settings persistence.

**Classes:** `SettingsMigrationResult`, `SettingsStoreError`
**Public functions:** `import_psd1_settings_for_service()`, `import_psd1_settings_preview_for_service()`, `load_settings_authority_for_service()`, `migrate_imported_settings_mapping()`, `save_settings_authority_for_service()`, `settings_projection_last_good_path()`, `settings_projection_path_for_config()`, `settings_store_last_good_path()`, `settings_store_metadata_for_service()`, `settings_store_path_for_config()`, `utc_now_text()`
**In-repo imports:** `mediapipeline.contracts.config`, `mediapipeline.core.config.file_io`, `mediapipeline.core.config.load`, `mediapipeline.core.config.validation`, `mediapipeline.core.kernel.config_key_aliases`, `mediapipeline.core.kernel.config_key_order`, `mediapipeline.core.kernel.config_locations`, `mediapipeline.core.kernel.models_core`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/settings_store.py`._
