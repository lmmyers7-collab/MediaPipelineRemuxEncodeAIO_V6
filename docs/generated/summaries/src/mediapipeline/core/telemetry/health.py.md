---
file: src/mediapipeline/core/telemetry/health.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: observability
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 0532a532e585422fa9ba7230e6857cf679e0ee684723833a843b688ca28689cd
---
# `src/mediapipeline/core/telemetry/health.py`

**Purpose:** Python implementation for health; exposes api_contract_health_rows, ass_to_srt_exception_row, ass_to_srt_missing_row.

**Public symbols:** `api_contract_health_rows`, `ass_to_srt_exception_row`, `ass_to_srt_missing_row`, `ass_to_srt_result_row`, `bundle_layout_health_rows`, `bundled_tool_health_rows`, `config_schema_health_rows`, `configured_root_health_rows`, `find_ass_to_srt_script`, `find_bundled_or_system_tool`, `find_vobsub_tesseract`, `health_config_bool`, `health_config_languages`, `health_config_text`, `health_path_roots`, `library_output_health_rows`, `nvidia_smi_health_row`, `powershell_health_row`, `process_guard_health_rows`, `resolve_health_path`, `runtime_state_health_rows`, `subtitle_config_directory_health_row`, `subtitle_config_file_health_row`, `subtitle_health_label`, `subtitle_tool_health_rows`, `tool_capability_detail`, `vobsub_tesseract_health_row`
**In-repo imports:** `mediapipeline.contracts.config`, `mediapipeline.core.config.library_profiles`, `mediapipeline.core.kernel.config_keys`, `mediapipeline.core.storage.db`
**HTTP routes:** `/api/contract`, `/api/health`, `/api/maintenance`, `/api/maintenance/progress`, `/api/snapshot`, `/api/status`
**State/config identifiers:** `mediapipeline.core.storage.db`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/telemetry/health.py`._
