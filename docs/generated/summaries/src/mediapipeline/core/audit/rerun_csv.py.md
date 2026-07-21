---
file: src/mediapipeline/core/audit/rerun_csv.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: 27fe75a4192e42b0108dfc5b62b8fcb0112d174746adbec6028502048e98a990
---
# `src/mediapipeline/core/audit/rerun_csv.py`

**Purpose:** Python implementation for rerun csv; exposes append_rerun_note, apply_rerun_source_metadata, build_rerun_csv_row.

**Public symbols:** `append_rerun_note`, `apply_rerun_source_metadata`, `build_rerun_csv_row`, `disable_duplicate_planned_output_rows`, `normalize_rerun_output_container`, `normalize_rerun_planned_output_key`, `normalize_source_content_sha256`, `normalize_source_content_sha256_algorithm`, `planned_output_key_for_rerun_row`, `rerun_output_container_from_config`, `source_stat_to_rerun_values`
**In-repo imports:** `mediapipeline.core.audit.contracts`, `mediapipeline.core.audit.rerun_records`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/audit/rerun_csv.py`._
