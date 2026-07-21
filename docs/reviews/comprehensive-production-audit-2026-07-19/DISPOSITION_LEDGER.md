# Disposition Ledger

Status: historical reconciliation in progress.

## Allowed Dispositions

- Still present.
- Fixed and adequately covered.
- Fixed but missing regression coverage.
- Partially fixed.
- Superseded.
- Duplicate or merged.
- Cannot reproduce.
- Deferred with reason.
- Accepted risk.
- Requires runtime evidence.
- Requires representative real-media evidence.

Historical entries retain their original IDs. New IDs are not issued until
the coordinator checks for cross-audit duplicates and verifies the evidence.

## Historical Reconciliation

| Historical ID / source | Original summary | Initial classification | Current evidence | Related current ID | Uncertainty / next proof |
| --- | --- | --- | --- | --- | --- |
| HIST-FR | Function/module audit, 61 deduplicated findings | reconciled_documentary | Source register plus current checklist | Original `FR-*` IDs | Ten closures need present-source/test verification; FR-015 still needs representative subtitle evidence |
| HIST-NCW | Network coordinator/worker audit, 35 findings | fixed and covered, pending present-source revalidation | Finding register and later disposition ledger | Original `NCW-*` IDs | Historical closure does not by itself prove the current overlay |
| HIST-CSW | Full code sweep, 53 worker findings merged/reconciled below | mixed | Coordinator review, remediation packet, current source | Original `CSW-*` / worker IDs | Three P1 settings, four P2, and one P3 carry-forward independently verified; several candidates still need verification |
| HIST-FFA | Full functional audit | mixed | Final report | `AUDIT-*`, `SAFETY-*` | Blocked/skipped controls and missing real-media/clean-machine evidence remain open evidence gaps |
| HIST-CQL | CodeQL baseline, 32 rule groups | mixed | CodeQL disposition ledger | Rule-group names | Remote authoritative closure remains required for locally fixed defects |

## Current Campaign Dispositions

| Finding ID | Disposition | Date | Evidence | Rationale / remaining work |
| --- | --- | --- | --- | --- |
| CSW-2026-07-09-SCHEDULE-001 | Still present | 2026-07-19 | Source plus isolated restart reproduction | Historical P2 retained; remediation not authorized |
| CSW-2026-07-09-MAINTENANCE-002 | Still present | 2026-07-19 | UI/facade/test trace plus focused PowerShell check | Historical P2 retained; remediation not authorized |
 | CPA-2026-07-19-001 | Remediated in current overlay | 2026-07-20 | v2 smoke map discovers all 34 modules, classifies 25 wrapper-backed/9 direct-only, validates exact catalog headings, and reconciles 45 numeric claims across 12 active docs; focused tests plus canonical `--check` pass | Fixed and regression-covered in `MP-CHANGE-2026-0720-009`; not yet committed or shipped |
| CPA-2026-07-19-002 | Verified open | 2026-07-19 | Overlay diff, call trace, and no-write PowerShell binding reproduction | New overlay-only P2; remediation not authorized |
| CPA-2026-07-19-003 | Verified open; independent P1 verification complete | 2026-07-19 | Two isolated reproductions plus HEAD/source/test trace | New P1 affecting HEAD and overlay; representative media still required |
| CPA-2026-07-19-004 | Verified open; independent P1 verification complete | 2026-07-19 | Independent and coordinator lifecycle/source traces | New P1 affecting HEAD and overlay; native hard-crash census still required |
| CPA-2026-07-19-005 | Verified open; independent P1 verification complete | 2026-07-19 | Independent and coordinator in-memory reproductions plus HEAD/source trace | New P1 affecting HEAD and overlay; native descendant/Tauri proof still required |
| CPA-2026-07-19-006 | Verified open | 2026-07-19 | Rust source, adjacent contract, official runtime docs, test search | New P2 affecting HEAD and overlay; native wait-error injection pending |
| CSW-2026-07-09-HOME-003 | Still present | 2026-07-19 | HEAD/current source plus isolated actual-module DOM-stub reproduction | Historical P2; command gate remains fail-closed but facts contradict it |
| CSW-2026-07-09-TELEMETRY-004 | Still present | 2026-07-19 | HEAD/current source plus isolated actual-module Node reproduction | Historical P2; browser timing capture pending |
| CPA-2026-07-19-007 | Verified open | 2026-07-19 | HEAD/current source, registry query, retry/test trace | New P2; representative subtitle media and queue soak pending |
| CSW-2026-07-09-SETTINGS-001 | Still present; independent P1 verification complete | 2026-07-19 | Architecture boundary, production candidate-builder trace, and focused passing test | Historical P1; response redaction does not prevent browser request-side exposure |
| CSW-2026-07-09-SETTINGS-002 | Still present; independent P1 verification complete | 2026-07-19 | Python projection, PowerShell schema/runtime trace, and actual-function no-write reproduction | Historical inert classification disproven; representative policy sampling pending |
| CSW-2026-07-09-SETTINGS-003 | Partially fixed; independent P1 verification complete | 2026-07-19 | Current lock/digest trace and deterministic two-facade lost-update reproduction | Sequential stale guard exists; cross-process compare/write race remains |
| CPA-2026-07-19-008 | Verified open | 2026-07-19 | Current source/metadata counts, active inventories, and generator/check search | New P3; row-by-row settings semantic review pending |
| CSW-2026-07-09-PENDING-003 | Still present | 2026-07-20 | Production discovery/consumer/WebView trace plus focused ordinary-orphan tests | Historical P3; fail-closed safety is strong but normal product flow has no proposal producer |
| CSW-2026-07-09-RENAME-004 | Still present | 2026-07-20 | Current/HEAD frontend trace, actual-module Node VM reproduction, and focused 57-test rename suite | Historical P2; backend prevents duplicate reversal but history refresh re-enables stale undo UI |

