---
file: src/mediapipeline/tools/dev/check_risky_file_registry.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: f8df061b6fc8a2bc2428f269998a2bd1e2a4686e8d9f27a593bbbd80044341f7
---
# `src/mediapipeline/tools/dev/check_risky_file_registry.py`

**Purpose:** Validate and query the machine-readable risky file registry.

**Classes:** `RegistryFinding`, `RiskMatch`
**Public functions:** `changed_paths()`, `classify_paths()`, `load_registry()`, `main()`, `normalize_path()`, `render_findings()`, `render_matches()`, `validate_registry()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_risky_file_registry.py`._
