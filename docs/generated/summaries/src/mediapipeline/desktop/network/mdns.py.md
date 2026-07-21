---
file: src/mediapipeline/desktop/network/mdns.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 74a4906d1b0293a5f9f748012100dba544270fd600873cfb8a6b400fc8fdb512
---
# `src/mediapipeline/desktop/network/mdns.py`

**Purpose:** network.mdns ============ mDNS (Bonjour / DNS-SD) helpers for coordinator auto-discovery. Coordinator advertises on the local network as ``_mediapipeline._tcp``. Workers can scan for coordinators instead of typing the URL manually. Requires the optional ``zeroconf`` library. All public functions gracefully raise :class:`ZeroconfUnavailable` when the library is not installed so the rest of the app never crashes on missing zeroconf. Phase 3: full implementation.

**Public symbols:** `CoordinatorAdvertiser`, `discover_coordinators`, `discover_coordinators_async`, `ZeroconfUnavailable`
**In-repo imports:** `.local_ip`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/mdns.py`._