## Function/Module Audit (`FR-001`–`FR-061`)

The original register reported 59 fixed and two deferred. Current canonical
status closes the two deferred decisions. Every ID is classified below without
issuing replacement IDs.

| IDs | Classification | Evidence / remaining limit |
| --- | --- | --- |
| FR-001, FR-002, FR-003, FR-005, FR-006, FR-007, FR-009, FR-011, FR-012, FR-013, FR-014, FR-017, FR-018, FR-019, FR-020, FR-021, FR-022, FR-023, FR-025, FR-027, FR-028, FR-029, FR-031, FR-032, FR-034, FR-035, FR-036, FR-037, FR-038, FR-039, FR-040, FR-041, FR-043, FR-044, FR-045, FR-047, FR-048, FR-050, FR-051, FR-052, FR-053, FR-054, FR-055, FR-056, FR-057, FR-058, FR-059, FR-060, FR-061 | Fixed and adequately covered (historical documentary classification) | Per-finding disposition rows in the original register; present-overlay regression still requires sampled verification |
| FR-004, FR-008, FR-010, FR-015, FR-024, FR-026, FR-030, FR-033, FR-046, FR-049 | Fixed but missing per-finding regression/disposition evidence in that register | Present source/tests must be verified; FR-015 additionally requires representative subtitle real-media evidence |
| FR-016 | Fixed and adequately covered for preserve-all topology | Current checklist records real-video preserve-all and two-stream topology proof; broader Dynamic-HDR/hardware evidence remains separate |
| FR-042 | Fixed and adequately covered | Current checklist records evidence-writing `-DryRun` retained and separate no-write `-PlanOnly` added |

## Network Coordinator/Worker Audit (`NCW-*`)

| IDs | Classification | Evidence / remaining limit |
| --- | --- | --- |
| NCW-P1-01, NCW-P1-02, NCW-P1-03, NCW-P1-04, NCW-P1-05, NCW-P1-06, NCW-P1-07, NCW-P1-08, NCW-P1-09, NCW-P1-10, NCW-P1-11, NCW-P1-12, NCW-P1-13, NCW-P1-14 | Fixed and adequately covered (historical), pending present-source revalidation | Later ledger has one disposition/test row per finding |
| NCW-P2-01, NCW-P2-02, NCW-P2-03, NCW-P2-04, NCW-P2-05, NCW-P2-06, NCW-P2-07, NCW-P2-08, NCW-P2-09, NCW-P2-10, NCW-P2-11, NCW-P2-12, NCW-P2-13, NCW-P2-14, NCW-P2-15, NCW-P2-16, NCW-P2-17, NCW-P2-18, NCW-P2-19 | Fixed and adequately covered (historical), pending present-source revalidation | Later ledger has one disposition/test row per finding |
| NCW-P3-01, NCW-P3-02 | Fixed and adequately covered (historical), pending present-source revalidation | Later ledger has one disposition/test row per finding |

## Full Code Sweep — Coordinator Merge

