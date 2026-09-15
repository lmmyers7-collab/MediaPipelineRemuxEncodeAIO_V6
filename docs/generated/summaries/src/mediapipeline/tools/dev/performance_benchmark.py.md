---
file: src/mediapipeline/tools/dev/performance_benchmark.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-09-14
last_reviewed: 2026-07-10
sha256: ec5566844b63f1f60255d52c441e1172ba365f8379e3259cbaf75438cb4f8ac7
---
# `src/mediapipeline/tools/dev/performance_benchmark.py`

**Purpose:** Repeatable, read-only performance baselines for the active workspace.

**Classes:** `CommandSample`
**Public functions:** `benchmark_audit_suite()`, `benchmark_backend_import()`, `benchmark_pipeline_module_graph()`, `benchmark_queue_source_inventory()`, `benchmark_static_shell()`, `build_payload()`, `main()`, `parse_args()`, `records_for_payload()`, `run_command_samples()`
**In-repo imports:** `mediapipeline.core.observability.performance`, `mediapipeline.core.paths.contracts`, `mediapipeline.core.queue.source_inventory`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/performance_benchmark.py`._
