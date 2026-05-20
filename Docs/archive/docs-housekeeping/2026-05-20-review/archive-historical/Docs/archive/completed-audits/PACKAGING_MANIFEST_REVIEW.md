# Packaging Manifest Review

Date: 2026-05-14

Gap report comparing what the release builder (`Build-MediaPipelineRemuxEncodeAIO-Release.ps1`) includes against V5 modules and documentation added after the initial release process was established. Identifies any new V5 docs or scripts that may require explicit inclusion or exclusion handling.

This document does not modify the release builder. All packaging changes must be made deliberately to the builder script.

---

## Release Builder Overview

The release builder (`Build-MediaPipelineRemuxEncodeAIO-Release.ps1`) copies the workspace tree with selective exclusions. Key flags:

| Flag | Effect |
|---|---|
| `-IncludeTests` | Include Pipeline/Tests/ subdirectory |
| `-IncludeDevDocs` | Include development checklist docs |
| `-IncludeOptionalTools` | Include optional diagnostic tools (ffplay, MKVToolNix extras) |
| `-IncludeToolDocs` | Include tool vendor documentation |
| `-KeepPersonalConfig` | Include operator's personal PSD1 config (default: use template) |
| `-DryRun` | Report what would be packaged without writing any files |

---

## Always-Included in Release Package

| Path / Pattern | Notes |
|---|---|
| `DesktopApp/` (minus exclusions) | Main app — Python, Tauri shell, WebView assets, bundled runtime |
| `Pipeline/` (minus exclusions) | PowerShell pipeline scripts |
| `Docs/` (minus exclusions) | Operator and engineering documentation |
| Root-level `.bat` files | Launcher scripts |
| Root-level `Test-WebView*.ps1` files | **All WebView smoke wrappers are always included** |
| `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` | Release self-test — always included |
| `release_manifest.json` | Generated per-release |
| Bundled `Runtime/` (Python, PowerShell 7.6.0) | Self-contained runtime |
| Bundled FFmpeg, mkvmerge, PgsToSrt | Tool binaries |

---

## Always-Excluded From Release Package

