---
file: scripts/dev/check_risky_file_registry.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-02
last_reviewed: 2026-05-28
sha256: d1c23bb568d865c610f59da5c4d3c903678923793292bf11ccafc0d12130946a
---
# `scripts/dev/check_risky_file_registry.py`

**Purpose:** Validate and query the machine-readable risky file registry.

**Classes:** `RegistryFinding`, `RiskMatch`
**Public functions:** `changed_paths()`, `classify_paths()`, `load_registry()`, `main()`, `normalize_path()`, `render_findings()`, `render_matches()`, `validate_registry()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/check_risky_file_registry.py`._
