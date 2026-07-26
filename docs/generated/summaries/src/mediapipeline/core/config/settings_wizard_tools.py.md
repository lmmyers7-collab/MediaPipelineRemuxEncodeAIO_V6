---
file: src/mediapipeline/core/config/settings_wizard_tools.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 6d422554c27de6792df41e83676ff915db2d80dd5fa8a03f1b337968467264f1
---
# `src/mediapipeline/core/config/settings_wizard_tools.py`

**Purpose:** Settings setup wizard helpers. The wizard is a guided front end over the existing settings patch pipeline. It produces normal settings `changes` and then delegates preview/save to the same backend-owned PSD1 validation, backup, serialization, and reload flow.

**In-repo imports:** `mediapipeline.core.config.encoding_capabilities`, `mediapipeline.core.config.identity`, `mediapipeline.core.config.library_profiles`, `mediapipeline.core.config.settings_patch_policy`, `mediapipeline.core.kernel.config_keys`, `mediapipeline.core.paths.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/settings_wizard_tools.py`._
