---
file: src/mediapipeline/core/config/identity.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 5001a2681c271e4de346932c6bb73b5e6c8d4fd1fb189e8a9b1d61a39d274a1d
---
# `src/mediapipeline/core/config/identity.py`

**Purpose:** Config identity, health, and last-known-good snapshot helpers.

**Public functions:** `build_config_identity()`, `config_identity_block_reasons()`, `config_looks_like_template()`, `config_operation_block_data()`, `config_operation_block_message()`, `config_template_candidates()`, `file_sha256()`, `last_good_snapshot_path()`, `path_modified_utc()`, `user_last_good_snapshot_path()`, `write_last_good_config_snapshot()`
**In-repo imports:** `mediapipeline.core.kernel.config_locations`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/identity.py`._
