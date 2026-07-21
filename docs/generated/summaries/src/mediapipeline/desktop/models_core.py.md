---
file: src/mediapipeline/desktop/models_core.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: unknown
last_modified: 2026-06-29
last_reviewed: 2026-06-04
sha256: 03e9fb076bb516f9ebd74dc6bcc80630732df670333ae66b7ae5880f5c0e3aac
---
# `src/mediapipeline/desktop/models_core.py`

**Purpose:** Compatibility shim. Moved to core-owned record modules by ADR-0013/#23. This module re-exports the public API from its new home. New code should import domain records from their core homes directly; this shim is removed in the ADR-0013 Wave 6 cleanup.

**In-repo imports:** `mediapipeline.core.config.contracts`, `mediapipeline.core.kernel.models_core`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.status.contracts`, `mediapipeline.core.telemetry.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/models_core.py`._
