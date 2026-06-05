---
file: src/mediapipeline/core/rename/path_authority.py
pipeline_stage: rename
token_priority: medium
owner_domain: rename
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: b803e4c572d28927bc220a35348e91a63374468c73a0b46978258fa8a23aaedc
---
# `src/mediapipeline/core/rename/path_authority.py`

**Purpose:** Configured-root authority and undo manifest root helpers for rename.

**Public functions:** `annotate_rename_plan_path_authority()`, `rename_authority_fields_for_source()`, `rename_configured_media_roots_from_request()`, `rename_configured_media_roots_from_resolved()`, `rename_plan_outside_configured_roots()`, `rename_request_allows_outside_configured_roots()`, `rename_request_paths()`, `rename_undo_manifest_root_from_request()`, `rename_undo_manifest_root_from_resolved()`
**In-repo imports:** `mediapipeline.core.paths.layout`, `mediapipeline.desktop.config_keys`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/rename/path_authority.py`._
