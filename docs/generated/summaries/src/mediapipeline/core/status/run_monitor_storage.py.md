---
file: src/mediapipeline/core/status/run_monitor_storage.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: observability
last_modified: 2026-07-20
last_reviewed: 2026-07-16
sha256: 692123da1938400c7888d0eca3e09dfca27a67259efcf1b678b6792182d63c92
---
# `src/mediapipeline/core/status/run_monitor_storage.py`

**Purpose:** Durable storage for backend-owned Run Monitor artifacts. Python writes before a pipeline process is spawned, when that spawn fails, or after the backend force-stop service has terminated the correlated process tree. While PowerShell is alive, the engine is the sole writer and uses a cross-process lock around read/modify/replace. Ordinary readers never mutate files.

**Public symbols:** `RunMonitorStore`
**In-repo imports:** `mediapipeline.contracts.run_monitor`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/status/run_monitor_storage.py`._
