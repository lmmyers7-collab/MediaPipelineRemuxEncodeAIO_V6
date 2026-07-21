---
file: src/mediapipeline/core/processes/preflight_facade.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: baff0e0e7509d8ee17dc465e2e30f2f76a0a027882170eb23935bff083593694
---
# `src/mediapipeline/core/processes/preflight_facade.py`

**Purpose:** Process launch preflight facade adapter.

**Public symbols:** `ProcessFacadeMixin`
**In-repo imports:** `mediapipeline.core.config.identity`, `mediapipeline.core.config.settings_policy`, `mediapipeline.core.kernel.contracts`, `mediapipeline.core.kernel.dto_base`, `mediapipeline.core.kernel.dto_commands`, `mediapipeline.core.kernel.runtime.subprocess_runner`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.paths.queue_input_fingerprint`, `mediapipeline.core.processes`, `mediapipeline.core.processes.audit_policy`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.processes.launch_intent`, `mediapipeline.core.processes.path_evidence`, `mediapipeline.core.processes.pipeline_policy`, `mediapipeline.core.processes.preflight_support`, `mediapipeline.core.processes.preflight_types`, `mediapipeline.core.processes.rerun_policy`, `mediapipeline.core.processes.rerun_preview`, `mediapipeline.core.processes.schedule_policy`, `mediapipeline.core.processes.source_path_policy`, `mediapipeline.core.queue.freshness`, `mediapipeline.core.queue.priority_export`
**HTTP routes:** `/api/audit/start`, `/api/pipeline/start`, `/api/rerun/start`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/preflight_facade.py`._
