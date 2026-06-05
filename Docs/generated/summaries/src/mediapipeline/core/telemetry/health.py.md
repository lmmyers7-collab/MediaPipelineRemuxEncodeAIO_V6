---
file: src/mediapipeline/core/telemetry/health.py
pipeline_stage: observability
token_priority: medium
owner_domain: observability
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 9a2e7895328fe7d7fe67aa93e84c893a85fdbaebd958cbf7ab531dc948a77ca2
---
# `src/mediapipeline/core/telemetry/health.py`

**Purpose:** (no module docstring)

**Public functions:** `api_contract_health_rows()`, `ass_to_srt_exception_row()`, `ass_to_srt_missing_row()`, `ass_to_srt_result_row()`, `bundle_layout_health_rows()`, `bundled_tool_health_rows()`, `config_schema_health_rows()`, `configured_root_health_rows()`, `find_ass_to_srt_script()`, `find_bundled_or_system_tool()`, `find_vobsub_tesseract()`, `health_config_bool()`, `health_config_languages()`, `health_config_text()`, `health_path_roots()`, `library_output_health_rows()`, `nvidia_smi_health_row()`, `powershell_health_row()`, `process_guard_health_rows()`, `resolve_health_path()`
**In-repo imports:** `mediapipeline.contracts.config`, `mediapipeline.core.config.library_profiles`, `mediapipeline.core.kernel.config_keys`, `mediapipeline.core.storage.db`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/telemetry/health.py`._
