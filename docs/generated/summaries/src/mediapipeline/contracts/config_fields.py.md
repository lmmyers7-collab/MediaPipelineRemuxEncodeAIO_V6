---
file: src/mediapipeline/contracts/config_fields.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-07-16
last_reviewed: 2026-07-11
sha256: bcb4638830957f0fa771bfac267be63e9605681616c36b537874af58365b1a1c
---
# `src/mediapipeline/contracts/config_fields.py`

**Purpose:** Canonical Pydantic contract for MediaPipeline configuration. The runtime PSD1, the desktop settings schema, and generated JSON Schema share this flat field shape. Field names intentionally match the PSD1 keys instead of using snake_case aliases so round-trips do not need a key map.

**In-repo imports:** `mediapipeline.contracts.config_coercion`, `mediapipeline.contracts.config_defaults`, `mediapipeline.contracts.config_schema_extras`, `mediapipeline.contracts.config_validators`, `mediapipeline.contracts.height_tolerance`, `mediapipeline.core.rename.constants`, `mediapipeline.core.rename.movie`, `mediapipeline.core.rename.tv`, `mediapipeline.core.validation.strict_json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/config_fields.py`._
