---
file: src/mediapipeline/core/audit/sources.py
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-07-02
last_reviewed: 2026-06-29
sha256: 5fdf7e338d9625ca427be102e0ca83c6a9307ba877a499bfe514b7667740d5f1
---
# `src/mediapipeline/core/audit/sources.py`

**Purpose:** Audit source registry and read-only source metric scanning.

**Classes:** `AuditSourceMetricsServiceMixin`
**Public functions:** `audit_source_state_paths()`, `audit_source_state_payload()`, `scan_audit_sources()`, `sync_audit_sources_from_completed_audit()`, `update_audit_sources()`
**In-repo imports:** `mediapipeline.core.files.constants`, `mediapipeline.core.kernel.dto_base`, `mediapipeline.core.paths.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/audit/sources.py`._
