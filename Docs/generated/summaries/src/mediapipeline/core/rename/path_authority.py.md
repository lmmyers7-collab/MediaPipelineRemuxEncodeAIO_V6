---
file: src/mediapipeline/core/rename/path_authority.py
pipeline_stage: rename
token_priority: medium
owner_domain: rename
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 1b39732a5f40542fc0d93a8ae9473fe74c8602214f013db6fcf80a0b375f8f19
---
# `src/mediapipeline/core/rename/path_authority.py`

**Purpose:** Configured-root authority and undo manifest root helpers for rename.

**Public functions:** `annotate_rename_plan_path_authority()`, `rename_authority_fields_for_source()`, `rename_configured_media_roots_from_request()`, `rename_configured_media_roots_from_resolved()`, `rename_plan_outside_configured_roots()`, `rename_request_allows_outside_configured_roots()`, `rename_request_paths()`, `rename_undo_manifest_root_from_request()`, `rename_undo_manifest_root_from_resolved()`
**In-repo imports:** `mediapipeline.core.kernel.config_keys`, `mediapipeline.core.paths.layout`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/rename/path_authority.py`._
