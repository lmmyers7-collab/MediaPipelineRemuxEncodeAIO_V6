---
file: src/mediapipeline/tools/dev/check_legacy_removal_readiness.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 9b57306e040fe9801765a7efbcc746c8014db580c6c4ce2cf072cf57aeecc3bd
---
# `src/mediapipeline/tools/dev/check_legacy_removal_readiness.py`

**Purpose:** Report legacy-surface removal readiness by migration family. This is intentionally report-only by default. Use ``--strict`` with one or more ``--family`` values when a migration slice is ready to enforce deletion.

**Public symbols:** `collect_family_statuses`, `family_files`, `FamilyStatus`, `LegacyFamily`, `main`, `normalize_path`, `reference_matches`, `ReferenceMatch`, `render_report`, `statuses_to_json`, `strict_failures`
**In-repo imports:** `mediapipeline.tools.paths`
**HTTP routes:** `/api/command_payloads.py`, `/api/command_payloads_`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_legacy_removal_readiness.py`._
