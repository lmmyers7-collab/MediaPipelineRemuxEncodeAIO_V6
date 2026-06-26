# Worker Review: worker-02-core-config-settings-library

## Scope

- Worker ID: `worker-02-core-config-settings-library`
- Assigned slice: config/settings/library surfaces, including `src/mediapipeline/core/config/`, backend settings metadata/builders, PSD1/config parsing helpers, config schema/default/persistence logic, effective settings/profile inheritance, and assigned final-library promotion helpers.
- Review mode: static/repro audit only. No source fixes, refactors, commits, media mutation, runtime queue mutation, or aggregate review files were changed.
- Report/change packet writes only:
  - `docs/reviews/function-module-audit-2026-06-11/workers/worker-02-core-config-settings-library.md`
  - `ops/release/changes/unreleased/MP-CHANGE-2026-0610-006.json`

Required first reads were completed: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, and `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`.

## Coverage Ledger

Coverage is complete for the assigned worker slice at module/function level. Generated schema review focused on assigned config behavior: defaults, required keys, profile shape, and conditional validation. Static metadata modules were reviewed as backend field/default registries rather than runtime algorithms.

PowerShell config/library modules reviewed:

- `ops/pipeline/engine/config/choice_registry.ps1`
- `ops/pipeline/engine/config/config_keys.ps1`
- `ops/pipeline/engine/config/config_schema.ps1`
- `ops/pipeline/engine/config/default_values.ps1`
- `ops/pipeline/engine/config/getters.ps1`
- `ops/pipeline/engine/config/library_overrides.ps1`
- `ops/pipeline/engine/config/runtime_config.ps1`
- `ops/pipeline/engine/config/runtime_merge.ps1`
- `ops/pipeline/engine/config/runtime_paths.ps1`
- `ops/pipeline/engine/config/runtime_validation.ps1`
- `ops/pipeline/engine/config/schema_keys.ps1`
- `ops/pipeline/engine/config/schema_validation.ps1`
- `ops/pipeline/engine/library/library_index.ps1`

Python config/settings/library modules reviewed:

