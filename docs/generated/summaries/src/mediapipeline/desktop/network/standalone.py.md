---
file: src/mediapipeline/desktop/network/standalone.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-23
last_reviewed: 2026-06-04
sha256: c07c217642feb8dde3c3bcf54aff9fb81fca99c24013c3a2881289b8113ce8b9
---
# `src/mediapipeline/desktop/network/standalone.py`

**Purpose:** network.standalone ================== ``StandaloneDispatcher`` — wraps the existing single-machine queue behaviour. This is the default dispatcher used when ``NetworkRole == "standalone"``. It wraps the ``queue_records`` list that the app already maintains. Claims, releases, and terminal completion share application-scoped reservation state so separately created dispatcher instances cannot claim one record twice. No networking or filesystem side effects.

**Public symbols:** `StandaloneDispatcher`
**In-repo imports:** `.dispatcher`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/standalone.py`._
