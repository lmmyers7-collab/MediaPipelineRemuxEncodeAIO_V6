---
file: src/mediapipeline/desktop/application/dto_base.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: application
last_modified: 2026-06-26
last_reviewed: 2026-06-04
sha256: 91c2e432852d2ee370647b21b34b8afe7b69fcdeb2ba359d18af117220a27760
---
# `src/mediapipeline/desktop/application/dto_base.py`

**Purpose:** Compatibility shim. Moved to ``mediapipeline.core.kernel.dto_base`` by ADR-0013 (Wave 3). Re-exports the full public namespace from the new home, including names not listed in ``__all__`` (e.g. ``JsonMap``), so existing imports keep working. New code should import from ``mediapipeline.core.kernel.dto_base`` directly; this shim is removed in the ADR-0013 Wave 6 cleanup.

**In-repo imports:** `mediapipeline.core.kernel`, `mediapipeline.core.kernel.dto_base`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/application/dto_base.py`._
