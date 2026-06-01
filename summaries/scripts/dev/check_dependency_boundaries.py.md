---
file: scripts/dev/check_dependency_boundaries.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-31
last_reviewed: 2026-05-31
sha256: f4bc600f934b9a26713eb6522822ec68a2c2045a810bed615e6a3c878aa17906
---
# `scripts/dev/check_dependency_boundaries.py`

**Purpose:** Check Python app dependency boundary rules.

**Classes:** `AllowlistEntry`, `AllowlistError`, `DependencyReport`, `EnforcementReport`, `ImportEdge`, `ParseError`, `RuleFinding`
**Public functions:** `analyze()`, `collect_app_imports()`, `config_rule_id()`, `cycles_from_graph()`, `display_path()`, `enforce_rules()`, `filter_package_edge()`, `filter_target()`, `format_edge()`, `graph_from_edges()`, `hard_rule_findings()`, `has_rule_findings()`, `import_targets()`, `iter_app_modules()`, `load_allowlist()`, `main()`, `module_cycle_edges()`, `module_name_for_path()`, `package_cycle_edges()`, `package_name()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/check_dependency_boundaries.py`._
