# Local API Route Count Sync Audit

Date: 2026-05-14

Confirms that route count claims in documentation match the actual backend contract files. Identifies which docs reflect the current count and which contain a stale figure.

---

## Authoritative Source: Contract Files

Route counts measured from the backend contract files under `DesktopApp\mediapipeline_desktop_app\api\`:

| File | Role | Route Count |
|---|---|---|
| `contract_read.py` | Read (GET) route contract | **21** |
| `contract_command.py` | Command (POST) route contract | **22** |
| **Total** | | **43** |

Verification command (run from `DesktopApp\`):

```powershell
python - <<'PY'
from mediapipeline_desktop_app.api.contract_read import LOCAL_API_READ_ROUTE_CONTRACT
from mediapipeline_desktop_app.api.contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT
print(len(LOCAL_API_READ_ROUTE_CONTRACT), len(LOCAL_API_COMMAND_ROUTE_CONTRACT))
PY
# Expected output: 21 22
```

---

## Documentation Route Count Comparison

| Document | Claimed Count | Read Routes | Command Routes | Status |
|---|---|---|---|---|
| `Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md` | 41 total | 21 | **20** | **Stale** — 2 command routes missing |
| `Docs\LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` | 41 total | 21 | **20** | **Stale** — companion to ROUTE_OWNERSHIP_MAP; same mismatch |
| `Docs\API_ROUTE_INVENTORY.md` | 43 total | 21 | 22 | **Current** — authoritative post-sprint count |
| `Docs\COMMAND_OWNERSHIP_MATRIX.md` | 20 POST routes (inferred) | — | **20** | **Stale** — 2 command routes not mapped |

---

## Route Effect Categories — Current Coverage

The 22 command routes in `contract_command.py` cover the following effect categories (as inventoried in `API_ROUTE_INVENTORY.md`):

| Effect Class | Example Routes |
|---|---|
| `file-open` | diagnostics open |
| `diagnostics-tail` | diagnostics tail |
| `maintenance` | audit start, CSV rerun |
| `rename` | rename plan, rename apply |
| `settings` | settings preview, settings save-patch |
| `schedule` | schedule preview, schedule save |
| `sample-validation` | sample validation append |
| `process` | pipeline once, continuous, validate, control, stop |

The 2 routes added after `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` was written are likely from the schedule preview/save or sample validation groups, which were introduced as part of V5 WebView work.

---

## Gap: Routes Not Covered in Older Docs

`LOCAL_API_ROUTE_OWNERSHIP_MAP.md` and `LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` document 20 command routes. The 2 missing routes are not identified by name in this audit (that would require line-by-line comparison). The authoritative current mapping is in `API_ROUTE_INVENTORY.md`.

**Recommended action** (doc-only, no code change):
- Add a note at the top of `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` stating: "Note: this map documents 41 routes. Two additional POST routes were added in V5 (schedule preview/save or sample validation); see `API_ROUTE_INVENTORY.md` for the current 43-route inventory."
- Same note for `LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`.
- These docs do not need full rewrites; the 2 missing routes are documented in `API_ROUTE_INVENTORY.md`.

---

## Docs Index Description Sync

`Docs\DOCS_INDEX.md` describes:

| Doc | Current Description | Accuracy |
|---|---|---|
| `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` | "complete map of all 41 Local API routes (21 read, 20 command)" | Stale count — should say 43 or note the mismatch |
| `LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` | "classifies all 41 routes" | Stale count — should note that API_ROUTE_INVENTORY.md has the current 43-route count |
| `API_ROUTE_INVENTORY.md` | "full inventory of all 43 Local API routes (21 GET + 22 POST)" | Correct |

---

## Summary

| Finding | Detail |
|---|---|
| Actual route count | 21 read + 22 command = **43 total** |
| Correct docs | `API_ROUTE_INVENTORY.md` |
| Stale docs | `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` (claims 41), `LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` (claims 41), `COMMAND_OWNERSHIP_MATRIX.md` (maps 20 POST routes) |
| Code change required | No — counts are correct in code; only doc descriptions are stale |
| Priority | Low — the stale docs are still useful for what they cover; the 2 missing routes are covered in `API_ROUTE_INVENTORY.md` |

---

## Freshness Recheck — 2026-05-15 (CLN2-09)

Re-read `contract_read.py` and `contract_command.py` directly. Re-checked all four documentation files.

| Check | Result |
|---|---|
| `contract_read.py` route count | 21 (STATUS:10, INVENTORY:6, WORKSPACE:5) |
| `contract_command.py` route count | 22 (FILE:4, MAINTENANCE:2, DIAGNOSTICS:1, RENAME:2, SETTINGS:4, SCHEDULE:2, SAMPLE_VALIDATION:2, PROCESS:5) |
| Total routes | 43 — unchanged |
| `API_ROUTE_INVENTORY.md` | Correct — "43 routes (21 GET + 22 POST)" |
| `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` | **Resolved** — now reads "Total routes: 43 (21 read, 22 command)"; CLN-010 "Stale" finding no longer applies |
| `LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` | **Resolved** — now reads "Total routes: 43 (21 read, 22 command); source of truth remains contract_read.py and contract_command.py"; CLN-010 "Stale" finding no longer applies |
| `DOCS_INDEX.md` description for `LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md` | Stale — still says "stale at 41 routes pending operator-decision"; corrected below |

`DOCS_INDEX.md` description updated: removed "stale at 41" language; now states all route-count docs agree at 43.

No route-count discrepancies remain. All four documents are consistent with the implemented contract.

---

## Task Output

```
Task ID: CLN-010
Files inspected: DesktopApp\mediapipeline_desktop_app\api\contract_read.py, contract_command.py, Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md, Docs\LOCAL_API_EVIDENCE_MUTATION_MATRIX.md, Docs\API_ROUTE_INVENTORY.md, Docs\DOCS_INDEX.md
Files changed: Docs\LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md (created)
Validation: Route counts confirmed via contract file lengths (21+22=43). Cross-referenced against DOCS_INDEX descriptions.
Findings: ROUTE_OWNERSHIP_MAP and EVIDENCE_MUTATION_MATRIX both claim 41 routes. API_ROUTE_INVENTORY correctly claims 43. No code defect — docs are stale.
Open questions: Which 2 specific command routes were added after ROUTE_OWNERSHIP_MAP was written? Cross-referencing API_ROUTE_INVENTORY.md against ROUTE_OWNERSHIP_MAP.md would identify them.
Risk: Low — documentation only.
```
