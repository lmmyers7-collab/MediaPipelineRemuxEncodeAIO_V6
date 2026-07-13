---
file: src/mediapipeline/tools/dev/policy_proof_pack.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-13
last_reviewed: 2026-07-10
sha256: cbe4a077897c161409367941c93cf5e42e2794e9e16bf1da8b91fe4c0e806682
---
# `src/mediapipeline/tools/dev/policy_proof_pack.py`

**Purpose:** Build and verify an isolated, owned-media policy proof pack.

**Public functions:** `apply_config_overlay()`, `assert_allowed_policy_root()`, `assert_output_expectations()`, `command_materialize()`, `command_run()`, `command_verify()`, `drain_isolated_pending_publish()`, `execute_backend_fixture()`, `exit_code_for_policy_result()`, `facts_from_ffprobe_payload()`, `facts_match()`, `is_applicable()`, `is_under()`, `load_catalog()`, `load_json_object()`, `load_source_mapping()`, `main()`, `materialize_policy_proof_pack()`, `output_facts_for_worker()`, `parse_args()`
**In-repo imports:** `mediapipeline.contracts.source_media_streams`, `mediapipeline.tools.dev`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/policy_proof_pack.py`._
