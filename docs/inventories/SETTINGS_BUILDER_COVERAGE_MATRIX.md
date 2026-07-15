# Settings Builder Coverage Matrix

Current inventory of backend configuration metadata, structured WebView builder bindings, dedicated editors, and intentionally direct-only fields. Backend metadata and validation remain authoritative; frontend arrays define display/order bindings and stage patches for backend Preview/Save.

Last verified: 2026-07-13.

## Coverage Summary

| Measure | Count | Meaning |
|---|---:|---|
| Backend metadata keys | 204 | Keys in `CONFIG_FIELD_DEFINITIONS` / the config contract |
| Structured builder bindings | 155 | Entries across the ten builder arrays in `settingsMetadata.js` |
| Unique structured builder keys | 145 | Distinct backend keys represented by those bindings |
| Duplicate bindings | 10 | Deliberate File Safety / Pending Publish workflow overlap |
| Library Profile override-capable keys | 77 | Keys supported by the dedicated inheritance/override editor |
| Override-only keys | 0 | Every override-capable key also exists in backend metadata |
| No routine structured builder | 59 | 1 dedicated `LibraryProfiles` editor + 56 advanced/direct keys + 2 hidden secrets |

The arithmetic is intentional: `145` structured keys + `59` keys without a routine structured builder = `204` backend metadata keys. Binding count is higher than unique-key count because ten keys appear in two workflow-specific builders.

## Builder Groups

| Builder group | Binding count | Primary purpose |
|---|---:|---|
| Routing / Size | 18 | Route profile, size guard, movie/TV targets, height tolerances, and route bitrate ceilings |
| Video Detail | 17 | Encode ladder/backend/container, preset/quality, remux compatibility, CPU fallback, and extra flags |
| Quality Verification | 9 | Metric, sampling, thresholds, action, and timeout |
| File Safety / Publish | 22 | Source/output/scratch paths, free-space/stability/watch policy, integrity, and deferred-publish posture |
| Network | 12 | Coordinator/worker non-secret configuration; rendered on the separate Network page while using the same backend patch contract |
| Queue / Reprocess | 4 | Priority markers, processed-index refresh, version floor, and reprocess mode |
| Runtime / Diagnostics | 18 | Logging, artifact retention, FFmpeg/tool/copy/scan timeouts, retry, and system-tool fallback |
| Pending Publish / Recovery | 12 | Deferred publish, retry/copy/cleanup policy, free-space and size policy, integrity/stability, and review/block budgets |
| Subtitle | 34 | TX3G, BDPGS, VobSub, ASS/SSA language, OCR, preservation, conversion, and classification policy |
| Audio | 9 | Passthrough profile, codec/language policy, transcode bitrate, downmix, channels, and no-audio posture |
| **Total** | **155** | 145 unique keys plus 10 deliberate duplicate bindings |

### Deliberate Duplicate Bindings

These ten keys appear in both File Safety / Publish and Pending Publish / Recovery because each page supports a distinct operator workflow over the same backend-owned value:

`DeferredPublish`, `CleanupRemoteStaging`, `TransientFailureRetryLimit`, `CleanupStaleAgeHours`, `RobocopyTimeoutSeconds`, `RobocopyFlags`, `OutsourceMinFreeSpaceGB`, `OutputSizeMultiplier`, `EnableIntegrityCheck`, and `SkipStabilityCheck`.

They are not independent values. Either builder stages the same config key, and backend Preview/Save remains authoritative.

## Settings Page Placement

The Settings surface has ten operator panes. These are navigation/placement groupings, not ten additional sources of config truth.

| Pane | Role |
|---|---|
| `status` | Saved/staged posture, backend evidence, and command result visibility |
| `guided-setup` | Guided entry points and readiness explanations |
| `paths-safety` | Source/output/scratch and file-safety controls |
| `routing-size` | Routing, size guard, target, and quality controls |
| `media-output` | Video, audio, and subtitle output policy |
| `publish-recovery` | Deferred publish and recovery controls |
| `naming` | Naming/rename-related settings guidance |
| `queue-runtime` | Queue/reprocess and runtime/diagnostics controls |
| `presets` | Saved preset and Library Profile workflows |
| `advanced-evidence` | Raw-key action plan, risk/readiness evidence, and advanced handoff |

