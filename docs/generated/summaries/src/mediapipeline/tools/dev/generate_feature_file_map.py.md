---
file: src/mediapipeline/tools/dev/generate_feature_file_map.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-12
last_reviewed: 2026-06-11
sha256: a9ccd4c437be83972a78d0a98515b941607f530b05611e30aab51e0e012bb9a3
---
# `src/mediapipeline/tools/dev/generate_feature_file_map.py`

**Purpose:** Generate docs/generated/FEATURE_FILE_MAP.md from docs/generated/PROJECT_INDEX.md.

**Classes:** `FeatureGroup`, `IndexEntry`, `PathReferenceFinding`
**Public functions:** `check_file()`, `entries_for_group()`, `load_project_index()`, `main()`, `parse_project_index()`, `path_reference_findings()`, `render_feature_map()`, `render_findings()`, `render_path_list()`, `selector_matches()`, `table_cell()`
**In-repo imports:** `mediapipeline.tools.dev.release_package_scope`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_feature_file_map.py`._
