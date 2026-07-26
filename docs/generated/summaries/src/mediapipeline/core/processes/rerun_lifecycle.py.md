---
file: src/mediapipeline/core/processes/rerun_lifecycle.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-23
last_reviewed: 2026-07-14
sha256: 0d2c6a796d787ab67804d94ad9ce42c4bb8ae8599d6dcc5a4f9eb099758f57cc
---
# `src/mediapipeline/core/processes/rerun_lifecycle.py`

**Purpose:** Durable backend-owned lifecycle evidence for local CSV rerun launches.

**Public symbols:** `create_rerun_enrollment`, `finalize_rerun_enrollment_after_exit`, `find_rerun_recovery_enrollment`, `force_terminalize_rerun_enrollment`, `new_rerun_correlation`, `read_rerun_startup_reconciliation`, `reconcile_local_rerun_enrollments`, `record_rerun_spawn_transition_ambiguity`, `record_rerun_spawn_transition_failure`, `rerun_execution_manifest_root`, `rerun_lifecycle_counts`, `rerun_manifest_declared_path_matches_actual`, `rerun_manifest_matches_enrollment`, `rerun_manifest_path_matches_canonical_batch`, `rerun_recovery_enrollment_guard`, `rerun_startup_reconciliation_path`, `RerunCorrelation`, `transition_rerun_enrollment`
**In-repo imports:** `mediapipeline.core.paths.contracts`, `mediapipeline.core.processes.active_jobs`, `mediapipeline.core.processes.file_io`, `mediapipeline.core.rerun.evidence`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/processes/rerun_lifecycle.py`._
