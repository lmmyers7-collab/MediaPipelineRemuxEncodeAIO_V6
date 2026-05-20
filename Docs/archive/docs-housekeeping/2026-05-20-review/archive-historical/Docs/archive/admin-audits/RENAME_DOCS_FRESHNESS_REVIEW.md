# Rename Documentation Freshness Review

Date: 2026-05-14

Checks whether rename documentation reflects the current standalone Rename tool, movie/TV split, final-name overrides, checked-row scope, and backend-owned apply. Source: `Docs\RENAME_SAFETY_TEST_INVENTORY.md`, `Docs\RENAME_TOOL_EDGE_CASE_CATALOG.md`.

---

## Summary

No stale "queue-integrated only" wording found. Rename is correctly documented as a standalone backend-owned workflow with TV/Movie split, selected-row scope, and backend-owned apply. No documentation changes required.

---

## Acceptance Criteria Check

| Criterion | Status | Evidence |
|---|---|---|
| Docs do not imply Rename is queue-integrated only | Pass | Rename test files use standalone service layer; no queue integration in rename tests |
| Docs mention backend-owned apply and selected/checked scope | Pass | `RENAME_SAFETY_TEST_INVENTORY.md`: `rename.apply` is browser-verified as NOT called when blocked; selected-source filtering is covered with path casefolding |
| Docs do not promise unsupported PowerRename-level freeform behavior | Pass | No PowerRename reference found in rename docs |

---

## Current Rename System Scope (From RENAME_SAFETY_TEST_INVENTORY.md)

| Feature | Coverage in tests | Assessment |
|---|---|---|
| TV episode rename (season/episode extraction) | `test_service_rename_tv.py` — season from folder, file-embedded override, OVA/specials | Correct; well-tested |
| Movie rename (release tag stripping) | `test_service_rename_movie.py` — strip release groups, quality markers | Correct |
| Checked/selected row scope | `test_facade_rename_policy.py` — selected-source filtering with path casefolding | Correct; Windows/POSIX case-insensitive match covered |
| Backend-owned apply | `test_webview_rename_readiness_smoke.py`, `test_webview_browser_rename_smoke.py` — verifies `rename.apply` NOT called when blocked | Correct |
| Duplicate-destination blocking | Both UI-layer tests verify blocked state without calling apply | Correct |
| Case-only rename (Windows two-step) | `test_service_rename_apply.py` | Correct |
| Sidecar metadata preservation after rename | `test_service_rename_apply.py` — error marker preservation, history cap at 25 | Correct |

---

## Known Coverage Gaps (From RENAME_SAFETY_TEST_INVENTORY.md)

These are documented test gaps, not documentation errors:

| Gap | Documented in |
|---|---|
| No explicit "backend ignores frontend plan" integration test | `RENAME_SAFETY_TEST_INVENTORY.md` Safety Properties table |
| `confirm_apply` rejection test missing at service layer | `RENAME_SAFETY_TEST_INVENTORY.md` Safety Properties table |
| Duplicate-destination detection at service layer (vs UI layer) | `RENAME_SAFETY_TEST_INVENTORY.md` Safety Properties table |
| Undo manifest verification | `RENAME_SAFETY_TEST_INVENTORY.md` Safety Properties table |

None of these gaps cause incorrect documentation. They are engineering coverage gaps, not doc accuracy problems.

---

## Files Inspected

- `Docs\RENAME_SAFETY_TEST_INVENTORY.md`: 15-file inventory; TV/Movie/selected-scope/apply tests
- `Docs\RENAME_TOOL_EDGE_CASE_CATALOG.md`: TV/Movie edge cases, duplicate-target, case-only, already-correct, missing metadata

---

## Freshness Review — 2026-05-15 (CLN2-12)

Re-checked all five CLN2-12 scope items against `renameView.js` (reference only), `RENAME_TOOL_EDGE_CASE_CATALOG.md`, and `TAURI_WEBVIEW_PARITY_MATRIX.md`.

