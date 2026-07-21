---
file: src/mediapipeline/core/kernel/__init__.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: low
owner_domain: kernel
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 46b1608589f1ff5a3ed9747be4453724b5e1dacdf2e1967fee0d17dc721d23da
---
# `src/mediapipeline/core/kernel/__init__.py`

**Purpose:** Shared kernel: cross-layer types and constants. Per ADR-0012 / ADR-0013, this package holds types depended on by both ``mediapipeline.core`` and ``mediapipeline.desktop``. It must not import anything else from ``mediapipeline.core.*`` or ``mediapipeline.desktop.*``. Wave 1 (ADR-0013) seeds it with the ``models`` trio.


_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/kernel/__init__.py`._
