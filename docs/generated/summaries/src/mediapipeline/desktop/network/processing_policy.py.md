---
file: src/mediapipeline/desktop/network/processing_policy.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-05
last_reviewed: 2026-06-14
sha256: 281c25e5881408521873c78a9d4abf8132fa2155c73902381f233ac0ae8e6b46
---
# `src/mediapipeline/desktop/network/processing_policy.py`

**Purpose:** Python implementation for processing policy; exposes build_coordinator_processing_policy, build_worker_effective_config, claim_processing_policy.

**Public symbols:** `build_coordinator_processing_policy`, `build_worker_effective_config`, `claim_processing_policy`, `codec_family_from_encoder`, `materialize_worker_effective_config`, `parse_worker_encoder_map`, `quality_tier_from_video_quality`, `resolve_worker_encoder`, `worker_encoder_map_descriptor`, `worker_honor_coordinator_policy_enabled`
**In-repo imports:** `..config_keys`, `.json_policy`, `mediapipeline.core.config.file_io`, `mediapipeline.core.config.library_profile_defaults`, `mediapipeline.core.config.library_profile_state`, `mediapipeline.core.config.load`, `mediapipeline.core.kernel.models`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/processing_policy.py`._