- `src/mediapipeline/contracts/schemas/config.v1.schema.json`
- `src/mediapipeline/core/config/__init__.py`
- `src/mediapipeline/core/config/constants.py`
- `src/mediapipeline/core/config/contracts.py`
- `src/mediapipeline/core/config/document_runner.py`
- `src/mediapipeline/core/config/encoding_capabilities.py`
- `src/mediapipeline/core/config/file_io.py`
- `src/mediapipeline/core/config/identity.py`
- `src/mediapipeline/core/config/library_profile_defaults.py`
- `src/mediapipeline/core/config/library_profile_normalization.py`
- `src/mediapipeline/core/config/library_profile_promotion.py`
- `src/mediapipeline/core/config/library_profile_state.py`
- `src/mediapipeline/core/config/library_profile_validation.py`
- `src/mediapipeline/core/config/library_profile_wizard.py`
- `src/mediapipeline/core/config/library_profiles.py`
- `src/mediapipeline/core/config/load.py`
- `src/mediapipeline/core/config/metadata.py`
- `src/mediapipeline/core/config/metadata_choices.py`
- `src/mediapipeline/core/config/metadata_layout.py`
- `src/mediapipeline/core/config/metadata_network.py`
- `src/mediapipeline/core/config/metadata_parts/__init__.py`
- `src/mediapipeline/core/config/metadata_parts/advanced_fields.py`
- `src/mediapipeline/core/config/metadata_parts/basic_fields.py`
- `src/mediapipeline/core/config/metadata_parts/basic_media_policy.py`
- `src/mediapipeline/core/config/metadata_parts/basic_paths.py`
- `src/mediapipeline/core/config/metadata_parts/basic_processing.py`
- `src/mediapipeline/core/config/metadata_parts/field_definitions.py`
- `src/mediapipeline/core/config/metadata_parts/field_display.py`
- `src/mediapipeline/core/config/metadata_parts/field_registry.py`
- `src/mediapipeline/core/config/metadata_parts/field_scope.py`
- `src/mediapipeline/core/config/metadata_parts/network_fields.py`
- `src/mediapipeline/core/config/metadata_parts/policy.py`
- `src/mediapipeline/core/config/metadata_parts/queue_fields.py`
- `src/mediapipeline/core/config/metadata_parts/subtitle_fields.py`
- `src/mediapipeline/core/config/metadata_parts/video_fields.py`
- `src/mediapipeline/core/config/metadata_support.py`
- `src/mediapipeline/core/config/numeric_policy.py`
- `src/mediapipeline/core/config/option_policy.py`
- `src/mediapipeline/core/config/path_warnings.py`
- `src/mediapipeline/core/config/preset_compatibility.py`
- `src/mediapipeline/core/config/preset_display_adapter.py`
- `src/mediapipeline/core/config/preset_encoding_sections.py`
- `src/mediapipeline/core/config/preset_migration.py`
- `src/mediapipeline/core/config/preset_migration_models.py`
- `src/mediapipeline/core/config/preset_policy.py`
- `src/mediapipeline/core/config/preview.py`
- `src/mediapipeline/core/config/profiles.py`
- `src/mediapipeline/core/config/recovery.py`
- `src/mediapipeline/core/config/rollout.py`
- `src/mediapipeline/core/config/save_runner.py`
- `src/mediapipeline/core/config/service.py`
- `src/mediapipeline/core/config/settings_facade.py`
- `src/mediapipeline/core/config/settings_helpers_facade.py`
- `src/mediapipeline/core/config/settings_patch_candidate_facade.py`
- `src/mediapipeline/core/config/settings_patch_policy.py`
- `src/mediapipeline/core/config/settings_policy.py`
- `src/mediapipeline/core/config/settings_risk_facade.py`
- `src/mediapipeline/core/config/settings_wizard.py`
- `src/mediapipeline/core/config/settings_wizard_facade.py`
- `src/mediapipeline/core/config/validation.py`
- `src/mediapipeline/core/config/value_checks.py`

Final-library modules reviewed:

- `src/mediapipeline/core/final_library/__init__.py`
- `src/mediapipeline/core/final_library/facade.py`
- `src/mediapipeline/core/final_library/promotion.py`
- `src/mediapipeline/core/final_library/promotion_parts/__init__.py`
- `src/mediapipeline/core/final_library/promotion_parts/cleanup.py`
- `src/mediapipeline/core/final_library/promotion_parts/planning.py`
- `src/mediapipeline/core/final_library/promotion_parts/results.py`
- `src/mediapipeline/core/final_library/promotion_parts/transfer.py`
- `src/mediapipeline/core/final_library/service.py`

## Findings Summary

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 2 |
| Medium | 2 |
| Low | 0 |

| ID | Severity | File | Symbol/section | Summary |
|---|---|---|---|---|
| W02-001 | High | `src/mediapipeline/core/config/validation.py` | `validate_config_values` root path validation | Python settings save/preview treats source/output/scratch overlap as warning-only while PowerShell runtime schema rejects the same layout as an error. |
| W02-002 | High | `src/mediapipeline/core/final_library/promotion_parts/transfer.py` | `companion_sidecars` | Final-library sidecar discovery includes adjacent media files such as `Movie.sample.mkv`; cleanup-after-verified can then delete them from the publish root. |
| W02-003 | Medium | `src/mediapipeline/core/config/settings_patch_candidate_facade.py` | `_settings_patch_candidate` OCR validation filter | Patch preview suppresses unchanged OCR conversion toggles, so unrelated previews can look valid even when full merged config fails OCR tool validation. |
| W02-004 | Medium | `ops/pipeline/engine/config/default_values.ps1` | `Get-MediaPipelineConfigDefaultValues` | PowerShell setup defaults use `C:\Videos\...` roots while generated config schema/identity/template defaults use `C:\MediaPipeline\...`, leaving default-source drift unguarded. |

## Detailed Findings

