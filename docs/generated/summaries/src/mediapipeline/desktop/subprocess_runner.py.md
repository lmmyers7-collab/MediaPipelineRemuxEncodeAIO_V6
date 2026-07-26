---
file: src/mediapipeline/desktop/subprocess_runner.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: unknown
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 90884d7e51de485727a7e3ebb0a44b7081c064d83b85e9e606e4df6335008534
---
# `src/mediapipeline/desktop/subprocess_runner.py`

**Purpose:** Compatibility shim. Moved to ``mediapipeline.core.kernel.runtime.subprocess_runner`` by ADR-0013 (Wave 2). This module re-exports the public API from its new home. New code should import from ``mediapipeline.core.kernel.runtime.subprocess_runner`` directly; this shim is removed in the ADR-0013 Wave 6 cleanup.

**In-repo imports:** `mediapipeline.core.kernel.runtime.subprocess_runner`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/subprocess_runner.py`._
