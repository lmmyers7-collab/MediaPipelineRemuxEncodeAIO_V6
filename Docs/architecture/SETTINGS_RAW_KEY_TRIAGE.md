# Settings Raw-Key Triage

Date: 2026-05-14

Identifies config keys that still rely on raw JSON editing in WebView Settings, classifies them by operator impact, and separates intentionally hidden dangerous keys from missing structured builders. Source: `docs\inventories\SETTINGS_BUILDER_COVERAGE_MATRIX.md`.

This document does not change settings behavior. Changes to builder coverage require deliberate implementation work.

---

## Summary

| Category | Count |
|---|---|
| Keys in structured WebView builder arrays | 118 |
| Dedicated Library Profiles editor | 1 |
| Known advanced/direct-config metadata without routine builder | 9 |
| Intentionally hidden (excluded from WebView) | 2 |
| **Backend metadata keys** | **130** |

**Update (CLN2-11, 2026-05-15):** `ConsoleLogLevel` and `FileLogLevel` are now covered by the Runtime builder (`settingsMetadata.js`). Removed from raw-only list.

**Update (2026-05-15):** `WorkerSourcePathMap` and `WorkerConfigOverrides` were initially tracked for raw-key triage, then covered by the Network builder as JSON text fields during the WebView settings split work.

**Update (2026-05-19):** `BdpgsOcrToolPath` and `BdpgsOcrTessdataPath` are now covered by structured Subtitle builder text fields. They still rely on backend Preview/Save and backend-authored saved path evidence; no WebView path picker or frontend path resolution was added.

**Update (2026-05-19):** `SubSDHTitleKeywords` and `SubSupplementalKeywords` are now covered by structured Subtitle builder list fields. The WebView only stages list text; backend Preview/Save and backend subtitle classification remain authoritative.

**Update (2026-05-31):** The settings/library rewrite makes backend field metadata canonical for visible labels, help text, allowed values, defaults, advanced/display taxonomy, and library override eligibility. This raw-key triage remains an operator visibility note, not a metadata source of truth. The WebView remains staging/display only, Preview/Save remains backend-owned, and persisted current persisted keys/groups were not renamed.

**Update (2026-06-02, MDS-049):** `MixPriorityPhase`, `QueueOrderingStrategy`, and `ShowOverrides` now have backend field metadata so Settings Preview/Save and the Raw-Key Action Plan treat them as known advanced/direct-config keys instead of schema drift.

**Update (2026-06-04, MP-CHANGE-2026-0604-047):** Raw JSON may still stage unknown keys for backend Preview/Save, but keys that case-insensitively match a known persisted key must use the exact canonical spelling. Preview/Save now reject non-canonical spellings such as `routingprofile` with a canonical-key message instead of preserving an inert duplicate. Missing `ConvertBdpgsToSrt` is displayed as disabled, matching the config contract.

---

## Known Advanced / Direct-Config Keys

These non-secret keys are known backend metadata/config-contract keys but do not have routine structured WebView builder controls. They are not schema drift. Use raw JSON/direct config plus backend Preview Patch before Save.

| Key | Category | Operator action |
|---|---|---|
| `ConfigSchemaVersion` | Runtime / migration | Do not edit unless deliberately migrating schema |
| `MaxParallelEncodes` | Runtime / parallelism | Validate local encode capacity before changing |
| `ParallelEncodeMode` | Runtime / parallelism | Keep aligned with `MaxParallelEncodes` and local worker-slot validation |
| `MixPriorityPhase` | Queue planning | Preview Queue and inspect selected phase ordering |
| `QueueOrderingStrategy` | Queue planning | Preview Queue and inspect sort strategy effects |
| `OutputValidationProbeTimeoutSeconds` | Output validation | Validate completed-output probe behavior before changing |
| `OutputValidationMinSizeBytes` | Output validation | Validate small-output acceptance behavior before changing |
| `OutputValidationDurationToleranceSeconds` | Output validation | Validate duration tolerance against representative media before changing |
| `ShowOverrides` | Per-show media policy | Treat as media-policy work; verify Queue/Launch/Completed evidence for affected shows |

**Note (CLN2-11, 2026-05-15):** `ConsoleLogLevel` and `FileLogLevel` were added to the Runtime builder in `settingsMetadata.js` after the original CLN-015 audit. They are no longer raw-only.

---

## High-Impact OCR Path Keys

These two keys are most likely to cause silent failures if misconfigured, and are now handled by the Subtitle builder plus backend path evidence:

| Key | Risk if misconfigured | Operator signal |
|---|---|---|
| `BdpgsOcrToolPath` | BDPGS OCR silently fails or uses the wrong tool | OCR output is absent or corrupt; no explicit error if path resolves to a different binary |
| `BdpgsOcrTessdataPath` | OCR produces garbage or silently skips | Subtitles present but unreadable |

**Implemented improvement**: WebView Settings now stages `BdpgsOcrToolPath` and `BdpgsOcrTessdataPath` through structured Subtitle builder text fields and shows backend-authored read-only path evidence alongside the BDPGS builder controls. It reports saved-config path resolution, existence, expected file/folder type, `.dll`/`dotnet` posture, and blocked/review/ready status. It does not add a path-picker or frontend-owned path resolution.

---

## Intentionally Hidden Keys (Excluded From WebView Builder and Raw JSON Display)

These keys are present in `CONFIG_FIELD_DEFINITIONS` and visible in backend risk policy but are not shown in the structured builder or offered for raw JSON staging via the WebView.

