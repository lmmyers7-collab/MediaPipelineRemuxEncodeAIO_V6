---
file: src/mediapipeline/tools/dev/tdarr_matrix_models.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 23edf7837e3fa502da5215458c93e992c52f48398788c9c6e733d1b0c0484948
---
# `src/mediapipeline/tools/dev/tdarr_matrix_models.py`

**Purpose:** Audit and sample-run harness for the generated Tdarr Matrix test library.

**Classes:** `Finding`, `FixtureProbeResult`, `ManifestRow`, `ProcessOutcome`
**Public functions:** `audit_fixture_video_probes()`, `codec_container_key()`, `contained_manifest_child()`, `ffprobe_command_available()`, `filter_auto_sample_probe_mismatches()`, `finding_for_row()`, `fixture_probe_evidence()`, `fixture_probe_mismatch_finding()`, `fixture_probe_unavailable_finding()`, `has_usable_video_stream()`, `int_value()`, `is_under()`, `load_manifest_rows()`, `manifest_case_key()`, `manifest_row_declares_video()`, `normalized_token()`, `path_key()`, `probe_fixture_row()`, `resolve_default_powershell()`, `resolve_path()`
**In-repo imports:** `mediapipeline.core.diagnostics.tdarr_matrix_proof`, `mediapipeline.tools.dev`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/tdarr_matrix_models.py`._
