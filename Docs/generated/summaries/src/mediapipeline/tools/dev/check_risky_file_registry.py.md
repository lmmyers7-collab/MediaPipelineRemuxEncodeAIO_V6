---
file: src/mediapipeline/tools/dev/check_risky_file_registry.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 9ee1fe5080ad7e0438c65821e76480dc14967080926d1f8b7ed16d7021c1d1a4
---
# `src/mediapipeline/tools/dev/check_risky_file_registry.py`

**Purpose:** Validate and query the machine-readable risky file registry.

**Classes:** `RegistryFinding`, `RiskMatch`
**Public functions:** `changed_paths()`, `classify_paths()`, `load_registry()`, `main()`, `normalize_path()`, `render_findings()`, `render_matches()`, `validate_registry()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_risky_file_registry.py`._
