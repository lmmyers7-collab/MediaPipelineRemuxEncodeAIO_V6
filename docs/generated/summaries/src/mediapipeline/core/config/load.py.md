---
file: src/mediapipeline/core/config/load.py
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: bfd2f8273d04cea06a541a16fa521d0aceb49fef629320ccdb770180cd782b66
---
# `src/mediapipeline/core/config/load.py`

**Purpose:** Canonical PSD1 loader and converter for `mediapipeline.contracts.config`.

**Classes:** `ConfigLoadError`, `Psd1LoadResult`
**Public functions:** `build_psd1_import_args()`, `config_from_mapping()`, `config_to_flat_dict()`, `config_to_psd1()`, `default_powershell_host()`, `load_config()`, `load_psd1_mapping()`, `order_top_level_config()`, `parse_psd1_json()`, `psd1_key()`, `psd1_lines()`, `psd1_quote()`, `serialize_psd1_document()`
**In-repo imports:** `mediapipeline.contracts.config`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/load.py`._
