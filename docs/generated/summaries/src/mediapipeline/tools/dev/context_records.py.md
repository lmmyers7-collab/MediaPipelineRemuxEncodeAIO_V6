---
file: src/mediapipeline/tools/dev/context_records.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-20
last_reviewed: 2026-07-20
sha256: 5a57e553d0bb6f58988a5bacfe4ee658e9b88d896bd4ee0e911467a363e7fb9d
---
# `src/mediapipeline/tools/dev/context_records.py`

**Purpose:** Build the authoritative typed record catalog for generated AI navigation.

**Public symbols:** `authority_for`, `canonical_path`, `collect_context_records`, `ContextRecord`, `evidence_category_for`, `feature_scores`, `feature_spec`, `FeatureSpec`, `layer_for`, `load_records`, `low_information_terms_for`, `normalize_retrieval_text`, `normalize_retrieval_tier`, `owner_domain_for`, `record_is_retrievable`, `record_serialized_size_bytes`, `records_from_jsonl`, `records_to_jsonl`, `retrieval_terms_for`, `risk_tier_for`, `terms_for`, `token_priority_for`, `validate_record_paths`, `validation_rung_for`
**In-repo imports:** `mediapipeline.tools.dev`, `mediapipeline.tools.dev.context_extractors`, `mediapipeline.tools.paths`
**HTTP routes:** `/api/contract_read.py`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/context_records.py`._
