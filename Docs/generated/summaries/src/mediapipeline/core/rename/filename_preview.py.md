---
file: src/mediapipeline/core/rename/filename_preview.py
pipeline_stage: rename
token_priority: medium
owner_domain: rename
last_modified: 2026-06-18
last_reviewed: 2026-06-04
sha256: abf041b09e1689dae42ebc87d83ba09bb4176e303de876e1b59e4970537bd758
---
# `src/mediapipeline/core/rename/filename_preview.py`

**Purpose:** Read-only rename filename preview and filter catalog payloads.

**Public functions:** `rename_clean_filename_preview_from_request()`, `rename_cleaning_filter_catalog_payload()`, `rename_filename_leaf()`, `rename_movie_filter_catalog_payload()`, `rename_plan_kwargs_from_request()`
**In-repo imports:** `mediapipeline.core.files.constants`, `mediapipeline.core.rename.cleaning_policy`, `mediapipeline.core.rename.movie`, `mediapipeline.core.rename.tv`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/rename/filename_preview.py`._
