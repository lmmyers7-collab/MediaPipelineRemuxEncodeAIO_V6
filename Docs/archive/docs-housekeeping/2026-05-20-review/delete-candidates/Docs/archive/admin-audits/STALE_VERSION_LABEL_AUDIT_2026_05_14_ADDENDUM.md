# Stale Version Label Audit — 2026-05-14 Addendum

Purpose: recheck visible version labels and documentation references after the V5 Tauri/WebView2 transition work that occurred between the original audit and this addendum. This is an administrative audit; it does not change any code.

Original audit: `Docs/STALE_VERSION_LABEL_AUDIT.md`

Date: 2026-05-14

2026-05-18 resolution: the original four recommended updates are complete. `Versioning.ps1`, `Audit-MediaLibrary_chatgpt.ps1`, `test_contracts.py`, and `Docs/archive/historical-reviews/V3_RELIABILITY_NOTES.md` now align with the V5 product label while preserving V4 fallback references as intentional history.

---

## Summary of Changes Since Original Audit

The original audit (preserved in `Docs/STALE_VERSION_LABEL_AUDIT.md`) identified four stale labels and classified the rest as intentional historical references or false positives. The V5 transition work has added the following areas to review:

- New Tauri/WebView2 preview shell with its own version references
- New admin handoff backlog documents
- New WebView smoke wrappers and test files
- Expanded parity matrix and transition plan

---

## No New Stale Product Version Labels Found

After reviewing new files added during the Tauri/WebView2 transition work (as of 2026-05-14):

- `DesktopApp/tauri_shell/src-tauri/tauri.conf.json`: `"version": "5.0.0"` — Correct for V5.
- `DesktopApp/tauri_shell/src-tauri/Cargo.toml`: `version = "5.0.0"` — Correct for V5.
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/index.html`: `V5` sidebar label — Correct.
- New `Docs/CLAUDE_HANDOFF_ADMIN_20_TASK_BACKLOG.md`: References V4 as known-good backup — Intentional. References V5 as active workspace — Correct.
- New `Docs/CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md`: References V4 as backup — Intentional.
- New `Docs/CLAUDE_HANDOFF_20_TASK_BACKLOG.md`: References V4 as backup — Intentional.
- New `Docs/TAURI_WEBVIEW_PARITY_MATRIX.md` header: Date updated to 2026-05-14 — Correct.
- New `Docs/V5_TAURI_TRANSITION_CURRENT_PLAN.md`: References V4 as backup, V5 as active — Correct.

The four stale labels identified in the original audit were resolved on 2026-05-18:

1. `Pipeline/Modules/Versioning.ps1` returns `'v5.000'`.
2. `Pipeline/Audit-MediaLibrary_chatgpt.ps1` uses `'v5.000'` before importing the central version helper and then reads the central value.
3. `DesktopApp/tests/test_contracts.py` fixtures use `"v5.000"`.
4. `Docs/archive/historical-reviews/V3_RELIABILITY_NOTES.md` header references the V5 reliability baseline inherited from V4 hardening.

No stale product-version label remains open from this audit.

---

## New Classification: V5 Transition Docs

New documents added during the V5 Tauri work all correctly use V5 to describe the active workspace and V4 to describe the known-good fallback. These are all intentional references.

| New file | Reference | Classification |
|---|---|---|
| `Docs/V5_TAURI_TRANSITION_CURRENT_PLAN.md` | "V5 Tauri/WebView2 Transition Current Plan" | Correct — active workspace |
| `Docs/TAURI_WEBVIEW_PARITY_MATRIX.md` | "V5 CustomTkinter fallback" | Correct — Tk is the V5 fallback |
| `Docs/V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md` | "V5" workspace | Correct |
| `Docs/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md` | "V5 state as audited" | Correct |
| `Docs/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` | "V5 WebView/Tauri preview" | Correct |
| `Docs/V5_MIGRATION_RISK_REGISTER.md` | "V5 transition" | Correct |
| `Docs/V5_TRANSITION_STATUS_BOARD.md` | "V5" | Correct |
| `Docs/CLAUDE_HANDOFF_ADMIN_20_TASK_BACKLOG.md` | V4 as backup, V5 as workspace | Intentional |

---

## WebView UI Labels — No Changes

The WebView UI labels visible to operators remain:
- Sidebar: `V5` — Correct.
- Window title (Tauri shell): Reflects `tauri.conf.json` version `5.0.0` — Correct.
- `GET /api/snapshot` → `pipeline_version` field: Returns value from `Versioning.ps1` — now `v5.000`.

The previous `GET /api/snapshot` pipeline-version mismatch is resolved as of 2026-05-18.

---

## No Additional Stale Labels Found

No new stale or confusing product version labels were found in files added after the original audit. The original four recommended updates are resolved as of 2026-05-18.

---

## CLN Sprint Documentation Rescan (2026-05-14)

The CLN-020 rescan checked all documentation files created during the 2026-05-14 cleanup/review/sorting sprint (CLN-001 through CLN-030 task outputs). These are all Markdown documentation files. None contain product version strings beyond correct references to V5 as the active workspace and V4 as the known-good fallback.

| New file group | Version references | Classification |
|---|---|---|
| All `CLN-*.md` audit and review docs | None | N/A — no version strings |
| `ROOT_SCRIPT_INVENTORY.md` | V4/V5 context only | Correct — V4 is backup reference |
| `RELEASE_SELF_TEST_LAYOUT_AUDIT.md` | None | N/A |
| `CLAUDE_HANDOFF_STATUS_RECONCILIATION.md` | None | N/A |

No new stale version labels found in CLN sprint documents.

---

## Resolution Verification Order

1. `Pipeline/Modules/Versioning.ps1` returns `'v5.000'`.
2. `Pipeline/Audit-MediaLibrary_chatgpt.ps1` is aligned to the central product version.
3. `DesktopApp/tests/test_contracts.py` fixtures assert `"v5.000"`.
4. `Docs/archive/historical-reviews/V3_RELIABILITY_NOTES.md` header reflects V5 inheritance.

Do not update `MinPipelineVersion` config values from this audit.

---

## See Also

- Original audit: `Docs/STALE_VERSION_LABEL_AUDIT.md`
- Pipeline version source: `Pipeline/Modules/Versioning.ps1`
- Snapshot API: `GET /api/snapshot` → `desktop_app_snapshot.v1`
