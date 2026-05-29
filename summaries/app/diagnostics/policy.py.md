---
file: app/diagnostics/policy.py
pipeline_stage: observability
token_priority: medium
owner_domain: diagnostics
last_modified: 2026-05-28
last_reviewed: 2026-05-28
sha256: 0cf43bcd168a342bb848d5cddb61368e1ed338b42e6a3b9624a501bf02c289e3
---
# `app/diagnostics/policy.py`

**Purpose:** Read-only diagnostics payload and summary policy helpers.

**Public functions:** `clamp_diagnostics_tail_bytes()`, `diagnostics_active_job_detail_rows()`, `diagnostics_active_job_rows()`, `diagnostics_launch_log_summary()`, `diagnostics_summary_lines()`, `diagnostics_tail_base_payload()`, `diagnostics_tail_disallowed_payload()`, `diagnostics_tail_evidence()`, `diagnostics_tail_file_payload()`, `diagnostics_tail_missing_payload()`, `diagnostics_warnings()`
**In-repo imports:** `app.status.active_jobs`, `mediapipeline_desktop_app.models`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths app/diagnostics/policy.py`._
