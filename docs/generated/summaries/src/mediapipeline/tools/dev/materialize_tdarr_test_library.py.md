---
file: src/mediapipeline/tools/dev/materialize_tdarr_test_library.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-23
last_reviewed: 2026-06-07
sha256: 2b46f515b1867ea54cae35ea5167f078e6436e3716f6037469e238247f2f99d3
---
# `src/mediapipeline/tools/dev/materialize_tdarr_test_library.py`

**Purpose:** Materialize a Tdarr sample matrix as local Movies/TV test libraries.

**Public symbols:** `assert_allowed_library_root`, `case_id`, `classify_bucket`, `diagnostic_bucket`, `display_tokens`, `is_quarantined_sample`, `library_root_identity_payload`, `library_root_path_identity`, `link_or_copy`, `load_inventory`, `main`, `manifest_record`, `materialize`, `materialized_rows`, `MaterializedRow`, `movie_relative_path`, `parse_args`, `parse_views`, `partition_quarantined_samples`, `path_has_link_component`, `prepare_library_root`, `ps_array`, `ps_bool`, `ps_quote`, `render_config`, `render_library_profiles`, `replace_psd1_key`, `resolve_inventory_local_path`, `resolve_repo_path`, `restore_library_root_after_failure`
**In-repo imports:** `mediapipeline.tools.paths`
**State/config identifiers:** `MediaPipeline_config.tdarr-matrix.psd1`, `MediaPipeline_config_template.psd1`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/materialize_tdarr_test_library.py`._
