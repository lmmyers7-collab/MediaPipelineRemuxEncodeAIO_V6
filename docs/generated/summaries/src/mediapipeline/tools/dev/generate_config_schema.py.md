---
file: src/mediapipeline/tools/dev/generate_config_schema.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: config
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: fac2051471245941aa5e7b0e9a5c9e0b456ffaae6d316e4bce508a12217602d8
---
# `src/mediapipeline/tools/dev/generate_config_schema.py`

**Purpose:** Generate the config JSON Schema from `mediapipeline.contracts.config`. Use `--check` in CI/pre-commit to fail when `src/mediapipeline/contracts/schemas/config.v1.schema.json` is stale.

**Public symbols:** `check_current`, `main`, `render_schema`, `write_if_changed`
**In-repo imports:** `mediapipeline.tools.paths`
**State/config identifiers:** `config.v1.schema.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_config_schema.py`._
