---
file: src/mediapipeline/tools/dev/generate_duplicate_test_name_report.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-17
last_reviewed: 2026-06-17
sha256: 22d7fd440c85e93a9f64b1c4761529ab104af8e171e97657e20798f8c8b13a7d
---
# `src/mediapipeline/tools/dev/generate_duplicate_test_name_report.py`

**Purpose:** Generate a focused exact duplicate Python test-name report. The report groups bare test function/method names that appear in more than one test file. Existing duplicates are review candidates only; --check verifies that the generated report is current.

**Public symbols:** `check_current`, `collect_definitions_from_tree`, `collect_test_definitions`, `duplicate_groups`, `iter_test_files`, `main`, `render_duplicate_test_name_report`, `repo_rel`, `TestDefinition`, `write_if_changed`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_duplicate_test_name_report.py`._
