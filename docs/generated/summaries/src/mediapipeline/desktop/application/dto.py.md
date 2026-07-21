---
file: src/mediapipeline/desktop/application/dto.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: application
last_modified: 2026-06-26
last_reviewed: 2026-06-04
sha256: a26f1128c0f9617df72b7d585cd115a562df0aa538885ccb0d8e881dfe381943
---
# `src/mediapipeline/desktop/application/dto.py`

**Purpose:** Compatibility shim. Moved to ``mediapipeline.core.kernel.dto`` by ADR-0013 (Wave 4). This aggregator re-exports the kernel DTO families. The full public namespace is copied from the new home so existing imports (including ``application/__init__.py``) keep working. New code should import from ``mediapipeline.core.kernel.dto`` directly; this shim is removed in the ADR-0013 Wave 6 cleanup.

**In-repo imports:** `mediapipeline.core.kernel`, `mediapipeline.core.kernel.dto`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/application/dto.py`._