### W02-001 - Python Settings validation allows root overlap that runtime schema rejects

- Severity: High
- File / symbol: `src/mediapipeline/core/config/validation.py:234` `validate_config_values`
- Supporting code: `src/mediapipeline/core/config/path_warnings.py:59`, `src/mediapipeline/core/config/document_runner.py:37`, `ops/pipeline/engine/config/schema_validation.ps1:151`
- Evidence:
  - Python overlap checks return warning strings for identical/nested root paths in `config_path_overlap_warning` and `config_root_path_warnings` (`path_warnings.py:75-84`, `path_warnings.py:103-119`).
  - `validate_config_values` appends those root checks to `warnings`, not `errors` (`validation.py:271-277`).
  - The save document preflight calls `service.validate_config_values(config_values)` and then only verifies PSD1 syntax via `Import-PowerShellDataFile` (`document_runner.py:49-63`).
  - The PowerShell runtime schema treats the same root pairs as hard errors: equal paths error at `schema_validation.ps1:183-184`; nested paths error at `schema_validation.ps1:185-187`.
  - Repro evidence:
    - Python with contract defaults plus `SourceMovies=C:\Media\Processed\IncomingMovies`, `Outsource=C:\Media\Processed`: `python_errors=[]`; warnings include `SourceMovies is inside Outsource. Keep source, output, and scratch roots separated.`
    - PowerShell `Test-MediaPipelineConfigSchema` with equivalent overrides: `ps_ok=False`; `ps_errors=Outsource and SourceMovies must not be nested inside each other.`
- Impact: Settings preview/save can accept and persist a path layout that later fails pipeline launch validation. This is also a media-boundary risk because it weakens the source/output/scratch separation policy at the backend Settings boundary.
- Fix direction: Make Python settings save validation share the PowerShell path-shape policy. Either promote root overlap warnings to errors for save/patch paths or run `Test-MediaPipelineConfigSchema` against the generated candidate document before save.
- Validation to add: Python and PowerShell parity tests for `SourceMovies`/`SourceTV`/`Outsource`/`LocalBase` equal and nested cases; Settings Patch preview/save tests that these cases block config writes.

### W02-002 - Companion sidecar discovery can copy and delete adjacent media files

- Severity: High
- File / symbol: `src/mediapipeline/core/final_library/promotion_parts/transfer.py:373` `companion_sidecars`
- Supporting code: `src/mediapipeline/core/final_library/promotion.py:558`, `src/mediapipeline/core/final_library/promotion.py:592`, `src/mediapipeline/core/final_library/promotion_parts/cleanup.py:37`
- Evidence:
  - `companion_sidecars` confirms only the primary file suffix is media (`transfer.py:373-375`), then includes every sibling file whose name starts with `primary.stem + "."` and is not a temp promotion file (`transfer.py:380-388`).
  - It does not exclude companion files whose suffix is in `MEDIA_FILE_SUFFIXES`, even though that constant is imported at `transfer.py:10`.
  - `promote_item` sends these companions into the copy plan (`promotion.py:558-563`), records verified copies (`promotion.py:589`), and when cleanup is enabled calls `cleanup_verified_files` (`promotion.py:592-593`).
  - `cleanup_verified_files` deletes every verified source path that remains under the publish root (`cleanup.py:47-50`).
  - Repro evidence using a temp directory: `companion_sidecars(Movie.mkv)` returned `['Movie.en.srt', 'Movie.sample.mkv']`.
  - Existing test coverage at `tests/python/desktop/test_final_library_promotion.py:914-929` verifies `.srt`/`.json` companions and temp exclusion, but not adjacent media suffix exclusion.
