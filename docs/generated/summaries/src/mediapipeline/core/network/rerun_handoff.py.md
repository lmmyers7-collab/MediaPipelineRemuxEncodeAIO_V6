---
file: src/mediapipeline/core/network/rerun_handoff.py
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-10
last_reviewed: 2026-07-05
sha256: 4be2d93a1055290dab79ec08b22d16f0c00aa749be5207e9eb0082baa910c8af
---
# `src/mediapipeline/core/network/rerun_handoff.py`

**Purpose:** Network CSV rerun handoff path planning and validation.

**Public functions:** `network_rerun_assign_batch_handoff_paths()`, `network_rerun_handoff_config_errors()`, `network_rerun_handoff_for_row()`, `network_rerun_handoff_forbidden_roots()`, `network_rerun_handoff_root_evidence()`, `probe_network_rerun_handoff_root()`
**In-repo imports:** `mediapipeline.core.config.library_profiles`, `mediapipeline.core.kernel.config_keys`, `mediapipeline.core.paths.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/network/rerun_handoff.py`._
