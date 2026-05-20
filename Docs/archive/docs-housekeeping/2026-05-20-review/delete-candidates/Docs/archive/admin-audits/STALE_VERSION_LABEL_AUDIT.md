# Stale Version Label Audit

Purpose: identify every file in the V5 workspace where V3 or V4 text appears and classify each occurrence as intentional historical context, a stale label that should be updated, or a false positive. This document does not make code changes.

2026-05-18 resolution: the four stale labels identified by this audit are resolved. `Pipeline/Modules/Versioning.ps1` returns `v5.000`; `Pipeline/Audit-MediaLibrary_chatgpt.ps1` uses the same product label; `DesktopApp/tests/test_contracts.py` fixtures use `v5.000`; and `Docs/archive/historical-reviews/V3_RELIABILITY_NOTES.md` now describes the V5 reliability baseline inherited from V4 hardening. Historical findings below are retained for audit trail only.

---

## Classification Key

| Class | Meaning |
|---|---|
| **Stale** | Should say V5 or reflect the current version; will cause operator confusion or test drift |
| **Intentional** | Deliberately preserved as historical context (migration notes, backup references, archive docs) |
| **False positive** | V3/V4 text that is not a product version label (ASS format version, schema name, etc.) |

---

## Stale Labels — Should Be Updated

These files contain V3 or V4 product version strings where V5 is the correct value.

### `Pipeline/Modules/Versioning.ps1` — line 10

```powershell
return 'v4.000'
```

The canonical product version string for the PowerShell pipeline layer. This should be `'v5.000'` to match the workspace, Tauri shell version (`5.0.0`), and WebView display (`V5`). Until updated, `GET /api/snapshot` (which reads this via the pipeline facade) may report `v4.000` as the pipeline version, which conflicts with the V5 label displayed in the sidebar.

**Impact**: Moderate — operator confusion if the snapshot shows `v4.000` while the UI says `V5`.

### `Pipeline/Audit-MediaLibrary_chatgpt.ps1` — line 18

```powershell
$script:ProductVersion = 'v4.000'
```

The audit script's own version declaration. Should match `Versioning.ps1` once that is updated. Stale for the same reason.

**Impact**: Low — applies to the audit launch path only, not the daily pipeline.

### `DesktopApp/tests/test_contracts.py` — line 74

```python
"product_version": "v4.000",
```

A test fixture or schema example that embeds the product version. If `Versioning.ps1` is updated to `v5.000`, this test will expect the old value and fail. The test should be updated in the same change as `Versioning.ps1`.

**Impact**: Test drift — will produce a false failure after Versioning.ps1 is bumped.

### `DesktopApp/docs/V3_RELIABILITY_NOTES.md` — header (line 1)

```
# V4 Reliability Notes
```

The file is named `V3_RELIABILITY_NOTES.md` (filename retained for historical compatibility) but the header says "V4 Reliability Notes". Neither matches V5. The content describes V4 reliability hardening work that V5 inherits. The header should clarify that V5 is the active version built on V4's baseline.

**Impact**: Low operator confusion. The file is engineering context, not operator-facing.

---

## Intentional Historical References — Do Not Change

These files contain V3 or V4 text that is deliberately preserved as migration or backup documentation.

| File | V3/V4 reference | Why intentional |
|---|---|---|
| `Docs/CODE_CLEANUP_CHECKLIST.md` | "V4 Code Cleanup Archive" | Archive of completed V4 cleanup work |
| `Docs/CONTROL_SURFACE_HARDENING_CHECKLIST.md` | "V4 Control Surface Hardening Archive" | Archive of completed V4 hardening work |
| `Docs/TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md` | "V4 is working well enough to preserve as a stable backup", "Keep V4 Intact" | The transition design requires V4 to remain as the known-good fallback |
| `Docs/V4_MIGRATION_NOTES.md` | Entire file describes how V4 was curated from V3 | Historical provenance document; excluded from clean releases |
| `Build-MediaPipelineRemuxEncodeAIO-Release.ps1` | References `'V4_MIGRATION_NOTES.md'` in exclusion list | Correctly excludes the V4 migration history from clean packages |
| `Docs/TLDR.md` | References V4 as the known-good backup | Operational guidance telling operators V4 is still available |
| `DesktopApp/docs/V3_RELIABILITY_NOTES.md` (filename) | `V3_` prefix | Filename is kept for cross-reference compatibility with older notes; the disclaimer in the file header explains the mismatch |
| `CLAUDE_HANDOFF_*` docs | References to V4 as known-good backup | Handoff context for AI-assisted development sessions |

---

## False Positives — Not Product Version Labels

These files contain "V3" or "V4" text that is not a product version label.

| File | Text | What it actually is |
|---|---|---|
| `Pipeline/Tests/Invoke-ToolIntegrationChecks.ps1` | `'ScriptType: v4.00+'`, `'[V4+ Styles]'` | ASS/SSA subtitle format version markers. V4+ is the ASS script format version, not the product version. Do not change. |
| Various subtitles config | `v4.00` | ASS format version in subtitle files |
| `Pipeline/Schemas/media_pipeline_config.schema.json` | No V3/V4 product version reference found | Schema describes config keys; no product version embedded |

---

## Version Label Consistency Summary

The current state of product version declarations:

| Location | Current value | Correct for V5? |
|---|---|---|
| `Pipeline/Modules/Versioning.ps1` | `'v4.000'` | **No** — stale |
| `Pipeline/Audit-MediaLibrary_chatgpt.ps1` | `'v4.000'` | **No** — stale |
| `DesktopApp/tests/test_contracts.py` (fixture) | `"v4.000"` | **No** — will fail after version bump |
| `DesktopApp/tauri_shell/src-tauri/tauri.conf.json` | `"version": "5.0.0"` | Yes |
| `DesktopApp/tauri_shell/src-tauri/Cargo.toml` | `version = "5.0.0"` | Yes |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/index.html` | `V5` | Yes |
| `Docs/DesktopApp/docs/V3_RELIABILITY_NOTES.md` header | "V4 Reliability Notes" | Partially — header should reference V5 inheritance |

---

## Recommended Update Order (When Ready)

1. `Pipeline/Modules/Versioning.ps1` — bump `'v4.000'` to `'v5.000'`
2. `Pipeline/Audit-MediaLibrary_chatgpt.ps1` — match the new version
3. `DesktopApp/tests/test_contracts.py` — update fixture to `"v5.000"` in the same change
4. `DesktopApp/docs/V3_RELIABILITY_NOTES.md` header — update to "V5 Reliability Baseline (inherited from V4 hardening)" or similar

These four changes are the only code changes needed. All other V3/V4 references are intentional or false positives and should not be changed.

Do not update `MinPipelineVersion` config values from this audit — `MinPipelineVersion` is a sidecar freshness gate set per operator and is not a display label.

---

## See Also

- Tauri shell Rust source: `DesktopApp/tauri_shell/src-tauri/lib.rs` (no V3/V4 labels)
- Product version in snapshot: `GET /api/snapshot` → `desktop_app_snapshot.v1` (reads from `Versioning.ps1`)
- V4 migration history: `Docs/V4_MIGRATION_NOTES.md` (intentionally preserved)