- Impact: A publish folder containing `Movie.mkv` plus `Movie.sample.mkv`, `Movie.trailer.mp4`, or another dot-suffixed media variant can copy that second media file to the final library as if it were a sidecar. With `FinalLibraryPromotionCleanupAfterVerified` enabled, the adjacent publish-root media file is then deleted after verification.
- Fix direction: Restrict companion discovery to explicit sidecar/manifest suffixes, or at minimum exclude `item.suffix.casefold() in MEDIA_FILE_SUFFIXES` for companion files unless an intentional media-companion policy is added.
- Validation to add: Final-library promotion test with `Movie.mkv`, `Movie.en.srt`, and `Movie.sample.mkv`; expected plan includes only `.srt` and excludes the second media file, including cleanup-after-verified mode.

### W02-003 - Patch preview hides existing OCR tool blockers when OCR keys are unchanged

- Severity: Medium
- File / symbol: `src/mediapipeline/core/config/settings_patch_candidate_facade.py:117` `_settings_patch_candidate`
- Supporting code: `src/mediapipeline/core/config/validation.py:150`
- Evidence:
  - `_ocr_tool_path_errors` only checks BDPGS/VobSub OCR tool paths when the conversion toggle or matching tool path appears in `changed_keys` (`settings_patch_candidate_facade.py:98-110`).
  - Before calling the shared validator, `_settings_patch_candidate` removes `ConvertBdpgsToSrt` and `ConvertVobSubToSrt` from `validation_values` when the OCR keys are not in `changed_keys` (`settings_patch_candidate_facade.py:212-217`).
  - The full validator does correctly reject `ConvertBdpgsToSrt=True` with blank `BdpgsOcrToolPath` (`validation.py:150-156`, `validation.py:278-280`).
  - Save eventually calls `save_config_document` with the full merged config (`src/mediapipeline/core/orchestration/settings_patch_facade.py:196-203`), so this is a preview/early-validation drift rather than a silent successful save.
  - Repro evidence with contract defaults, an existing `ConvertBdpgsToSrt=True` and blank `BdpgsOcrToolPath`, plus unrelated `RoutingProfile` change:
    - `patch_local_ocr_errors=[]`
    - filtered validator OCR errors: `[]`
    - full validator OCR errors: `['ConvertBdpgsToSrt requires BdpgsOcrToolPath.']`
- Impact: An unrelated Settings Patch preview can return `ok=True` even though the merged config is invalid under full backend validation. The operator sees a false green preview, and Save can fail later through the document save path instead of the normal patch validation result.
- Fix direction: Validate the full merged config for preview/save. If the UI needs to distinguish existing blockers from proposed-change blockers, report them as a separate field rather than removing conversion toggles before validation.
- Validation to add: `test_application_facade_settings_patch.py` regression where base config has BDPGS OCR enabled with blank tool path and an unrelated setting change; preview must include the OCR error and `ok=False`.

### W02-004 - PowerShell setup defaults drift from generated schema and identity defaults

- Severity: Medium
- File / symbol: `ops/pipeline/engine/config/default_values.ps1:161` `Get-MediaPipelineConfigDefaultValues`
- Supporting code: `src/mediapipeline/contracts/schemas/config.v1.schema.json:173`, `src/mediapipeline/core/config/identity.py:22`
- Evidence:
  - PowerShell shared defaults use `C:\Videos` roots: `SourceMovies=C:\Videos\Incoming\Movies`, `SourceTV=C:\Videos\Incoming\TV`, `Outsource=C:\Videos\Processed`, `LocalBase=C:\Videos\Scratch` (`default_values.ps1:161-214`).
  - Generated config schema defaults use `C:\MediaPipeline` roots (`config.v1.schema.json:173-186`, `config.v1.schema.json:430-431`).
  - Config identity template-path blocking only recognizes the `C:\MediaPipeline` root set (`identity.py:22-27`), and reports template/default matches from those values (`identity.py:95-110`).
  - Repro evidence:
    - `Get-MediaPipelineConfigDefaultValues`: `ps_SourceMovies=C:\Videos\Incoming\Movies`, `ps_Outsource=C:\Videos\Processed`, `ps_LocalBase=C:\Videos\Scratch`
    - `mediapipeline.contracts.config.Config()`: `contract_SourceMovies=C:\MediaPipeline\Incoming\Movies`, `contract_Outsource=C:\MediaPipeline\Processed`, `contract_LocalBase=C:\MediaPipeline\Scratch`
