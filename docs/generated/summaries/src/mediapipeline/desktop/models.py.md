---
file: src/mediapipeline/desktop/models.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: unknown
last_modified: 2026-06-29
last_reviewed: 2026-06-04
sha256: 9a40a3c1f2b24d034a4455181bc26fd76cf88e40089045a4831d6ad0feeec6c6
---
# `src/mediapipeline/desktop/models.py`

**Purpose:** Compatibility shim. Moved to core-owned record modules by ADR-0013/#23. This module re-exports the public API from its new home. New code should import domain records from their core homes directly; this shim is removed in the ADR-0013 Wave 6 cleanup.

**In-repo imports:** `mediapipeline.core.audit.contracts`, `mediapipeline.core.completed.contracts`, `mediapipeline.core.config.contracts`, `mediapipeline.core.failures.contracts`, `mediapipeline.core.kernel.models`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.queue.contracts`, `mediapipeline.core.status.contracts`, `mediapipeline.core.telemetry.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/models.py`._