| Coordinator ID | Severity | Merged worker IDs | Classification |
| --- | --- | --- | --- |
| COORD-001 | P0 | QUEUE-001, QUEUE-004 | Fixed and adequately covered on current tree: rerun source imports and all affected summaries pass freshness/integrity check |
| COORD-002 | P1 | QUEUE-002 | Fixed and adequately covered on current tree: Python and PowerShell malformed manifests fail closed |
| COORD-003 | P1 | HOME-001, DIAGNOSTICS-001, TELEMETRY-002, TELEMETRY-003, REPORTS-001, REPORTS-002, METRICS-003 | Fixed and covered historically; present-source revalidation required |
| COORD-004 | P1 | HOME-002, LAUNCH-001 | Fixed and covered historically; present-source revalidation required |
| COORD-005 | P1 | COMPLETED-001, NETWORK-001, SETTINGS-003, RENAME-002 | Mixed: `SETTINGS-003` remains open; `RENAME-002` is fixed and current-source/test verified; other merged items remain historically fixed pending revalidation |
| COORD-006 | P1 | LIBRARIES-001, LIBRARIES-002, RENAME-001 | Mixed: `RENAME-001` is fixed and current-source/test verified; library items remain historically fixed pending revalidation |
| COORD-007 | P1 | METRICS-001, METRICS-002, REPORTS-003 | Fixed and covered historically; present-source revalidation required |
| COORD-008 | P2 | QUEUE-003, NETWORK-002, NETWORK-004 | Mixed verification: `QUEUE-003` fixed/current test-covered; Network items remain historically fixed pending present-source revalidation |
| COORD-009 | P2 | PENDING-001, PENDING-002, HOME-003, COMPLETED-002, SETTINGS-004, RENAME-003 | Mixed: `HOME-003` remains open; Pending 001/002 and `RENAME-003` are fixed and current-source/test verified; other items remain historically fixed pending revalidation |

Historical packet `MP-CHANGE-2026-0709-003` records focused tests and one
real-media rerun/park/drain/publish proof. It also records an unrelated red
aggregate release test, two residual broad-browser failures, and blocked strict
packet validation. Those limitations remain attached to the closure evidence.

### Other Sweep Findings