- Impact: The backend has two different default root families. Setup/default-profile flows that rely on the PowerShell default provider can seed `C:\Videos` paths while the generated schema, WebView contract, and template identity guard document/block `C:\MediaPipeline` paths. That makes default-source drift easy to miss and can leave one placeholder-default family outside the identity block.
- Fix direction: Pick one canonical default source and align `Get-MediaPipelineConfigDefaultValues`, generated contract/schema defaults, config template/default profile roots, and `TEMPLATE_PATH_VALUES`. Add a drift test that compares critical root defaults across these sources.
- Validation to add: PowerShell/Python default parity test for `SourceMovies`, `SourceTV`, `Outsource`, `LocalBase`, `LibraryProfiles` default path fields, and critical media-policy defaults such as `VideoQuality`.

## Test Coverage Gaps

- No test currently asserts that Python Settings save/preview rejects the same root-overlap cases that PowerShell `Test-MediaPipelineConfigSchema` rejects.
- Existing path-warning tests intentionally assert warning behavior, but there is no save-path parity test for source/output/scratch overlap.
- Settings patch tests cover OCR errors when OCR keys are changed, but not the case where an invalid existing OCR configuration is present and an unrelated setting is previewed.
- Final-library companion sidecar tests do not include adjacent media files with the primary stem.
- Default drift is not covered by a cross-source parity test comparing `Get-MediaPipelineConfigDefaultValues`, generated JSON schema defaults, template/identity defaults, and library profile defaults.

## Boundary Risks

- W02-001 touches the source/scratch/output separation boundary and Settings persistence boundary.
- W02-002 touches publish/final-library promotion and cleanup-after-verified behavior. It does not mutate original source roots, but it can delete publish-root media files incorrectly.
- W02-003 affects operator trust in backend-owned Settings preview/save validation.
- W02-004 affects bad-default detection and config identity safety for first-run/setup/default paths.

## Files Reviewed With No Findings

No findings were recorded in the remaining assigned files after module/function-level review:

