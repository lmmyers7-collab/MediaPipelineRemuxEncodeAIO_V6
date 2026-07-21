---
file: src/mediapipeline/desktop/network/__init__.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: low
owner_domain: network
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 80ad0f4c7a22b9faffd0ce3e8899c2e1ceaeb7c5d431f23a3b41e37a07c830ce
---
# `src/mediapipeline/desktop/network/__init__.py`

**Purpose:** network ======= Standalone / Coordinator / Worker distributed queue architecture. Public API ---------- ``get_dispatcher(app)`` Factory that reads ``NetworkRole`` from the resolved config and returns the appropriate ``QueueDispatcher`` implementation. Unknown or missing roles fail closed instead of falling back to local work. ``QueueDispatcher``, ``ClaimedJob`` Re-exported for callers that need type annotations without importing the sub-module directly. Phases ------ * Phase 0/1: Standalone and Coordinator modes are production-ready. * Phase 2: Worker mode is production-ready as of this implementation. * Phase 3: mDNS auto-discovery and per-worker config overrides — production-ready.

**Public symbols:** `get_dispatcher`
**In-repo imports:** `.dispatcher`, `.standalone`, `mediapipeline.core.processes.pipeline_policy`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/__init__.py`._
