---
file: src/mediapipeline/tools/dev/tdarr_proof_pack.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-23
last_reviewed: 2026-06-12
sha256: 355688662dc5897d5ec0d5c7b4467a822b3013e24be0a6fc8eee848cbe58afc2
---
# `src/mediapipeline/tools/dev/tdarr_proof_pack.py`

**Purpose:** Build and clean up the durable Tdarr proof pack.

**Public symbols:** `archive_full_matrix_reports`, `assert_proof_root_allowed`, `cleanup_plan`, `cleanup_target_is_eligible`, `cleanup_target_rows`, `command_cleanup`, `command_materialize`, `copy_source_to_cache`, `default_source_manifest`, `delete_full_matrix`, `is_directory_link`, `is_under`, `link_or_copy`, `load_source_manifest_rows`, `main`, `manifest_case_id_number`, `materialize_proof_pack`, `parse_args`, `path_has_link_component`, `path_size_bytes`, `prepare_proof_root`, `proof_cache_relative_path`, `proof_pack_case_metadata`, `proof_root_identity_payload`, `proof_root_path_identity`, `remove_cleanup_target`, `resolve_path`, `restore_proof_root_after_failure`, `select_proof_rows`, `source_manifest_candidates`
**In-repo imports:** `mediapipeline.core.diagnostics.tdarr_matrix_proof`, `mediapipeline.tools.dev`, `mediapipeline.tools.paths`
**State/config identifiers:** `full_matrix_archive_manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/tdarr_proof_pack.py`._
