---
file: src/mediapipeline/tools/dev/generate_dependency_atlas.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: fdaeaeec64e90bdfcdf6e0c342313f853b6882f8cd731c2b39edb1dfe06da845
---
# `src/mediapipeline/tools/dev/generate_dependency_atlas.py`

**Purpose:** Generate a readable Python dependency atlas for current navigation.

**Classes:** `AtlasData`, `DetailRecord`, `ModuleIndex`
**Public functions:** `category_for_module()`, `clean_outputs()`, `collect_data()`, `current_package_parts()`, `display_path()`, `dot_quote()`, `html_link()`, `import_targets()`, `iter_python_modules()`, `main()`, `module_label()`, `parse_args()`, `render_detail_dot()`, `render_html()`, `render_overview_dot()`, `resolve_dot()`, `resolve_local_module()`, `run_dot()`, `slug()`, `validate_html_links()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_dependency_atlas.py`._
