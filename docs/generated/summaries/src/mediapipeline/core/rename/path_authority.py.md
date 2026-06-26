---
file: src/mediapipeline/core/rename/path_authority.py
pipeline_stage: rename
token_priority: medium
owner_domain: rename
last_modified: 2026-06-23
last_reviewed: 2026-06-04
sha256: 7c9b9bd12117836137f01a3f0d5e3bb7f3fb062922d9994cf72026d1d75b0696
---
# `src/mediapipeline/core/rename/path_authority.py`

**Purpose:** Configured-root authority and undo manifest root helpers for rename.

**Public functions:** `annotate_rename_plan_path_authority()`, `rename_authority_fields_for_source()`, `rename_configured_media_roots_from_request()`, `rename_configured_media_roots_from_resolved()`, `rename_plan_outside_configured_roots()`, `rename_plan_unscoped_operator_paths()`, `rename_request_allows_outside_configured_roots()`, `rename_request_paths()`, `rename_undo_manifest_root_from_request()`, `rename_undo_manifest_root_from_resolved()`
**In-repo imports:** `mediapipeline.core.kernel.config_keys`, `mediapipeline.core.paths.layout`, `mediapipeline.core.rename.input_classification`, `mediapipeline.core.validation.strict_json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/rename/path_authority.py`._
