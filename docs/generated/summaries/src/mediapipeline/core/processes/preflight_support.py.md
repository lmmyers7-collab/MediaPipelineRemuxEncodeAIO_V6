---
file: src/mediapipeline/core/processes/preflight_support.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 601f60236bc512296d7932a1754e095c9354cee253b61837d5ee809d30656915
---
# `src/mediapipeline/core/processes/preflight_support.py`

**Purpose:** Process launch preflight facade adapter.

**In-repo imports:** `mediapipeline.core.config.identity`, `mediapipeline.core.config.settings_policy`, `mediapipeline.core.kernel.dto_base`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.kernel.runtime.subprocess_runner`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.audit_policy`, `mediapipeline.core.processes.launch_intent`, `mediapipeline.core.processes.path_evidence`, `mediapipeline.core.processes.pipeline_policy`, `mediapipeline.core.processes.preflight_types`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.processes.schedule_policy`, `mediapipeline.core.processes.source_path_policy`
**HTTP routes:** `/api/launch/preflight`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/preflight_support.py`._
