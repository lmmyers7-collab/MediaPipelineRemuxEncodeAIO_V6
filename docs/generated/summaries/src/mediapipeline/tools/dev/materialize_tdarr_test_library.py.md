---
file: src/mediapipeline/tools/dev/materialize_tdarr_test_library.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-12
last_reviewed: 2026-06-07
sha256: 925bf0cb6189ca43d02745dcc6515836fdc3671ce21e355dfa02139edd8d8275
---
# `src/mediapipeline/tools/dev/materialize_tdarr_test_library.py`

**Purpose:** Materialize a Tdarr sample matrix as local Movies/TV test libraries.

**Classes:** `MaterializedRow`, `TdarrSample`
**Public functions:** `assert_allowed_library_root()`, `case_id()`, `classify_bucket()`, `diagnostic_bucket()`, `display_tokens()`, `is_quarantined_sample()`, `link_or_copy()`, `load_inventory()`, `main()`, `manifest_record()`, `materialize()`, `materialized_rows()`, `movie_relative_path()`, `parse_args()`, `parse_views()`, `partition_quarantined_samples()`, `prepare_library_root()`, `ps_array()`, `ps_bool()`, `ps_quote()`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/materialize_tdarr_test_library.py`._
