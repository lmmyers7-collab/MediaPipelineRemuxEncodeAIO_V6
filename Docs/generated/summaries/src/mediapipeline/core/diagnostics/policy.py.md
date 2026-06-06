---
file: src/mediapipeline/core/diagnostics/policy.py
pipeline_stage: observability
token_priority: medium
owner_domain: diagnostics
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 4f9b7c9c3bf31ab843b5aad35e1877a30c72958ef0c624e5bad49475b7870645
---
# `src/mediapipeline/core/diagnostics/policy.py`

**Purpose:** Read-only diagnostics payload and summary policy helpers.

**Public functions:** `clamp_diagnostics_tail_bytes()`, `diagnostics_active_job_detail_rows()`, `diagnostics_active_job_rows()`, `diagnostics_launch_log_summary()`, `diagnostics_summary_lines()`, `diagnostics_tail_base_payload()`, `diagnostics_tail_disallowed_payload()`, `diagnostics_tail_evidence()`, `diagnostics_tail_file_payload()`, `diagnostics_tail_line_contains_term()`, `diagnostics_tail_missing_payload()`, `diagnostics_warnings()`
**In-repo imports:** `mediapipeline.core.status.active_jobs`, `mediapipeline.desktop.models`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/diagnostics/policy.py`._
