---
file: tests/python/desktop/test_tauri_pg1_close_adversarial_scaffold.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: e1a65bff259847dc3831e39f7ee76df21f099401ea51758f5c21f0d24ec28605
---
# `tests/python/desktop/test_tauri_pg1_close_adversarial_scaffold.py`

**Purpose:** test_tauri_pg1_close_adversarial_scaffold.py PG-1 adversarial close-readiness scaffold test. Verifies that the Tauri shell lib.rs contains all required structural patterns for handling combined active-work + armed-watcher + error close-readiness states. This is a static scaffold test — it does not run Tauri or require real media. PG-1 gate criteria (from the archived Tauri transition plan): Adversarial close-readiness: armed watcher + active work + in-flight commands must all surface in the Tauri native close-prompt dialog before the operator can dismiss. This scaffold test proves the lib.rs code satisfies the structural requirements. Full PG-1 validation requires a live Tauri run with a temporary adversarial backend (see VALIDATION_LADDER_RUNBOOK.md PG-1 section). This test does NOT: - run Tauri - open a window - process media - post commands - mutate any pipeline, settings, queue, rename, or publish state

**Public symbols:** `TestTauriPG1CloseAdversarialScaffold`
**In-repo imports:** `mediapipeline.tools.paths`
**HTTP routes:** `/api/backend/close-readiness`, `/api/pipeline/start`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_tauri_pg1_close_adversarial_scaffold.py`._
