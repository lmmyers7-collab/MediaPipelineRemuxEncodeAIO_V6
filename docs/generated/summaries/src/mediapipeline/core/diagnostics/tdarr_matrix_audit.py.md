---
file: src/mediapipeline/core/diagnostics/tdarr_matrix_audit.py
pipeline_stage: observability
token_priority: medium
owner_domain: diagnostics
last_modified: 2026-07-11
last_reviewed: 2026-06-07
sha256: 0aef09956b26998afa5ba202fd1a711558a5a94c0a79c9ca3106f89915402968
---
# `src/mediapipeline/core/diagnostics/tdarr_matrix_audit.py`

**Purpose:** Backend-owned Tdarr Matrix audit command policy and service runner.

**Classes:** `TdarrMatrixAuditServiceMixin`
**Public functions:** `tdarr_matrix_background_close_evidence()`, `tdarr_matrix_incomplete_full_run()`, `tdarr_matrix_incomplete_full_run_evidence()`
**In-repo imports:** `mediapipeline.core.diagnostics`, `mediapipeline.core.diagnostics.tdarr_matrix_audit_support`, `mediapipeline.core.diagnostics.tdarr_matrix_proof`, `mediapipeline.core.kernel.dto_base`, `mediapipeline.core.kernel.runtime.subprocess_runner`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/diagnostics/tdarr_matrix_audit.py`._
