---
file: app/rename/apply.py
pipeline_stage: rename
token_priority: high
owner_domain: rename
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: 8f8b920d688efbba054ea995b38861c2891da4ec631a0e5d98ae30ba573d0438
---
# `app/rename/apply.py`

**Purpose:** (no module docstring)

**Public functions:** `build_rename_operations()`, `pipeline_sidecar_paths_for_destination()`, `read_json_dict_for_rename()`, `rename_path_case_safe()`, `rollback_rename_operations()`, `update_pipeline_sidecar_after_rename()`, `update_rename_sidecar_metadata()`, `write_rename_undo_manifest()`
**In-repo imports:** `app.paths.layout`, `app.rename.constants`, `app.rename.file_io`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/rename/apply.py`._