The 12 Network bindings render on the separate Network page. They still stage through the same backend Preview/Save contract and are included in the 155 binding count.

## Library Profile Coverage

`LibraryProfiles` uses a dedicated editor rather than a static builder-array row. Its 77 override-capable keys are drawn from backend metadata; there are no override-only keys.

The editor distinguishes:

- inherited values from the selected parent/global configuration;
- persisted explicit overrides;
- staged explicit overrides; and
- reset-to-inherited actions.

Reset must restore the row's actual inherited value, not the schema default. An explicit value equal to the inherited value is not newly persisted as an override unless it was already an explicit persisted override. The browser field-matrix and Library Profiles save smokes cover these semantics against generated temporary config.

## Advanced / Direct-Config Metadata

There are 56 non-secret metadata keys without routine structured builder controls. The examples below are representative, not exhaustive. The executable source of truth remains `CONFIG_FIELD_DEFINITIONS`, the config contract, and backend Preview Patch output.

| Representative key/family | Why it remains advanced/direct |
|---|---|
| `ConfigSchemaVersion` | Backend migration/schema marker, not a routine operator setting |
| `MaxParallelEncodes`, `ParallelEncodeMode` | Coupled capacity controls that require deliberate worker-slot validation |
| `MixPriorityPhase`, `QueueOrderingStrategy` | Advanced queue planning; validate against Queue preview |
| `FinalLibraryPromotion*` | High-impact destination/verification/cleanup/overwrite policy; backend promotion workflow owns mutation |
| `RenameMovieFilterOptions`, `RenameMovieFilterTerms`, `RenameMovieRemoveTerms` | Advanced naming filters; Rename preview/apply boundaries remain authoritative |
| `OutputValidation*` | Completed-output validation thresholds and timeouts |
| `PendingPublishBacklogBlockThreshold`, `PendingPublishDeferredBlockThreshold` | Backend backpressure policy; does not grant frontend drain authority |
| `StateDb*` | SQLite observability/maintenance policy; JSON/JSONL authority is unchanged |
| `ShowOverrides` | Advanced per-show media-policy mapping with broad routing/audio/subtitle impact |

Do not treat this representative table as a complete key registry. Unknown or direct-only keys must be reviewed through the backend Raw-Key Action Plan and Preview Patch rather than inferred from this document.

## Intentionally Hidden From WebView

| Key | Category | Reason hidden |
|---|---|---|
| `CoordinatorAuthToken` | Network authentication | Secret must not appear in WebView controls, browser storage, or JS heap snapshots |
| `WorkerAuthToken` | Network authentication | Secret must match coordinator without browser exposure |

These two keys are included in the 59 keys without a routine structured builder. Do not add them to the WebView without an approved secret-handling design.

## Important Coverage Notes

- `ExtraVideoFlags`, `AllowNoAudio`, and `ReprocessAll` have structured controls but retain high-risk save-readiness treatment.
- OCR tool/tessdata fields are builder-covered text inputs; backend saved-path resolution and readiness evidence are authoritative. There is no frontend-owned path resolution.
- Byte-backed budget metadata is presented as GiB in the builder while persistence remains bytes; control metadata records the unit conversion.
- Network is an external page, not an omitted builder group.
- The Settings field-matrix smoke exercises all structured bindings by field type and validates strict confirmation/reload evidence in a disposable root. It does not validate live config or real-media behavior.

## Validation Sources

- Backend metadata registry: `src/mediapipeline/core/config/metadata_parts/field_definitions.py` and sibling `metadata_parts/*_fields.py` modules
- Builder arrays: `apps/desktop/webview/static/assets/settingsMetadata.js`
- Builder control metadata: `apps/desktop/webview/static/assets/settings/builderControls.js`
- Library Profile editor: `apps/desktop/webview/static/assets/settingsLibraries/`
- Browser matrix: `tests/webview/test_webview_browser_settings_field_matrix_smoke.py`
- Static Settings tests: `tests/python/desktop/test_application_facade_web_static_settings.py`, `tests/webview/test_webview_handbrake_settings_ui.py`, and Settings library/patch tests under `tests/webview/`
