---
file: src/mediapipeline/desktop/application/dto_status.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: application
last_modified: 2026-06-26
last_reviewed: 2026-06-04
sha256: 98566bd2e8e3be7d7ce29ca209323f322dd146fe3fb6f361c1d46a4465d91bd6
---
# `src/mediapipeline/desktop/application/dto_status.py`

**Purpose:** Compatibility shim. Moved to ``mediapipeline.core.kernel.dto_status`` by ADR-0013 (Wave 4). Re-exports the full public namespace from the new home so existing imports keep working. New code should import from ``mediapipeline.core.kernel.dto_status`` directly; this shim is removed in the ADR-0013 Wave 6 cleanup.

**In-repo imports:** `mediapipeline.core.kernel`, `mediapipeline.core.kernel.dto_status`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/application/dto_status.py`._