- `ops/pipeline/engine/config/choice_registry.ps1`
- `ops/pipeline/engine/config/config_keys.ps1`
- `ops/pipeline/engine/config/config_schema.ps1`
- `ops/pipeline/engine/config/getters.ps1`
- `ops/pipeline/engine/config/library_overrides.ps1`
- `ops/pipeline/engine/config/runtime_config.ps1`
- `ops/pipeline/engine/config/runtime_merge.ps1`
- `ops/pipeline/engine/config/runtime_paths.ps1`
- `ops/pipeline/engine/config/runtime_validation.ps1`
- `ops/pipeline/engine/config/schema_keys.ps1`
- `ops/pipeline/engine/library/library_index.ps1`
- `src/mediapipeline/core/config/__init__.py`
- `src/mediapipeline/core/config/constants.py`
- `src/mediapipeline/core/config/contracts.py`
- `src/mediapipeline/core/config/encoding_capabilities.py`
- `src/mediapipeline/core/config/file_io.py`
- `src/mediapipeline/core/config/library_profile_defaults.py`
- `src/mediapipeline/core/config/library_profile_normalization.py`
- `src/mediapipeline/core/config/library_profile_promotion.py`
- `src/mediapipeline/core/config/library_profile_state.py`
- `src/mediapipeline/core/config/library_profile_validation.py`
- `src/mediapipeline/core/config/library_profile_wizard.py`
- `src/mediapipeline/core/config/library_profiles.py`
- `src/mediapipeline/core/config/load.py`
- `src/mediapipeline/core/config/metadata.py`
- `src/mediapipeline/core/config/metadata_choices.py`
- `src/mediapipeline/core/config/metadata_layout.py`
- `src/mediapipeline/core/config/metadata_network.py`
- `src/mediapipeline/core/config/metadata_parts/__init__.py`
- `src/mediapipeline/core/config/metadata_parts/advanced_fields.py`
- `src/mediapipeline/core/config/metadata_parts/basic_fields.py`
- `src/mediapipeline/core/config/metadata_parts/basic_media_policy.py`
- `src/mediapipeline/core/config/metadata_parts/basic_paths.py`
- `src/mediapipeline/core/config/metadata_parts/basic_processing.py`
- `src/mediapipeline/core/config/metadata_parts/field_definitions.py`
- `src/mediapipeline/core/config/metadata_parts/field_display.py`
- `src/mediapipeline/core/config/metadata_parts/field_registry.py`
- `src/mediapipeline/core/config/metadata_parts/field_scope.py`
- `src/mediapipeline/core/config/metadata_parts/network_fields.py`
- `src/mediapipeline/core/config/metadata_parts/policy.py`
- `src/mediapipeline/core/config/metadata_parts/queue_fields.py`
- `src/mediapipeline/core/config/metadata_parts/subtitle_fields.py`
- `src/mediapipeline/core/config/metadata_parts/video_fields.py`
- `src/mediapipeline/core/config/metadata_support.py`
- `src/mediapipeline/core/config/numeric_policy.py`
- `src/mediapipeline/core/config/option_policy.py`
- `src/mediapipeline/core/config/path_warnings.py` beyond W02-001
- `src/mediapipeline/core/config/preset_compatibility.py`
- `src/mediapipeline/core/config/preset_display_adapter.py`
- `src/mediapipeline/core/config/preset_encoding_sections.py`
- `src/mediapipeline/core/config/preset_migration.py`
- `src/mediapipeline/core/config/preset_migration_models.py`
- `src/mediapipeline/core/config/preset_policy.py`
- `src/mediapipeline/core/config/preview.py`
- `src/mediapipeline/core/config/profiles.py`
- `src/mediapipeline/core/config/recovery.py`
- `src/mediapipeline/core/config/rollout.py`
- `src/mediapipeline/core/config/save_runner.py` beyond W02-001
- `src/mediapipeline/core/config/service.py`
- `src/mediapipeline/core/config/settings_facade.py`
- `src/mediapipeline/core/config/settings_helpers_facade.py`
- `src/mediapipeline/core/config/settings_patch_policy.py`
- `src/mediapipeline/core/config/settings_policy.py`
- `src/mediapipeline/core/config/settings_risk_facade.py`
- `src/mediapipeline/core/config/settings_wizard.py`
- `src/mediapipeline/core/config/settings_wizard_facade.py`
- `src/mediapipeline/core/config/value_checks.py`
- `src/mediapipeline/core/final_library/__init__.py`
- `src/mediapipeline/core/final_library/facade.py`
- `src/mediapipeline/core/final_library/promotion.py` beyond W02-002 call path
- `src/mediapipeline/core/final_library/promotion_parts/__init__.py`
- `src/mediapipeline/core/final_library/promotion_parts/cleanup.py`
- `src/mediapipeline/core/final_library/promotion_parts/planning.py`
- `src/mediapipeline/core/final_library/promotion_parts/results.py`
- `src/mediapipeline/core/final_library/service.py`

## Files Marked Out Of Scope

- `src/mediapipeline/core/config/library_profile_compatibility.py` exists on disk but is not listed in the W02 assignment list; it was not included in the coverage ledger.
- `src/mediapipeline/core/orchestration/settings_patch_facade.py` was read only as supporting call-chain evidence for W02-003.
- `ops/pipeline/config/setup/ConfigFile.ps1`, `ops/pipeline/config/MediaPipeline_config_template.psd1`, and `ops/pipeline/config/profiles/Default.psd1` were considered contextual/default-source evidence only; ownership belongs to other assignment slices.
- The existing untracked uppercase draft `docs/reviews/function-module-audit-2026-06-11/workers/W02-core-config-settings-library.md` was read as prior context but not modified and is not this worker output path.

## Incomplete Coverage

None for the assigned W02 file list. Unassigned discovered file `src/mediapipeline/core/config/library_profile_compatibility.py` remains skipped as out of scope.
