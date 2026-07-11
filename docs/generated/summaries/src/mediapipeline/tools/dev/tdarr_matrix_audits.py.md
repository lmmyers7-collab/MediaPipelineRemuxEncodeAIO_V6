---
file: src/mediapipeline/tools/dev/tdarr_matrix_audits.py
pipeline_stage: observability
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: b7388ab410f9c609151d3d5b3ebbc8372bc66a0a26831911410ee930ca706fbf
---
# `src/mediapipeline/tools/dev/tdarr_matrix_audits.py`

**Purpose:** Audit and sample-run harness for the generated Tdarr Matrix test library.

**Public functions:** `audit_bucket_classification()`, `audit_existing_worker_evidence()`, `audit_path_containment()`, `audit_queue_snapshot()`, `audit_source_hashes()`, `audit_worker_result()`, `expected_media_kind()`, `failure_artifact_count()`, `iter_json_path_values()`, `iter_json_payloads()`, `load_worker_result()`, `normalized_media_kind()`, `process_outcome_log_excerpt()`, `read_evidence_excerpt()`, `run_sample_processing()`, `startup_config_failure_finding()`
**In-repo imports:** `mediapipeline.core.diagnostics.tdarr_matrix_proof`, `mediapipeline.tools.dev`, `mediapipeline.tools.dev.tdarr_matrix_models`, `mediapipeline.tools.dev.tdarr_matrix_operations`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/tdarr_matrix_audits.py`._
