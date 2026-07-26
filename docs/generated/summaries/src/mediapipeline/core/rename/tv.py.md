---
file: src/mediapipeline/core/rename/tv.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: rename
token_priority: medium
owner_domain: rename
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: 34fe2ae17b52f2880796764dd987d0c6b4ea4f074a097ea7579ad9556ce3dc3e
---
# `src/mediapipeline/core/rename/tv.py`

**Purpose:** Python implementation for tv; exposes apply_tv_episode_title_template, build_auto_tv_rename_name, build_manual_tv_hierarchy_destination.

**Public symbols:** `apply_tv_episode_title_template`, `build_auto_tv_rename_name`, `build_manual_tv_hierarchy_destination`, `build_tv_rename_name`, `clean_pipeline_tv_name_part`, `collective_tv_filter_terms`, `extract_confident_tv_episode_title`, `find_tv_episode_token`, `normalize_tv_filter_options`, `normalize_tv_filter_terms`, `parse_formatted_tv_identity`, `parse_tv_identity`, `rename_tv_filter_default_terms`, `resolve_tv_folder_season_info`, `strip_tv_release_groups`, `tv_identity_key`
**In-repo imports:** `mediapipeline.core.rename.constants`, `mediapipeline.core.rename.movie`, `mediapipeline.core.rename.tv_folder`, `mediapipeline.core.rename.utils`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/rename/tv.py`._
