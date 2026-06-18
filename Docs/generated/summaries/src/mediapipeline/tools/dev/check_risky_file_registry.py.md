---
file: src/mediapipeline/tools/dev/check_risky_file_registry.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-17
last_reviewed: 2026-06-04
sha256: a4808f901b72ac1e70dd86fca0fcdd6b37dc770bca3b1891c9666a2eeb0a7cbb
---
# `src/mediapipeline/tools/dev/check_risky_file_registry.py`

**Purpose:** Validate and query the machine-readable risky file registry.

**Classes:** `RegistryFinding`, `RiskMatch`
**Public functions:** `changed_paths()`, `classify_paths()`, `load_registry()`, `main()`, `normalize_path()`, `render_findings()`, `render_matches()`, `validate_registry()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_risky_file_registry.py`._
