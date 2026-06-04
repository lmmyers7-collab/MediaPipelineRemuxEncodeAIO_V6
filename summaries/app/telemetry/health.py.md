---
file: app/telemetry/health.py
pipeline_stage: observability
token_priority: medium
owner_domain: observability
last_modified: 2026-06-03
last_reviewed: 2026-05-28
sha256: e9befd81de967269c0999daa7065b6f5c61ecf944f9086f334737adf1a14137b
---
# `app/telemetry/health.py`

**Purpose:** (no module docstring)

**Public functions:** `api_contract_health_rows()`, `ass_to_srt_exception_row()`, `ass_to_srt_missing_row()`, `ass_to_srt_result_row()`, `bundle_layout_health_rows()`, `bundled_tool_health_rows()`, `config_schema_health_rows()`, `configured_root_health_rows()`, `find_ass_to_srt_script()`, `find_bundled_or_system_tool()`, `find_vobsub_tesseract()`, `health_config_bool()`, `health_config_languages()`, `health_config_text()`, `health_path_roots()`, `library_output_health_rows()`, `nvidia_smi_health_row()`, `powershell_health_row()`, `process_guard_health_rows()`, `resolve_health_path()`
**In-repo imports:** `app.config.library_profiles`, `app.contracts.config`, `app.kernel.config_keys`, `app.storage.db`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/telemetry/health.py`._
