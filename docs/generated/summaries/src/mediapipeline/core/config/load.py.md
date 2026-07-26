---
file: src/mediapipeline/core/config/load.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-07-12
last_reviewed: 2026-06-04
sha256: 15c0b6fe88ade008b937b151d8676d9628a11a10dfb9a1979e46e35fc167bf06
---
# `src/mediapipeline/core/config/load.py`

**Purpose:** Canonical PSD1 loader and converter for `mediapipeline.contracts.config`. PowerShell remains the PSD1 parser because `Import-PowerShellDataFile` is the format authority. DesktopApp compatibility wrappers call into this module instead of composing separate import/serialize logic.

**Public symbols:** `build_psd1_import_args`, `config_from_mapping`, `config_to_flat_dict`, `config_to_psd1`, `ConfigLoadError`, `default_powershell_host`, `load_config`, `load_psd1_mapping`, `order_top_level_config`, `parse_psd1_json`, `psd1_key`, `psd1_lines`, `psd1_quote`, `Psd1LoadResult`, `serialize_psd1_document`
**In-repo imports:** `mediapipeline.contracts.config`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/load.py`._
