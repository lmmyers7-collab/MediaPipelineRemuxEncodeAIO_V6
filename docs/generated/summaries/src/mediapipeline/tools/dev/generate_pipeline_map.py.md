---
file: src/mediapipeline/tools/dev/generate_pipeline_map.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-12
last_reviewed: 2026-06-04
sha256: d41f05f672ec475af05a3b49ab770a25aa764c633ed22a6c5f8495c3f96e2792
---
# `src/mediapipeline/tools/dev/generate_pipeline_map.py`

**Purpose:** Generate docs/generated/PIPELINE_MAP.md from mediapipeline.contracts.stages. The stage registry in src/mediapipeline/contracts/stages.py is the source for stage order, stage wire name, payload class, result class, Pydantic field lists, and dispatcher backend. This script adds static operator notes for each known stage so the generated Markdown stays useful without letting the contract table drift.

**Public symbols:** `check_file`, `code_list`, `load_stages_module`, `main`, `model_field_names`, `render_pipeline_map`, `stage_value`, `table_cell`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_pipeline_map.py`._
