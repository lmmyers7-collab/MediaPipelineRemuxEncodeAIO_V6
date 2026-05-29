---
file: scripts/dev/check_risky_file_registry.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-28
last_reviewed: 2026-05-28
sha256: a7912e2178822881e1124570ad2e12279df08eea3f6f6151f7f662b4346f2d7a
---
# `scripts/dev/check_risky_file_registry.py`

**Purpose:** Validate and query the machine-readable risky file registry.

**Classes:** `RegistryFinding`, `RiskMatch`
**Public functions:** `changed_paths()`, `classify_paths()`, `load_registry()`, `main()`, `normalize_path()`, `render_findings()`, `render_matches()`, `validate_registry()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/check_risky_file_registry.py`._
