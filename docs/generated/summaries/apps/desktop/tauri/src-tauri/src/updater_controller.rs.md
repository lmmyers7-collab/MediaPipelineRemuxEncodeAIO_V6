---
file: apps/desktop/tauri/src-tauri/src/updater_controller.rs
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Rust
pipeline_stage: n/a
token_priority: medium
owner_domain: shell
last_modified: 2026-07-23
last_reviewed: 2026-07-23
sha256: 5693f10def125894b25a0eca5880d1c5a6b4d3cc11f6d171515934e31df9b23d
---
# `apps/desktop/tauri/src-tauri/src/updater_controller.rs`

**Purpose:** Rust implementation for updater controller; exposes bounded_evidence_text, cleanup_orphaned_temporary_files, evidence_is_atomic_bounded_and_retained.

**Public symbols:** `bounded_evidence_text`, `cleanup_orphaned_temporary_files`, `evidence_is_atomic_bounded_and_retained`, `fresh_close_readiness`, `install_block_reason`, `new`, `next_launch_reconciles_installer_handoff_by_exact_target_version`, `previous_install_outcome`, `PreviousInstallOutcome`, `prune_evidence_files`, `read_latest_event`, `readiness`, `reconcile_previous_install_handoff`, `record_event`, `record_optional_event`, `record_required_event`, `record_updater_failure`, `remote_text_is_bounded_and_control_characters_are_removed`, `restart_after_stopped_backend`, `run_native_update_check`, `schedule_native_update_check`, `unique_test_directory`, `unix_time_ms`, `unsafe_close_readiness_blocks_installation_without_force_path`, `updater_artifact_mode_enabled`, `updater_check_is_enabled_only_for_artifact_builds`, `updater_evidence_directory`, `updater_evidence_files`, `updater_failure_class`, `updater_failure_classes_separate_network_and_signature_rejection`, `UpdaterEvidence`, `write_event_to_directory`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/tauri/src-tauri/src/updater_controller.rs`._