| Historical ID | Classification | Current evidence / next proof |
| --- | --- | --- |
| LAUNCH-002 | Fixed and covered historically | Strict backend start controls and payload tests; verify current overlay |
| LIBRARIES-003 | Superseded/fixed | Canonical docs now disclose LibraryProfiles ownership and compatibility |
| LIBRARIES-004 | Fixed but current regression verification required | Historical packet added path/promotion negative coverage |
| DIAGNOSTICS-004 | Fixed but current source verification required | Later inventory/generated-context evidence indicates stale actions were removed |
| PENDING-001 | Fixed and adequately covered on current HEAD and overlay | Guard returns `allowed=true`, blocked state is advisory/review-only, and browser smoke submits the unchanged drain request to backend validation |
| PENDING-002 | Fixed and adequately covered on current HEAD and overlay | Index refresh is read-only; explicit recovery owns mutation and emits intent/result evidence; focused safety check passes |
| PENDING-003 | Still present, P3, current HEAD and overlay | Ordinary scan emits no proposal, consumer is the only production reference to proposal fields, successful tests inject one, and WebView still offers the futile dry-run |
| SETTINGS-002 | Still present, P1, current HEAD and overlay | Projection plus actual runtime merge materializes arbitrary legacy extras as script variables; earlier inert classification disproven |
| MAINTENANCE-001 | Fixed and adequately covered | Verify and Include Tests default checked; builder valid-pair guard retained |
| CSW-2026-07-09-SCHEDULE-001 | Still present, P2, current HEAD and overlay | Coordinator source verification confirms watch baseline/tracker/pending state is memory-only; isolated restart reproduction pending |
| CSW-2026-07-09-MAINTENANCE-002 | Still present, P2, current HEAD and overlay | UI promises no checkpoint rewrite while facade deliberately supplies a timestamped checkpoint and test requires the external write |
| REPORTS-004 | Partially fixed/deferred | Active implementation plan still calls for row freshness/source-count/rerun gates; current source verification pending |
| COMPLETED-003 | Requires source verification | Dry-run guidance/apply-route contradiction candidate |
| DIAGNOSTICS-002 | Requires source/security verification | Raw diagnostics redaction boundary candidate |
| DIAGNOSTICS-003 | Requires runtime evidence | Shell-open outcome may overclaim an unobservable result |
| METRICS-004, METRICS-005 | Requires source/operator-contract verification | Denominator and time-window disclosure semantics |
| METRICS-006 | Requires source verification | Read-only claim versus contained mutation controls |
| NETWORK-003 | Requires source/security verification | Coordinator-role authorization for join blob |
| RENAME-001 | Fixed and adequately covered on current HEAD and overlay | Derived destinations and sidecars are checked against the source-authorizing configured root; leaving it requires explicit outside-root confirmation |
| RENAME-002 | Fixed and adequately covered on current HEAD and overlay | Undo preflight pairs every metadata backup to an operation and boundary-checks both recorded and restored paths before mutation |
| RENAME-003 | Fixed and adequately covered on current HEAD and overlay | Apply requires a non-empty preview fingerprint and constant-time comparison against the backend-rebuilt current plan |
| RENAME-004 | Still present, P2, current HEAD and overlay | Actual-module reproduction proves apply-history refresh clears completed undo state and re-enables the same manifest; promoted under original ID |
| RENAME-005 | Fixed and adequately covered on current HEAD and overlay | Active inventory names facade/API active-work tests; current focused suite passes and tests prove no plan/apply call or filesystem mutation |
| SETTINGS-001 | Still present, P1, current HEAD and overlay | Documented hidden token boundary contradicted by production preview path and focused test carrying a real token |
| SETTINGS-003 | Partially fixed, P1, current HEAD and overlay | Sequential stale-authority guard exists, but deterministic separate-lock reproduction loses a disjoint update while both saves report success |
| QUEUE-001 | Fixed and adequately covered on current overlay; committed HEAD was not corrupt | Current `rerun_policy.py` compiles/imports and its refreshed summary passes integrity/currentness check |
| QUEUE-002 | Fixed and adequately covered on current HEAD and overlay | Typed Python error plus focused test and PowerShell malformed-manifest fail-closed check both pass |
| QUEUE-003 | Fixed and adequately covered on current HEAD and overlay | Canonical contract and both route inventories include `position`; focused contract test passes |
| QUEUE-004 | Fixed and adequately covered on current overlay | Three historically affected source/summary pairs pass targeted summary currentness/integrity check |
| TELEMETRY-001 | Requires source/runtime verification | Snapshot polling may rewrite ActiveJobs |
| TELEMETRY-004 | Still present; source and isolated runtime verified | First backend-stale poll is rewritten active; full browser timing proof pending |

## Full Functional Audit

| ID | Classification | Evidence / remaining limit |
| --- | --- | --- |
| AUDIT-001 | Fixed and adequately covered historically | Browser regression evidence for Completed evidence-row selection aliases |
| AUDIT-002 | Fixed and adequately covered historically | Static and repeated native-open evidence for Tauri Pipeline Log permission |
| SAFETY-001 | Confirmed audit-process incident; contained | Production runtime/media was accessed and one apply changed runtime evidence; affected run evidence is permanently invalid |
| SAFETY-002 | Confirmed audit-process incident; contained | Existing LocalAppData WebView2 profile accessed; affected run invalid |
| SAFETY-003 | Confirmed harness incident; contained | Timed-out isolated process tree survived outer timeout; affected run invalid |

Residual audit evidence: 757/970 authored controls passed, 160 blocked, 53
skipped, none failed/unclassified. Representative real media, native secondary
content/independent close, and clean-machine package/install evidence were not
established. Zero-unclassified touchpoints is not production-readiness closure.

### Browser evidence closure reconciliation — 2026-07-20

The historical 970-control result is retained as a baseline, not reused as the
current denominator. The source-derived ledger now contains 977 authored
controls. Its exact row identities and dispositions are in
`docs/generated/WEBVIEW_TOUCHPOINT_LEDGER.json`; runtime-generated and
Tauri-family records are reported separately and are not added to the authored
denominator.

| Snapshot | Authored | Passed | Failed/flaky | Blocked | Skipped |
| --- | ---: | ---: | ---: | ---: | ---: |
| Historical functional audit | 970 | 757 | 0 | 160 | 53 |
| Current row-derived evidence | 977 | 816 | 0 | 133 | 28 |

Under the closure taxonomy, the historical 213 blocked/skipped rows were
unexplained because they lacked a normalized prerequisite and next action. The
current rows reconcile as follows; each row has an exact prerequisite,
automation-feasibility flag, owner, next evidence action, and test or manual
recipe reference.

