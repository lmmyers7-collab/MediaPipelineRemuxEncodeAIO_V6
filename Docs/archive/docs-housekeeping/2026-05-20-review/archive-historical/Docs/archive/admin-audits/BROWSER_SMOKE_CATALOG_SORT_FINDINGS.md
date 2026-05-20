# Browser Smoke Ordering and Catalog Sort Findings

Date: 2026-05-14

Reviews browser smoke lists across docs for consistent ordering. Source: `Docs\BROWSER_SMOKE_TEST_RUNBOOK.md`, `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`, `Docs\DOCS_INDEX.md`.

---

## Summary

Browser smokes appear in a consistent order in `BROWSER_SMOKE_TEST_RUNBOOK.md` and `WEBVIEW_SMOKE_TEST_CATALOG.md`. A minor ordering difference exists in `DOCS_INDEX.md` — `HighRisk` appears third instead of first in the browser section. Non-browser and browser-backed smokes are clearly separated in all three docs. Schedule browser smoke appears near the top (position 1–2) in all docs.

No wording edits were made. This document records findings only.

---

## Order Comparison

### BROWSER_SMOKE_TEST_RUNBOOK.md and WEBVIEW_SMOKE_TEST_CATALOG.md (consistent)

| Position | Smoke |
|---|---|
| 1 | `Test-WebViewBrowserHighRiskSmoke.ps1` |
| 2 | `Test-WebViewBrowserScheduleSmoke.ps1` |
| 3 | `Test-WebViewBrowserLifecycleSmoke.ps1` |
| 4 | `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` |
| 5 | `Test-WebViewBrowserPendingDrainGuardSmoke.ps1` |
| 6 | `Test-WebViewBrowserCompletedPendingProofSmoke.ps1` |
| 7 | `Test-WebViewBrowserLargeTableSmoke.ps1` |
| 8 | `Test-WebViewBrowserRenameSmoke.ps1` |
| 9 | `Test-WebViewBrowserNetworkSmoke.ps1` |
| 10 | `Test-WebViewBrowserTelemetrySmoke.ps1` |
| 11 | `Test-WebViewBrowserSettingsLaunchSmoke.ps1` |

### DOCS_INDEX.md (minor deviation)

| Position | Smoke |
|---|---|
| 1 | `Test-WebViewBrowserScheduleSmoke.ps1` |
| 2 | `Test-WebViewBrowserLifecycleSmoke.ps1` |
| 3 | `Test-WebViewBrowserHighRiskSmoke.ps1` |
| 4–11 | (same as RUNBOOK/CATALOG) |

**Finding**: `Test-WebViewBrowserHighRiskSmoke.ps1` is first in the RUNBOOK/CATALOG (highest-urgency ordering) but third in DOCS_INDEX.md. This is a minor ordering inconsistency, not a functional problem.

---

## Non-Browser vs Browser Separation

All three docs clearly separate non-browser smokes (fixture-backed, no Chrome/Edge) from browser-backed smokes (require Chrome/Edge and Node.js). The distinction is correct in all docs.

---

## Acceptance Criteria

| Criterion | Status |
|---|---|
| Browser smokes appear in consistent order | Mostly — RUNBOOK and CATALOG are consistent; DOCS_INDEX.md has minor HighRisk/Schedule transposition |
| Non-browser and browser-backed smokes clearly separated | Pass — all docs separate the two groups |
| Schedule browser smoke appears near Schedule, not buried at the end | Pass — Schedule is position 1–2 in all docs |

---

## Suggested Fix (Optional, Low Priority)

Reorder the browser smokes in `DOCS_INDEX.md` to match the RUNBOOK/CATALOG order: HighRisk → Schedule → Lifecycle → ... This is a cosmetic improvement only. The current ordering does not cause any functional problem.

**No wording patches were applied.** If the operator wants to apply this fix, update lines 23–34 of `DOCS_INDEX.md` to place `Test-WebViewBrowserHighRiskSmoke.ps1` first.

---

## Files Inspected

- `Docs\BROWSER_SMOKE_TEST_RUNBOOK.md`: Running/per-smoke/interpretation sections; 11 browser smokes in defined order
- `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`: Browser smoke section; same order as RUNBOOK
- `Docs\DOCS_INDEX.md`: Operator Docs section; browser smoke entries lines 23–34

---

## Task Output

```
Task ID: CLN-005
Files inspected: Docs\BROWSER_SMOKE_TEST_RUNBOOK.md, Docs\WEBVIEW_SMOKE_TEST_CATALOG.md, Docs\DOCS_INDEX.md
Files changed: Docs\BROWSER_SMOKE_CATALOG_SORT_FINDINGS.md (created)
Validation: Compared order in all three docs; confirmed non-browser vs browser separation.
Findings: RUNBOOK and CATALOG are consistent. DOCS_INDEX.md has HighRisk at position 3 instead of 1. Schedule is position 1-2 everywhere.
Open questions: Operator to decide whether to reorder DOCS_INDEX.md to match RUNBOOK/CATALOG.
Risk: Low — documentation only.
```
