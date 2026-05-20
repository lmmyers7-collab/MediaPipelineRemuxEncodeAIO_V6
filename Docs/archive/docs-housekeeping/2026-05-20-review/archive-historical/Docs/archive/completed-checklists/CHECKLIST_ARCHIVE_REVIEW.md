# Completed Checklist Archive Review

Date: 2026-05-14

Classifies all checklist documents in `Docs/` as active, archive, superseded, or decision-needed. Source: `Docs\DOCS_INDEX.md` entries and opening status lines of each checklist.

---

## Summary

| Classification | Count | Files |
|---|---|---|
| **Archive (completed)** | 6 | See below |
| **Active (tracks remaining work)** | 2 | `DEPLOYABILITY_CHECKLIST.md`, `UI_IMPROVEMENT_CHECKLIST.md` |
| **Decision-needed** | 0 | None |

---

## Archive Checklists (Completed — Do Not Add To)

These checklists are historical records. Their content is fully completed and pruned. They are retained for traceability only. New implementation work should not reference or extend them.

| File | Status | Completed |
|---|---|---|
| `CODE_CLEANUP_CHECKLIST.md` | **Archive** | "Status: completed and pruned on 2026-05-06" |
| `CONTROL_SURFACE_HARDENING_CHECKLIST.md` | **Archive** | "completed control-surface hardening archive" (DOCS_INDEX description) |
| `NETWORK_MODE_CHECKLIST.md` | **Archive** | "completed implementation archive for experimental standalone/coordinator/worker mode" (DOCS_INDEX) |
| `UI_CHECKLIST.md` | **Archive** | "completed UI improvement archives with completed rows pruned" (DOCS_INDEX) |
| `UI_CHECKLIST_2.md` | **Archive** | Same as above |
| `UI_CHECKLIST_3.md` | **Archive** | Same as above |

**Recommended docs index wording**: All six are already described as "archive" or "completed archive" in `DOCS_INDEX.md`. No wording changes needed.

---

## Active Checklists (Track Remaining Work)

These checklists describe work still being considered or in progress.

| File | Status | Notes |
|---|---|---|
| `DEPLOYABILITY_CHECKLIST.md` | **Active** | "release-builder, config-template, and packaging readiness status" — tracks release pipeline readiness; may be updated when new release components are added |
| `UI_IMPROVEMENT_CHECKLIST.md` | **Active** | "remaining future UI improvement ideas; not part of the deployable operator package by default" — ideas backlog; intentionally kept as future reference |

---

## Additional Docs With "Checklist" In Name

Not in `Docs/` root but worth noting:

| File | Location | Classification |
|---|---|---|
| `BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md` | `Docs/` root | **Operator reference** — a step-by-step readiness checklist for browser smoke environment; not a work-tracking checklist; should be classified as "Operator Quick Start" |
| `Pipeline\NEW_PC_CHECKLIST_MediaPipelineRemuxEncodeAIO.md` | `Pipeline/` | **Operator reference** — machine setup checklist; not a work-tracking checklist |

---

## Docs Index Wording Review

Current `DOCS_INDEX.md` descriptions for the archive checklists:

| File | Current description | Correct? |
|---|---|---|
| `CODE_CLEANUP_CHECKLIST.md` | "completed V4 cleanup archive. Completed checklist rows have been pruned from active tracking." | Correct |
| `CONTROL_SURFACE_HARDENING_CHECKLIST.md` | "completed control-surface hardening archive." | Correct |
| `NETWORK_MODE_CHECKLIST.md` | "completed implementation archive for experimental standalone/coordinator/worker mode." | Correct |
| `UI_CHECKLIST.md/.2/.3` | "completed UI improvement archives with completed rows pruned." | Correct |
| `UI_IMPROVEMENT_CHECKLIST.md` | "remaining future UI improvement ideas; not part of the deployable operator package by default." | Correct |
| `DEPLOYABILITY_CHECKLIST.md` | "release-builder, config-template, and packaging readiness status." | Correct |

All descriptions are accurate. No wording changes needed.

---

## Recommendation

- **Do not delete** any archive checklists — they document completed work with traceability value.
- **Do not add new rows** to any archive checklist — if new work emerges in a completed area, start a new tracking doc.
- The `BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md` naming could be confused with "work checklist" — it is an operator reference tool, not a work-tracking list. Its description in `DOCS_INDEX.md` is correctly in the Operator Docs section.

---

## Files Inspected

- `Docs\DOCS_INDEX.md`: checklist descriptions in Operator Docs and Engineering Docs sections
- `Docs\CODE_CLEANUP_CHECKLIST.md`: status line confirms archive

---

## Task Output

```
Task ID: CLN-008
Files inspected: Docs\DOCS_INDEX.md, Docs\CODE_CLEANUP_CHECKLIST.md (status line)
Files changed: Docs\CHECKLIST_ARCHIVE_REVIEW.md (created)
Validation: Cross-referenced DOCS_INDEX descriptions with checklist status lines.
Findings: 6 archive checklists correctly described. 2 active checklists correctly described. No wording changes needed.
Open questions: None.
Risk: Low — documentation only.
```
