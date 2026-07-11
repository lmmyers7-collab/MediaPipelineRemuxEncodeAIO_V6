---
file: src/mediapipeline/tools/dev/check_dependency_boundaries.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 63dd2a46f0c683560fb6852440205314aa02283bc2a5c99c0cd88056a106c39c
---
# `src/mediapipeline/tools/dev/check_dependency_boundaries.py`

**Purpose:** Check Python backend dependency boundary rules.

**Classes:** `AllowlistEntry`, `AllowlistError`, `DependencyReport`, `EnforcementReport`, `ImportEdge`, `ParseError`, `RuleFinding`
**Public functions:** `analyze()`, `collect_backend_imports()`, `config_rule_id()`, `cycles_from_graph()`, `display_path()`, `enforce_rules()`, `filter_package_edge()`, `filter_target()`, `format_edge()`, `graph_from_edges()`, `hard_rule_findings()`, `import_targets()`, `iter_backend_modules()`, `load_allowlist()`, `main()`, `module_cycle_edges()`, `module_name_for_path()`, `package_cycle_edges()`, `package_name()`, `render_allowlist_error()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_dependency_boundaries.py`._
