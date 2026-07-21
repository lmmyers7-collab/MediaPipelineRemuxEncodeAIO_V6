---
file: src/mediapipeline/core/api/commands_file_overrides.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: api
token_priority: medium
owner_domain: api
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: ca1b302b60b7c5af06cb0e87935e48e56842fcae8c6cd2d48e320ba211ac883a
---
# `src/mediapipeline/core/api/commands_file_overrides.py`

**Purpose:** Python implementation for commands file overrides; exposes LocalApiFileOverridesCommandPayloadMixin.

**Public symbols:** `LocalApiFileOverridesCommandPayloadMixin`
**In-repo imports:** `.command_results`, `.file_overrides.effective_fields`, `.file_overrides.folder_preview`, `.file_overrides.remux_pilot`, `.file_overrides.results`, `.file_overrides.route_preview`, `.file_overrides.selectors`, `.file_overrides.series`, `.file_overrides.tracks`, `mediapipeline.core.orchestration.runner`, `mediapipeline.core.processes.source_path_policy`, `mediapipeline.core.queue.file_overrides`
**HTTP routes:** `/api/commands_file_overrides.py`, `/api/file_overrides/.`, `/api/queue/file-overrides`, `/api/queue/file-overrides/effective`, `/api/queue/file-overrides/folder-preview`, `/api/queue/file-overrides/folder-rule`, `/api/queue/file-overrides/remux-pilot-promote`, `/api/queue/file-overrides/route-preview`, `/api/queue/file-overrides/series-apply`, `/api/queue/file-overrides/series-clear-apply`, `/api/queue/file-overrides/series-clear-preview`, `/api/queue/file-overrides/series-preview`, `/api/queue/file-overrides/tracks`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/api/commands_file_overrides.py`._
