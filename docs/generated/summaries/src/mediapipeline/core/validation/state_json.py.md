---
file: src/mediapipeline/core/validation/state_json.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: validation
last_modified: 2026-07-24
last_reviewed: 2026-07-20
sha256: 0c84790d9402c8c5624544db5b2f1cb98313826982ee06c8053e439cb307c08f
---
# `src/mediapipeline/core/validation/state_json.py`

**Purpose:** Strict, bounded JSON reads for persisted state and evidence files. This boundary is intentionally separate from HTTP JSON handling. Persisted files may be partially written, retained for operator evidence, or supplied by an older runtime, so readers must fail without mutating or replacing the source artifact.

**Public symbols:** `loads_bounded_state_json`, `read_bounded_state_json`, `require_supported_schema_version`, `StateJsonError`, `StateSchemaVersionError`
**In-repo imports:** `mediapipeline.core.validation.strict_json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/validation/state_json.py`._
