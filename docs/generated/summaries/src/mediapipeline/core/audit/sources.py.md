---
file: src/mediapipeline/core/audit/sources.py
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-07-08
last_reviewed: 2026-06-29
sha256: 9d3a5e6ff3eb45e3485acb37373e5880daff5a4210c1e4501706c7e8f2b90f93
---
# `src/mediapipeline/core/audit/sources.py`

**Purpose:** Audit source registry and read-only source metric scanning.

**Classes:** `AuditSourceMetricsServiceMixin`, `AuditSourceRegistryError`
**Public functions:** `audit_source_state_paths()`, `audit_source_state_payload()`, `scan_audit_sources()`, `sync_audit_sources_from_completed_audit()`, `update_audit_sources()`
**In-repo imports:** `mediapipeline.core.files.constants`, `mediapipeline.core.kernel.dto_base`, `mediapipeline.core.paths.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/audit/sources.py`._
