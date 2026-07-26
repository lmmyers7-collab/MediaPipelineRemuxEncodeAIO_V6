---
file: src/mediapipeline/desktop/contracts/__init__.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: contracts
token_priority: low
owner_domain: contracts
last_modified: 2026-07-18
last_reviewed: 2026-06-04
sha256: 92a8afd0f1c687aedcc9db58d7a26fb4848f2ccccb8d30f5b7b680f28d602b68
---
# `src/mediapipeline/desktop/contracts/__init__.py`

**Purpose:** Compatibility shim. Moved to ``mediapipeline.core.kernel.contracts`` by ADR-0013 (Wave 5). Re-exports the contracts aggregator public namespace from the new home so existing imports (``from mediapipeline.desktop.contracts import ...``) keep working. New code should import from ``mediapipeline.core.kernel.contracts`` directly; this shim package is removed in the ADR-0013 Wave 6 cleanup.

**In-repo imports:** `mediapipeline.core.kernel`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/contracts/__init__.py`._
