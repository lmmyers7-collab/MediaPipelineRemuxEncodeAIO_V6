---
file: src/mediapipeline/tools/dev/tdarr_matrix_audit.py
pipeline_stage: observability
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-08
last_reviewed: 2026-06-07
sha256: 9fd70edad0f09b54e86dda6029d840d3f145ba7142cac1f76d7cce4dd8fc8ebc
---
# `src/mediapipeline/tools/dev/tdarr_matrix_audit.py`

**Purpose:** Audit and sample-run harness for the generated Tdarr Matrix test library.

**Classes:** `Finding`, `FixtureProbeResult`, `ManifestRow`, `ProcessOutcome`
**Public functions:** `add_common_arguments()`, `assert_allowed_run_root()`, `audit_bucket_classification()`, `audit_existing_library()`, `audit_fixture_video_probes()`, `audit_path_containment()`, `audit_queue_snapshot()`, `audit_source_hashes()`, `audit_worker_result()`, `build_effective_config_command()`, `build_powershell_file_command()`, `build_queue_snapshot_command()`, `build_single_file_command()`, `build_validate_command()`, `command_failure_finding()`, `command_report()`, `command_run_samples()`, `default_audit_dir()`, `default_config_path()`, `default_effective_config_path()`
**In-repo imports:** `mediapipeline.tools.dev`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/tdarr_matrix_audit.py`._
