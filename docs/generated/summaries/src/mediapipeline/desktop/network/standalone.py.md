---
file: src/mediapipeline/desktop/network/standalone.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 3161ec701c1e4c8a556c0d430d296b971ed6999db322a9825df165343cc9c059
---
# `src/mediapipeline/desktop/network/standalone.py`

**Purpose:** network.standalone ================== ``StandaloneDispatcher`` — wraps the existing single-machine queue behaviour. This is the default dispatcher used when ``NetworkRole == "standalone"``. It is a thin wrapper around the queue_records list that the app already maintains. Behaviour is byte-for-byte identical to what the app did before the dispatcher abstraction was introduced — the wrapper exists purely so the rest of the app can call ``dispatcher.claim_next()`` without knowing which mode is active. No networking, no locking beyond what was already present, no side effects.

**Public symbols:** `StandaloneDispatcher`
**In-repo imports:** `.dispatcher`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/standalone.py`._
