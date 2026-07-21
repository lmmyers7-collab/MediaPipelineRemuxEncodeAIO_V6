---
file: src/mediapipeline/core/config/settings_wizard.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: a0c00a1dccd2b809075766c5de0c3884e2039a95378b612bd109076cbe76df53
---
# `src/mediapipeline/core/config/settings_wizard.py`

**Purpose:** Settings setup wizard helpers. The wizard is a guided front end over the existing settings patch pipeline. It produces normal settings `changes` and then delegates preview/save to the same backend-owned PSD1 validation, backup, serialization, and reload flow.

**Public symbols:** `mark_settings_wizard_completed`, `preview_settings_wizard`, `probe_ffmpeg_hardware`, `save_settings_wizard`, `settings_wizard_defaults`, `settings_wizard_payload_from_request`, `settings_wizard_status`, `tool_candidates`, `validate_ffmpeg_tools`, `validate_wizard_paths`, `validate_wizard_payload`, `validate_worker_settings`, `wizard_changes`
**In-repo imports:** `mediapipeline.core.config.encoding_capabilities`, `mediapipeline.core.config.identity`, `mediapipeline.core.config.library_profiles`, `mediapipeline.core.config.settings_patch_policy`, `mediapipeline.core.config.settings_wizard_tools`, `mediapipeline.core.kernel.config_keys`, `mediapipeline.core.paths.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/settings_wizard.py`._
