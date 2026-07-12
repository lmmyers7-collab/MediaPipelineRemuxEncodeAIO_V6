---
file: src/mediapipeline/tools/dev/generate_dependency_atlas.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: ebb838056aee6f48fe4169128fbec4c337b1c29c0a01734a62e5baf79eda719e
---
# `src/mediapipeline/tools/dev/generate_dependency_atlas.py`

**Purpose:** Generate a readable Python dependency atlas for current navigation.

**Classes:** `AtlasData`, `DetailRecord`, `ModuleIndex`
**Public functions:** `category_for_module()`, `clean_outputs()`, `collect_data()`, `current_package_parts()`, `display_path()`, `dot_quote()`, `html_link()`, `import_targets()`, `iter_python_modules()`, `legacy_root_atlas_artifact()`, `main()`, `module_label()`, `parse_args()`, `render_detail_dot()`, `render_html()`, `render_overview_dot()`, `resolve_dot()`, `resolve_local_module()`, `run_dot()`, `slug()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_dependency_atlas.py`._