| Snapshot | Automated passed | Automated but failing | Legitimately blocked | Manual/native-only | Intentionally excluded | Stale entries removed | Unexplained gaps | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Historical baseline under current taxonomy | 757 | 0 | 0 | 0 | 0 | 0 | 213 | 970 |
| Current reconciled ledger | 816 | 0 | 92 | 41 | 28 | 0 | 0 | 977 |

The current authored rows also reconcile by precise reason category. A passed
duplicate row remains passed only because its disposition links to applicable
repeatable evidence; exclusions are not promoted to passed.

| Reason category | Authored rows | Closure condition |
| --- | ---: | --- |
| `automated_passed` | 763 | Closed by the row-linked browser/static evidence |
| `duplicate_coverage_with_traceable_evidence` | 53 | Closed only while the linked applicable test remains current |
| `missing_fixture_or_backend_state` | 56 | Build disposable route-specific selection, saved-state, CSV, series-scope, or command-effect fixtures and prove the backend result |
| `intentionally_hidden_or_feature_gated` | 21 | Supply a supported reachability fixture or remove/document the future/derived authored surface |
| `lifecycle_state_precondition_not_constructed` | 9 | Construct an owned active/guarded lifecycle state, prove command identity, and prove cleanup |
| `harness_limitation` | 6 | Add isolated full-effect Diagnostics proof/smoke/strict-gate/rerun process harnesses with observable completion |
| `native_os_tauri_interaction_unavailable` | 41 | Execute the linked isolated Windows/Tauri manual recipe and attach its success/failure artifacts |
| `unsafe_mutation_excluded_by_no_mutation_policy` | 28 | Retain the exclusion, or authorize an isolated full-effect fixture with rollback and no personal/live media roots |
| **Total** | **977** | **816 automated passed + 92 legitimately blocked + 41 manual/native-only + 28 intentionally excluded** |

Native closure is specifically assigned to `NATIVE-OS-SHELL-OPEN-001` (25
authored rows) and `NATIVE-PICKER-ISOLATION-001` (16 authored rows) in
`docs/testing/WEBVIEW_NATIVE_MANUAL_EVIDENCE_RECIPES.md`. Pipeline Log UIA and
independent-close recipes cover supplemental Tauri-family records outside the
977 authored denominator. The generated ledger is the complete row table: each
record contains page/workflow, stable locator/DOM ID, control type, backend or
local behavior, mutation class, exact prerequisite, owner, evidence state,
disposition, feasibility, and next evidence action.

<!-- BEGIN WEBVIEW BROWSER CONTROL CLOSURE SUMMARY -->
```json
{
  "current": {
    "authored_total": 977,
    "evidence_state": {
      "passed": 816,
      "failed": 0,
      "flaky": 0,
      "blocked": 133,
      "skipped": 28,
      "not_run": 0
    },
    "closure": {
      "automated_passed": 816,
      "automated_but_failing": 0,
      "legitimately_blocked": 92,
      "manual_native_only": 41,
      "intentionally_excluded": 28,
      "stale_entries_removed": 0,
      "unexplained_gaps": 0
    }
  }
}
```
<!-- END WEBVIEW BROWSER CONTROL CLOSURE SUMMARY -->

## CodeQL Audit

| Source rows / groups | Classification | Evidence / remaining limit |
| --- | --- | --- |
| Defect-rule rows 15–32 | Fixed but missing authoritative remote closure coverage | Local remediation recorded; full CodeQL workflow required and no alerts dismissed |
| `py/unused-local-variable` row 33 | Mixed | Three fixed defects plus eight intentional/stale cases; retain alert-level distinctions |
| `js/trivial-conditional` row 34 | Mixed | One fixed, one stale/superseded, two intentional guards |
| Non-defect/compatibility rows 40–50 | Accepted risk for the enumerated historical instances | Does not waive review of new instances |
| `rust/unused-variable` row 51 | Cannot reproduce / false positive | Cargo compilation proves format-string capture uses the binding |

## Cross-Audit Duplicate Notes

- FR-010 is related to, but narrower than, July QUEUE-002.
- FR-018 and FR-025 are earlier instances of strict-intent/degraded-evidence
  themes, not exact duplicates.
- FR-034 overlaps later close-readiness risk but covers a different shutdown
  transition.
- FR-042 and MAINTENANCE-002 both use “dry run” terminology but concern
  different commands and are not duplicates.
- July NETWORK-004 was merged into COORD-008 and relates closely to NCW-P2-16.
