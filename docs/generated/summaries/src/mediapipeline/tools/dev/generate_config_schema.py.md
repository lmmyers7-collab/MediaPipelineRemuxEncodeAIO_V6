---
file: src/mediapipeline/tools/dev/generate_config_schema.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: config
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 89e4ee9d5820b6eb0df1a4ed0c472e39aece21d1e86b6a8608c781f3ba3b4e46
---
# `src/mediapipeline/tools/dev/generate_config_schema.py`

**Purpose:** Generate config JSON Schema artifacts from the authoritative ``Config`` model. The contracts schema contains the complete desktop/Python config shape. The PowerShell-facing mirror intentionally omits ``NETWORK_CONFIG_KEYS`` and uses a consumer-specific ``$id``; all remaining validation keywords are identical. Use ``--check`` in CI/pre-commit/release validation to fail when either shipped artifact is stale. Schema consumers use the committed artifacts; production runtime code never imports this developer-only generator.

**Public symbols:** `main`, `render_schema`
**In-repo imports:** `mediapipeline.tools.paths`
**State/config identifiers:** `config.v1.schema.json`, `media_pipeline_config.schema.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_config_schema.py`._
