---
file: src/mediapipeline/core/diagnostics/autonomy_health.py
pipeline_stage: observability
token_priority: medium
owner_domain: diagnostics
last_modified: 2026-07-11
last_reviewed: 2026-06-17
sha256: 7d6dd566e2e602ea6b6abe1a750008747e5e59484dd68d42bda05597c07cb6f9
---
# `src/mediapipeline/core/diagnostics/autonomy_health.py`

**Purpose:** (no module docstring)

**Public functions:** `autonomy_health_is_blocked()`, `autonomy_health_payload()`, `load_autonomy_growth_history()`, `record_autonomy_growth_snapshot()`
**In-repo imports:** `mediapipeline.core.diagnostics.autonomy_evaluators`, `mediapipeline.core.diagnostics.autonomy_growth`, `mediapipeline.core.diagnostics.autonomy_health_constants`, `mediapipeline.core.diagnostics.autonomy_health_projection`, `mediapipeline.core.diagnostics.autonomy_health_publish`, `mediapipeline.core.diagnostics.autonomy_health_runtime`, `mediapipeline.core.diagnostics.autonomy_health_storage`, `mediapipeline.core.diagnostics.autonomy_health_support`, `mediapipeline.core.diagnostics.autonomy_policy`, `mediapipeline.core.diagnostics.autonomy_recovery`, `mediapipeline.core.diagnostics.autonomy_scan`, `mediapipeline.core.diagnostics.autonomy_types`, `mediapipeline.core.kernel.contracts.pending_publish`, `mediapipeline.core.status.runtime_health`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/diagnostics/autonomy_health.py`._