| Item | Doc Coverage | Status |
|---|---|---|
| Templates (`template_preset`, `template_catalog`) | Not in `RENAME_TOOL_EDGE_CASE_CATALOG.md` | **Coverage gap** — feature exists in `renameView.js` (`template_preset` sent to `/api/rename/preview`; backend serves `template_catalog` for display labels). No stale text; missing entry. Low urgency — templates are a pre-canned preset mechanism, not a standalone behavior that could silently regress. |
| Selected scope / checked-row scope | Covered in CLN-016 freshness review (`test_facade_rename_policy.py`) | Pass — no drift |
| `force_pipeline_name` and per-row force overrides | Covered in `RENAME_TOOL_EDGE_CASE_CATALOG.md` — "Sidecar Gap (Force Override)" section | Pass — no drift |
| Sidecar behavior | Covered in `RENAME_TOOL_EDGE_CASE_CATALOG.md` — "Sidecar Behavior" section | Pass — no drift |
| Large-batch render cap (250 rows) | Covered in `RENAME_TOOL_EDGE_CASE_CATALOG.md` — "Render Cap Behavior" section; `RENAME_PREVIEW_RENDER_LIMIT = 250` confirmed in `renameView.js` | Pass — no drift |
| Pipeline handoff | Covered in `TAURI_WEBVIEW_PARITY_MATRIX.md` — "Rename Pipeline Handoff addendum": read-only cross-check of filenames against settings/sidecar/force-name posture; verified by rename smokes | Pass — no drift |

One coverage gap found: templates are not documented in `RENAME_TOOL_EDGE_CASE_CATALOG.md`. This is not a stale or incorrect entry — the gap is simply absent. No existing documentation claims templates do not exist. Recommended follow-up: add a "Template Preset Behavior" section to `RENAME_TOOL_EDGE_CASE_CATALOG.md` describing `template_preset` input and `template_catalog` backend-served response structure.

---

## Freshness Review — 2026-05-15 (CLN3-024)

Re-checked against current `RENAME_TOOL_EDGE_CASE_CATALOG.md` and `TLDR.md` for season logic, scrub filters, sidecar tagging, and apply-readiness references.

| Item | Status |
|---|---|
| Season/episode extraction (TV rename) | Pass — `test_service_rename_tv.py` covers season from folder, file-embedded override, OVA/specials |
| Movie rename (scrub/release tag stripping) | Pass — `test_service_rename_movie.py` covers release group/quality marker scrubbing |
| Sidecar metadata preservation | Pass — `RENAME_TOOL_EDGE_CASE_CATALOG.md` "Sidecar Behavior" section covers error marker preservation and history cap |
| Apply Readiness blocking | Pass — both rename smokes verify `rename.apply` is NOT called when blocked |
| Template preset coverage gap | Still open — `template_preset` / `template_catalog` not in `RENAME_TOOL_EDGE_CASE_CATALOG.md`; documented here for follow-up |

No new stale wording found. No documentation changes required beyond this note.

```
Task ID: CLN3-024
Files inspected: Docs\RENAME_DOCS_FRESHNESS_REVIEW.md, Docs\RENAME_TOOL_EDGE_CASE_CATALOG.md, Docs\TLDR.md (reference)
Files changed: Docs\RENAME_DOCS_FRESHNESS_REVIEW.md (CLN3-024 freshness note added)
Validation: Select-String -Path Docs\RENAME_DOCS_FRESHNESS_REVIEW.md,Docs\RENAME_TOOL_EDGE_CASE_CATALOG.md,Docs\TLDR.md -Pattern "season|movie|scrub|sidecar|Apply Readiness"
Findings: All items current. Template preset coverage gap remains open (unchanged from CLN2-12).
Open questions: None.
Risk: Low — documentation only.
```

No wording corrections required.

---

## Task Output

```
Task ID: CLN-016
Files inspected: Docs\RENAME_SAFETY_TEST_INVENTORY.md, Docs\RENAME_TOOL_EDGE_CASE_CATALOG.md
Files changed: Docs\RENAME_DOCS_FRESHNESS_REVIEW.md (created)
Validation: Checked acceptance criteria against test inventory and edge case catalog.
Findings: All acceptance criteria pass. Four documented test gaps exist but do not affect documentation accuracy.
Open questions: None.
Risk: Low — documentation only.
```