| Path / Pattern | Reason |
|---|---|
| `.git/`, `.claude/` | Source control and AI session metadata |
| `__pycache__/`, `*.pyc`, `*.pyo`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` | Python build artifacts |
| `DesktopApp/tauri_shell/node_modules/` | Tauri build dependency (not needed at runtime) |
| `DesktopApp/tauri_shell/src-tauri/gen/` | Generated Tauri schema output |
| `DesktopApp/tauri_shell/src-tauri/target/` | Rust build output |
| `~$*`, `*.docx`, `*.xlsx`, `*.pptx` | Office temp and working documents |
| `.gitignore` | Source control metadata |
| `DesktopApp/RunLogs/*`, `*.log`, `*.state.json` | Runtime artifacts |
| `Pipeline/MediaPipeline_config_chatgpt.psd1` | Personal config (template used instead, unless `-KeepPersonalConfig`) |
| `Docs/RealMediaValidationRuns/*` | Operator validation run records (may contain personal paths) |

---

## Dev-Docs Excluded by Default (Included With `-IncludeDevDocs`)

| File | Classification |
|---|---|
| `Docs/archive/completed-checklists/CODE_CLEANUP_CHECKLIST.md` | Completed development checklist |
| `Docs/archive/completed-checklists/CONTROL_SURFACE_HARDENING_CHECKLIST.md` | Completed development checklist |
| `Docs/UI_CHECKLIST*.md` | Completed UI checklists |
| `Docs/UI_IMPROVEMENT_CHECKLIST.md` | Completed UI checklist |
| `Docs/archive/historical-reviews/V4_MIGRATION_NOTES.md` | V4 migration reference |

These are already classified as "Archive: Completed" in `Docs/archive/admin-audits/DOCS_DEAD_MARKDOWN_AUDIT.md`. The default exclusion is correct.

---

## V5 New Docs: Inclusion Status

The following documentation files were created in this documentation sprint (2026-05-14). Their current inclusion status in the release builder is assessed below.

### Always-Included (Docs/ included by default; no individual exclusion pattern)

All new engineering and operator docs under `Docs/` are included by the default Docs/ inclusion rule. This covers:

| New doc | Appropriate in release package? |
|---|---|
| `Docs/API_ROUTE_INVENTORY.md` | Yes — operator/engineering reference |
| `Docs/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` | Yes — smoke test safety reference |
| `Docs/COMMAND_OWNERSHIP_MATRIX.md` | Yes — engineering reference |
| `Docs/COMPLETED_PENDING_FAILURE_PLAYBOOK.md` | Yes — operator runbook |
| `Docs/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md` | Yes — operator/engineering reference |
| `Docs/archive/admin-audits/DOCS_DEAD_MARKDOWN_AUDIT.md` | **Review** — internal audit doc; see note below |
| `Docs/FRONTEND_MODULE_SIZE_COHESION_REPORT.md` | **Review** — internal engineering doc |
| `Docs/LOG_ARTIFACT_CATALOG.md` | Yes — operator reference |
| `Docs/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md` | Yes — operator reference |
| `Docs/RENAME_TOOL_EDGE_CASE_CATALOG.md` | Yes — operator reference |
| `Docs/SETTINGS_KEY_OWNERSHIP_MAP.md` | Yes — operator/engineering reference |
| `Docs/STATE_FILE_SCHEMA_REFERENCE.md` | Yes — engineering reference |
| `Docs/TERMINOLOGY_CONSISTENCY_GUIDE.md` | Yes — engineering/docs reference |
| `Docs/TEST_COVERAGE_MATRIX.md` | **Review** — internal engineering doc |
| `Docs/V5_REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md` | **Review** — internal gap analysis |
| `Docs/WEBVIEW_APIPOST_MUTATION_REVIEW.md` | Yes — engineering reference |
| `Docs/WEBVIEW_DOM_ID_INVENTORY.md` | **Review** — internal engineering doc |
| `Docs/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md` | Yes — operator runbook |
| `Docs/WEBVIEW_OPERATOR_ERROR_MESSAGE_REVIEW.md` | **Review** — internal engineering doc |

**Review note**: Docs marked "Review" are internal engineering inventory/audit documents. They are safe to include in release packages (no personal paths, no secrets, no personal configs), but operators are unlikely to need them. Consider whether they should join the `-IncludeDevDocs` group or remain always-included.

---

### Always-Excluded (Pattern Match)

`Docs/RealMediaValidationRuns/*` is excluded because operator worksheet runs may contain personal file paths. This exclusion pattern covers any worksheets generated by `New-RealMediaValidationWorksheet.ps1`.

**Gap**: The `Docs/RealMediaValidationRuns/` directory itself (and its README, if any) might need a separate inclusion rule. Currently only the directory contents are excluded; confirm whether a README in that folder should be included.

---

## New PS1 Wrappers: Inclusion Status

All root-level `Test-WebView*.ps1` wrappers are always included. New wrappers added in V5 that must be confirmed present:

| File | Status |
|---|---|
| `Test-WebViewScheduleSmoke.ps1` | Always included (root-level, matches pattern) |
| `Test-WebViewRealMediaEvidenceSmoke.ps1` | Always included |
| `Test-WebViewBrowserScheduleSmoke.ps1` | Always included |
| `Test-WebViewBrowserLifecycleSmoke.ps1` | Always included |
| All other `Test-WebViewBrowser*.ps1` | Always included |

`New-RealMediaValidationWorksheet.ps1` (root-level): should be confirmed always-included; this utility is operator-facing and not covered by the `Test-WebView*.ps1` naming pattern. If the builder uses an explicit include list of root PS1 files, this file needs to appear there.

---

## Bundled Tool Versions (As of Current Release)

Captured in `release_manifest.json` by the builder:

| Tool | Version |
|---|---|
| PowerShell | 7.6.0 (bundled at `Runtime/PowerShell-7.6.0-win-x64/`) |
| FFmpeg / FFprobe | Latest bundled (check `release_manifest.json`) |
| mkvmerge | Latest bundled |
| PgsToSrt | Latest bundled |

---

## Identified Gaps and Recommendations

| # | Gap | Recommendation | Priority |
|---|---|---|---|
| 1 | `New-RealMediaValidationWorksheet.ps1` may not be covered by `Test-WebView*.ps1` inclusion pattern | Confirm the root PS1 inclusion logic covers this file | Medium |
| 2 | `Docs/archive/admin-audits/DOCS_DEAD_MARKDOWN_AUDIT.md`, `Docs/TEST_COVERAGE_MATRIX.md`, `Docs/FRONTEND_MODULE_SIZE_COHESION_REPORT.md`, `Docs/WEBVIEW_DOM_ID_INVENTORY.md`, and similar internal engineering docs are included by default | Decide whether to move these to the `-IncludeDevDocs` exclusion list | Low |
| 3 | `Docs/RealMediaValidationRuns/` README inclusion edge case | Confirm exclusion pattern does not accidentally exclude a wanted README | Low |
| 4 | Tauri shell binary (`.exe`) must be pre-built before release — the builder does not compile it | Ensure CI/release notes require a Tauri build step before packaging | High |
| 5 | WebView2 runtime bootstrap: the builder does not bundle WebView2; operators must install it separately | Confirm `BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md` and release notes mention WebView2 requirement | Medium |

---

## See Also

- Docs index: `Docs/DOCS_INDEX.md`
- Dead markdown audit: `Docs/archive/admin-audits/DOCS_DEAD_MARKDOWN_AUDIT.md`
- Smoke prerequisites: `Docs/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md`
- Test coverage matrix: `Docs/TEST_COVERAGE_MATRIX.md`
