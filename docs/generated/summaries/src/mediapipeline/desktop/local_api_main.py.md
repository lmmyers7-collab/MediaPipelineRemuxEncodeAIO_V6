---
file: src/mediapipeline/desktop/local_api_main.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: unknown
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 256d8d0f23c8e4225990556841d78674bae9b04be1df74d970342aed6c75f1cc
---
# `src/mediapipeline/desktop/local_api_main.py`

**Purpose:** Python implementation for local api main; exposes BackendResolvedState, bootstrap_payload, build_backend.

**Public symbols:** `BackendResolvedState`, `bootstrap_payload`, `build_backend`, `default_app_root`, `emit_startup_progress`, `main`, `parse_args`, `record_startup_path_step`, `record_startup_step`
**In-repo imports:** `.api`, `.api.http_helpers`, `.application`, `.backend_bootstrap`, `.backend_instance`, `.models`, `.services`, `mediapipeline.core.api.file_overrides.remux_pilot`, `mediapipeline.core.config.identity`, `mediapipeline.core.config.recovery`, `mediapipeline.core.processes.recovery`, `mediapipeline.core.processes.rerun_lifecycle`, `mediapipeline.tools.paths`
**HTTP routes:** `/api/audit/start`, `/api/pipeline/start`, `/api/rerun/start`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/local_api_main.py`._
