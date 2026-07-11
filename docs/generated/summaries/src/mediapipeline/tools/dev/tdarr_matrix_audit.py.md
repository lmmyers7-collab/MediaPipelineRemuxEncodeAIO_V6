---
file: src/mediapipeline/tools/dev/tdarr_matrix_audit.py
pipeline_stage: observability
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-10
last_reviewed: 2026-06-07
sha256: f1ea5f2a3ba4b84f22845fc5a5de5e6800d5ef6b7c15d97a5ab20e3f96c281bc
---
# `src/mediapipeline/tools/dev/tdarr_matrix_audit.py`

**Purpose:** Audit and sample-run harness for the generated Tdarr Matrix test library.

**Classes:** `Finding`, `FixtureProbeResult`, `ManifestRow`, `ProcessOutcome`
**Public functions:** `add_common_arguments()`, `allowed_materialize_source_roots()`, `assert_allowed_run_root()`, `audit_bucket_classification()`, `audit_existing_library()`, `audit_existing_worker_evidence()`, `audit_fixture_video_probes()`, `audit_path_containment()`, `audit_queue_snapshot()`, `audit_source_hashes()`, `audit_worker_result()`, `build_effective_config_command()`, `build_powershell_file_command()`, `build_queue_snapshot_command()`, `build_single_file_command()`, `build_validate_command()`, `command_failure_finding()`, `command_report()`, `command_run_samples()`, `contained_manifest_child()`
**In-repo imports:** `mediapipeline.core.diagnostics.tdarr_matrix_proof`, `mediapipeline.tools.dev`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/tdarr_matrix_audit.py`._
