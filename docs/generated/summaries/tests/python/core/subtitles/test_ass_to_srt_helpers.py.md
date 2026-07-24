---
file: tests/python/core/subtitles/test_ass_to_srt_helpers.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: subtitles
token_priority: high
owner_domain: tests
last_modified: 2026-07-22
last_reviewed: 2026-06-04
sha256: b46bef9a6c4a250521005f8e4e9d761cdba297f0fc8402cbe3a5777b4bff6981
---
# `tests/python/core/subtitles/test_ass_to_srt_helpers.py`

**Purpose:** Python implementation for test ass to srt helpers; exposes test_atomic_write_text_does_not_clobber_existing_destination, test_cli_rejects_existing_file_alias_via_hard_link, test_cli_rejects_existing_file_alias_via_symlink.

**Public symbols:** `test_atomic_write_text_does_not_clobber_existing_destination`, `test_cli_rejects_existing_file_alias_via_hard_link`, `test_cli_rejects_existing_file_alias_via_symlink`, `test_cli_rejects_existing_output_before_extraction`, `test_cli_rejects_source_as_srt_output`, `test_cli_rejects_summary_aliases`, `test_cli_rejects_windows_case_variant_of_source`, `test_dialogue_collection_keeps_whitelist_and_tracks_drop_diagnostics`, `test_encoding_selection_can_be_exercised_without_real_pysubs2_loader`, `test_encoding_selection_prefers_clean_cp932_over_longer_single_byte_mojibake`, `test_high_risk_single_byte_fallback_decode_routes_to_review`, `test_import_ass_to_srt_keeps_cli_module_public_surface`, `test_overlap_merge_minimum_gap_and_rendering_are_stable`, `test_text_cleanup_and_srt_rendering_preserve_exact_output_shape`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/core/subtitles/test_ass_to_srt_helpers.py`._
