---
file: src/mediapipeline/tools/dev/tdarr_matrix_operations.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 2e85173b869ff858a830d977c8ead9b54e5f0d2af1443fdd78af2ec81013227e
---
# `src/mediapipeline/tools/dev/tdarr_matrix_operations.py`

**Purpose:** Audit and sample-run harness for the generated Tdarr Matrix test library.

**Public symbols:** `allowed_materialize_source_roots`, `assert_allowed_run_root`, `build_effective_config_command`, `build_powershell_file_command`, `build_queue_snapshot_command`, `build_single_file_command`, `build_validate_command`, `command_failure_finding`, `default_audit_dir`, `default_config_path`, `default_effective_config_path`, `default_queue_snapshot_path`, `discover_run_roots`, `load_json_object`, `materialize_run_subset`, `plan_run_materialization`, `prepare_pipeline_evidence`, `prepare_run_root`, `prune_run_roots`, `resolve_materialize_source`, `run_subprocess_capture`, `terminate_process_tree`, `text_from_timeout`
**In-repo imports:** `mediapipeline.core.diagnostics.tdarr_matrix_proof`, `mediapipeline.tools.dev`, `mediapipeline.tools.dev.tdarr_matrix_models`, `mediapipeline.tools.paths`
**State/config identifiers:** `effective_config.json`, `queue_snapshot.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/tdarr_matrix_operations.py`._
