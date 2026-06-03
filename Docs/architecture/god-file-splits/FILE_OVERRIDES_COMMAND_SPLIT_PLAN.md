# File Overrides Command Split Plan

Date: 2026-06-03

## Scope

Target file:
`app/api/commands_file_overrides.py`

Current audit signal:

- 2,984 lines.
- Largest backend Python god-file candidate in the 2026-06-03 audit.
- Lower fan-in than the WebView files, but high blast radius because it mixes
  Local API route payloads, route preview, folder preview, track probing,
  selector validation, effective override metadata, and the command mixin.

This is a backend Local API split. Backend ownership of route decisions, file
override persistence, track probing, and validation must remain unchanged.

## Placement

Use a focused package under `app/api/`:

- `app/api/file_overrides/`

Keep `app/api/commands_file_overrides.py` as the thin compatibility/mixin entry
point until imports and tests prove callers can move to the new package.

## Proposed Slices

1. `app/api/file_overrides/results.py`
   - Move generic command-result helpers:
     `_fo_command_result_payload`, `_fo_unavailable`, `_fo_error`,
     `_fo_validation_error`, `_fo_read_error`, route/folder error helpers, and
     unsupported-key error helpers.

2. `app/api/file_overrides/route_preview.py`
   - Move route-preview validation and payload construction.
   - Candidate functions include `_normalize_route_name`,
     `_load_route_preview_snapshot_row`, `_validate_route_preview_proposal`,
     `_route_preview_current_payload`, `_route_preview_proposed_payload`,
     `_route_preview_impact`, and `_file_override_route_preview_payload`.

3. `app/api/file_overrides/folder_preview.py`
   - Move folder-preview and folder-rule validation/payload construction.
   - Candidate functions include `_validate_folder_preview_options`,
     `_validate_folder_preview_proposal`, `_validate_folder_rule_override`,
     `_validate_folder_rule_confirmation`, `_folder_preview_load_snapshot_rows`,
     `_folder_preview_sample_row`, `_folder_preview_conflicts`,
     `_folder_preview_scope_payload`, `_file_override_folder_preview_payload`,
     `_folder_rule_manifest_entry`, and `_folder_rule_command_payload`.

4. `app/api/file_overrides/tracks.py`
   - Move track probing, audio/subtitle track normalization, display helpers,
     and probe-result payload conversion.
   - Candidate functions include `_probe_tracks_for_source_path`,
     `_file_override_tracks_payload_from_probe_result`,
     `_audio_track_payload`, `_subtitle_track_payload`,
     `_audio_track_display`, and `_subtitle_track_display`.

5. `app/api/file_overrides/selectors.py`
   - Move selector matching, selector warning construction, exact selector
     validation, and track selection preview.
   - Candidate functions include `_track_matches_selector`,
     `_append_selector_warnings`, `_track_selection_section`,
     `_track_selection_preview`, `_override_exact_selector_validation`,
     `_override_exact_selectors`, and `_exact_selector_signature_errors`.

6. `app/api/file_overrides/effective_fields.py`
   - Move effective profile/library response and drawer-field metadata helpers.
   - Candidate functions include `_profile_effective_media`,
     `_profile_effective_route_settings`, `_library_response`,
     `_inherited_drawer_fields`, `_override_drawer_fields`,
     `_effective_drawer_fields`, `_expanded_field_metadata`,
     `_expanded_effective_fields`, `_expanded_scalar_field_metadata`,
     `_expanded_route_video_fields`, `_route_video_processing_projection`, and
     `_file_override_effective_payload`.

## Parent Responsibilities To Preserve

- `LocalApiFileOverridesCommandPayloadMixin` remains in
  `commands_file_overrides.py` initially.
- Existing route methods keep the same names and response envelopes.
- Strict JSON handling, confirmation checks, source-path policy, and command
  journal behavior must not change.
- No source media, output media, queue state, or settings persistence behavior
  changes during this split.

## Validation

After each slice:

```powershell
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_application_facade_queue -q
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_api_command_contracts -q
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_api_contract_payload -q
.\DesktopApp\Runtime\Python\python.exe scripts\dev\check_dependency_boundaries.py
.\DesktopApp\Runtime\Python\python.exe scripts\dev\check_godfiles.py --paths app/api/commands_file_overrides.py
```

If file override route behavior changes, also run the relevant WebView Queue
smokes and route ownership checks.
