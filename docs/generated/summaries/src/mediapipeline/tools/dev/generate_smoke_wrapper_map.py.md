---
file: src/mediapipeline/tools/dev/generate_smoke_wrapper_map.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-23
last_reviewed: 2026-06-17
sha256: 968b00ec1ed7271d440ec187770b6188f8bc8f21298e34a9ed22fab2bfaef30f
---
# `src/mediapipeline/tools/dev/generate_smoke_wrapper_map.py`

**Purpose:** Generate a machine-readable smoke wrapper drift map. The map ties each stable operator wrapper under ops/scripts/smoke/ to the Python test/module it delegates to, the active smoke docs, and the release layout gate. Use --check in release/tooling validation to catch drift without rewriting the generated JSON.

**Public symbols:** `build_smoke_wrapper_map`, `check_current`, `DriftFinding`, `extract_browser_catalog_headings`, `extract_invocation`, `extract_reported_browser_counts`, `extract_write_host_literals`, `main`, `parse_wrapper`, `proof_tier_for`, `python_module_for`, `read_text`, `render_smoke_wrapper_map`, `repo_rel`, `write_if_changed`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_smoke_wrapper_map.py`._