| Key | Why Hidden | Operator Action |
|---|---|---|
| `CoordinatorAuthToken` | Network auth secret — must not appear in browser storage, dev tools, or JS heap snapshots | Edit the config `.psd1` directly; use a secure credential management practice |
| `WorkerAuthToken` | Network auth secret — same as above | Edit the config `.psd1` directly |

Auth tokens must not be added to the WebView builder without a design that prevents browser exposure.

---

## Keys Appearing in Multiple Builders

Some keys appear in more than one builder group (by design):
- `DeferredPublish`, `CleanupRemoteStaging`, `RobocopyFlags`, `RobocopyTimeoutSeconds`, `OutsourceMinFreeSpaceGB`, `OutputSizeMultiplier`, `EnableIntegrityCheck`, `SkipStabilityCheck` — appear in both **File Safety / Publish** and **Pending Publish / Recovery** builders.

These duplicate appearances are correct — both pages have different operator workflows for the same config key.

---

## High-Risk Builder-Covered Keys (For Awareness)

Although covered by a structured builder, these keys warrant extra caution:

| Key | Risk | Builder Group |
|---|---|---|
| `ExtraVideoFlags` | Raw FFmpeg passthrough — arbitrary flags | Video Detail |
| `AllowNoAudio` | Unsafe if no-audio output is not the intended behavior | Audio |
| `ReprocessAll` | Reprocesses all sources on next run | Queue |

These are not raw-only, but their builders include risk warnings and/or local save-readiness checklist blocks.

---

## See Also

- `docs\inventories\SETTINGS_BUILDER_COVERAGE_MATRIX.md` — full key-to-builder mapping
- `docs\inventories\SETTINGS_KEY_OWNERSHIP_MAP.md` — risk tiers, Launch handoff visibility, test coverage per key

---

## Ranked Builder Priority for Remaining Raw-Only Keys (CLN2-11, updated 2026-05-19)

The 2 true gap keys from the original audit are now closed. The intentionally hidden auth tokens remain excluded by design.

| Status | Key | Rationale |
|---|---|---|
| Closed | `SubSDHTitleKeywords` | Now staged through the Subtitle builder as a list field; backend subtitle classification remains authoritative. |
| Closed | `SubSupplementalKeywords` | Now staged through the Subtitle builder as a list field; backend subtitle classification remains authoritative. |

**Implementation note for BdpgsOcr keys:** The read-only evidence is provided by `/api/settings/workspace` as `tool_path_evidence`. The builder fields only stage text into the existing Settings Preview/Save path. Do not add a frontend path-picker.

**What is not worth building:** `CoordinatorAuthToken` and `WorkerAuthToken` must not receive WebView builder support without a design that prevents browser exposure (dev tools, JS heap snapshots, localStorage). This constraint is not lifted by the above ranking.

---

## WebView Raw-Key Action Plan (2026-05-15)

The Settings page now includes a read-only **Raw-Key Action Plan**. It does not add builders or mutation, but it turns the raw-key triage into operator next steps:

| Area | WebView action-plan behavior |
|---|---|
| Schema drift | Unknown keys are blocked/review and require backend Preview Patch before any save. |
| BDPGS OCR paths | `BdpgsOcrToolPath` and `BdpgsOcrTessdataPath` are Subtitle builder fields, and their saved backend path evidence is shown directly in the action plan. No path picker was added. |
| Subtitle keyword lists | `SubSDHTitleKeywords` and `SubSupplementalKeywords` are covered by the Subtitle builder as staged list fields; backend subtitle classification remains authoritative. |
| Network auth secrets | `CoordinatorAuthToken` and `WorkerAuthToken` remain intentionally excluded from builders; backend redaction and placeholder rejection remain mandatory. |
| Remaining advanced raw | Valid but non-routine raw keys are grouped behind a backend-preview-before-save action. |
| Mutation boundary | The action plan cannot stage JSON, save config, edit secrets, run OCR/FFmpeg, launch, publish/drain, rename, rewrite manifests/sidecars, or touch media. |

This closes the operator-visibility gap for the remaining raw-key categories without changing configuration persistence or WebView mutation authority.

The same action-plan posture is also surfaced in Home's External Dependency Digest and Diagnostics First Response after the Settings workspace is loaded. This gives operators a path back to Settings when schema drift, high-review raw keys, OCR path evidence, or secret-boundary concerns matter during run-failure triage. Home and Diagnostics remain read-only and cannot save settings, edit secrets, add path pickers, run OCR/FFmpeg, launch, publish/drain, rename, rewrite manifests/sidecars, or touch media.

The Settings and Library Profiles pages now consume backend metadata for labels, help, value choices, defaults, advanced status, and library override eligibility where available. HandBrake-style section names are display metadata only. Patch preview and save still show persisted current persisted keys and persisted Library Profiles groups, and backend validation remains the save gate.

---

## Task Output

```
Task ID: CLN-015
Files inspected: docs\inventories\SETTINGS_BUILDER_COVERAGE_MATRIX.md, docs\inventories\SETTINGS_KEY_OWNERSHIP_MAP.md
Files changed: docs\architecture\SETTINGS_RAW_KEY_TRIAGE.md (created)
Validation: Cross-referenced raw-only key list from SETTINGS_BUILDER_COVERAGE_MATRIX.md.
Findings: 2 intentionally hidden auth token keys remain. BdpgsOcrToolPath and BdpgsOcrTessdataPath are covered by the Subtitle builder while backend path evidence remains authoritative. SubSDHTitleKeywords and SubSupplementalKeywords are covered by the Subtitle builder while backend subtitle classification remains authoritative.
Open questions: None.
Risk: Low — documentation only.
```

