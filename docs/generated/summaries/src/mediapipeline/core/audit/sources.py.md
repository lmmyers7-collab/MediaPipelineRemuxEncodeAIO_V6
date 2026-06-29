---
file: src/mediapipeline/core/audit/sources.py
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-06-29
last_reviewed: 2026-06-29
sha256: 3fa4eb9f1c2f119076ecfa3805c249521724d90f93070857f92469b26e072184
---
# `src/mediapipeline/core/audit/sources.py`

**Purpose:** Audit source registry and read-only source metric scanning.

**Public functions:** `audit_source_state_paths()`, `audit_source_state_payload()`, `scan_audit_sources()`, `update_audit_sources()`
**In-repo imports:** `mediapipeline.core.files.constants`, `mediapipeline.core.kernel.dto_base`, `mediapipeline.core.kernel.models_core`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/audit/sources.py`._
