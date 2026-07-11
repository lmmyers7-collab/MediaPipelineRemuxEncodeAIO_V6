---
file: src/mediapipeline/core/diagnostics/tdarr_matrix_audit.py
pipeline_stage: observability
token_priority: medium
owner_domain: diagnostics
last_modified: 2026-07-10
last_reviewed: 2026-06-07
sha256: 4b31ee89009fee5161ede232e5975302ca2174fe0075c26552ab0e5b25a16c6d
---
# `src/mediapipeline/core/diagnostics/tdarr_matrix_audit.py`

**Purpose:** Backend-owned Tdarr Matrix audit command policy and service runner.

**Classes:** `TdarrMatrixAuditServiceMixin`
**Public functions:** `normalize_tdarr_matrix_audit_action()`, `tdarr_matrix_audit_arguments()`, `tdarr_matrix_audit_exception_result()`, `tdarr_matrix_audit_findings_preview()`, `tdarr_matrix_audit_invalid_action_result()`, `tdarr_matrix_audit_preset()`, `tdarr_matrix_audit_progress_payload()`, `tdarr_matrix_audit_result()`, `tdarr_matrix_audit_runner_timeout()`, `tdarr_matrix_audit_unavailable_result()`, `tdarr_matrix_background_close_evidence()`, `tdarr_matrix_background_run_id()`, `tdarr_matrix_default_entrypoint()`, `tdarr_matrix_default_library_root()`, `tdarr_matrix_default_runs_root()`, `tdarr_matrix_incomplete_full_run()`, `tdarr_matrix_incomplete_full_run_evidence()`, `tdarr_matrix_runner_script()`
**In-repo imports:** `mediapipeline.core.diagnostics.tdarr_matrix_proof`, `mediapipeline.core.kernel.dto_base`, `mediapipeline.core.kernel.runtime.subprocess_runner`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/diagnostics/tdarr_matrix_audit.py`._
