---
file: src/mediapipeline/core/processes/rerun_facade.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: cdd5699a6c2017c2b639a8124aeb1a83f6174a4fe8198b44357bda201b84b6e8
---
# `src/mediapipeline/core/processes/rerun_facade.py`

**Purpose:** CSV rerun launch facade adapter.

**Public symbols:** `RerunLaunchFacadeMixin`
**In-repo imports:** `mediapipeline.core.config.identity`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.network.rerun_handoff`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.kill`, `mediapipeline.core.processes.pipeline_policy`, `mediapipeline.core.processes.rerun_control`, `mediapipeline.core.processes.rerun_lifecycle`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.processes.spawn_runner`
**HTTP routes:** `/api/rerun/network-preview`, `/api/rerun/network/start`, `/api/rerun/network/start.`, `/api/rerun/start`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_facade.py`._
