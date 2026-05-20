# V5 Transition Status Board

Date: 2026-05-19

Administrative overview of the V5 Tauri/WebView2 transition. Use as a quick orientation for new contributors and as a session-start reference for Claude/Codex handoffs.

This is a read-only status summary. It does not plan new work or approve engineering changes.

---

## Status Key

| Status | Meaning |
|---|---|
| **Stable fallback** | Working in Tk; not yet in WebView; V4 is backup |
| **Preview** | Implemented in WebView preview; not production replacement |
| **Partial parity** | WebView covers significant scope but has noted gaps |
| **Strong parity** | WebView covers the same operator workflow as Tk |
| **Read-only** | WebView provides read visibility only; mutation remains Tk-owned |
| **Not started** | No WebView equivalent exists |
| **Deferred** | Intentionally deferred; reason documented |

---

## Tk Fallback

| Item | Status | Notes |
|---|---|---|
| `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat` | **Stable fallback** | The supported production operator UI; must not be weakened |
| CustomTkinter controllers / views | **Stable fallback** | All Tk features remain functional; WebView parity is additive |
| V4 backup workspace | **Stable fallback** | `MediaPipelineRemuxEncodeAIO_V4` — untouched; known-good recovery path |

---

## Local API Backend

| Item | Status | Notes |
|---|---|---|
| 25 GET read routes | **Strong parity** | All implemented; auth coverage complete; schemas stable |
| 25 POST command routes | **Strong parity** | All implemented; mutation classes documented |
| Bootstrap token auth | **Strong parity** | Token-protected; Tauri shell receives token before WebView opens |
| Command journal (FIFO) | **Strong parity** | In-memory bounded; rendered in Command History and Diagnostics |
| Backend ownership enforcement | **Strong parity** | Frontend cannot pass raw paths, exec processes, or bypass guards |

---

## Tauri Shell

| Item | Status | Notes |
|---|---|---|
| Basic Tauri/WebView2 shell | **Preview** | Source/dev prereq and build gates passed on 2026-05-18; lifecycle guardrails now include backend health/crash events, WebView recovery banner, and single-instance rejection; not package-mode clean-machine proof |
| Pre-window asset gate | **Preview** | Validates backend-served assets before opening WebView2 |
| Close readiness / shutdown flow | **Preview** | Shell checks `GET /api/backend/close-readiness` before shutdown; armed schedule-stop watchers now block safe-close posture, terminal stop-requested watcher state is exposed without blocking safe close, structured watcher evidence renders in WebView and native Tauri close prompts, backend process exit/health failures emit lifecycle events, and coverage includes browser-backed lifecycle smoke plus browser-free Local API lifecycle contract tests |
| Tauri prereq/build gates | **Preview** | `Test-TauriShell-Prereqs.ps1 -CheckOnly` and `Test-TauriShell-Build.ps1` passed in source/dev validation on 2026-05-18; `Test-TauriShell-ProductionSurface.ps1` now audits production-surface lifecycle guardrails; PG-3 clean-machine package-mode launch still open |
| Package-mode launch smoke | **Preview** | Fresh current-handoff package `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` built with `-IncludeTauriPreviewBinary -Verify`; copied-bundle packaged launch/close passed locally, but the local boundary report found 8 developer-tool signals, so this is transfer readiness evidence only |
| Production daily-driver use | **Deferred** | Source/dev validation is green; PG-3 clean-machine package-mode launch and broader representative real-media validation remain required before daily-driver trust |

---

## WebView Pages

| Page | Status | Remaining gaps |
|---|---|---|
| Home (status, progress, context) | **Partial parity** | Sample validation record flow present; progress history not yet persisted |
| Live telemetry | **Partial parity** | Idle NVENC visible; longer history/export deferred |
| Queue | **Partial parity** | No queue mutation controls; launch decision checklist present |
| Completed | **Partial parity** | No repair/reconcile; output acceptance checklist present |
| Pending Publish | **Partial parity** | Drain command backend-owned; publish button guard present; true repair deferred |
| Rename | **Partial parity** | Apply readiness ledger present; more presets deferred until real usage proves need |
| Launch | **Partial parity** | Backend preflight present, including continuous schedule-stop watcher evidence; close-readiness visible; backend remains authoritative |
| Settings | **Partial parity** | ~76 of ~89 keys in structured builders; non-secret raw-only gaps closed, auth secrets intentionally hidden |
| Diagnostics | **Strong partial** | State artifact summary, command journal, tail reader, owner-page handoff, close-readiness watcher evidence, and backend lifecycle command evidence all present |
| Reports | **Partial parity** | Browser smoke now covers failure/audit triage and read-only handoff navigation; no rerun/export mutation in WebView |
| Schedule | **Partial parity** | Backend-owned preview/save editor is present for `schedule_enabled`/`schedule_grid`; coverage review, selected day detail, Node smoke, and browser-backed schedule/launch smoke are present; `/api/schedule` exposes read-only backend continuous watcher state for Schedule/Launch visibility; armed and stop-requested watcher states are covered through API/browser validation; backend Launch preflight/start owns the continuous schedule-stop watcher for WebView-started continuous runs; Tk remains fallback |
| Network | **Read-only** | Persisted worker state visible; lifecycle controls remain Tk-owned |
| Maintenance | **Partial parity** | Browser smoke covers health/readiness and dry-run result rendering; local API smoke now executes backend-owned release/backfill dry-run POST routes against temp state; no real repair actions |

---

## Release Package

| Item | Status | Notes |
|---|---|---|
| Clean release builder | **Strong parity** | `Build-MediaPipelineRemuxEncodeAIO-Release.ps1` — strips live config, logs, state |
| Release self-test | **Strong parity** | Full unskipped `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` passed on 2026-05-18 with bundled tool integration and end-to-end smoke included |
| Release manifest | **Strong parity** | `release_manifest.json` written on each build |
| Engineering handoff verification | **Strong parity** | `-Verify -IncludeTests` flag |
| Current PG-3 handoff candidate | **Preview** | `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116`; release self-test and copied-bundle package-mode Tauri launch passed locally; clean-machine PG-3 still open |
| Personal config protection | **Strong parity** | Release gate fails if live config is accidentally included |

---

## Tests and Smokes

| Area | Status | Count (approximate) | Notes |
|---|---|---|---|
| Python unit tests | **Strong parity** | ~100+ test files | Covers config, queue, process, rename, pending publish, API, facade layers |
| Pipeline PS unit checks | **Strong parity** | `Invoke-UnitChecks.ps1` | Covers routing, config, module imports |
| Reliability regression | **Strong parity** | `Invoke-ReliabilityRegressionChecks.ps1` | Covers known regression scenarios |
| Tool integration checks | **Strong parity** | `Invoke-ToolIntegrationChecks.ps1` | Requires bundled tools |
| Non-browser WebView smokes | **Strong parity** | 8 wrappers | Python/Node fixture-backed checks, no Chrome/Edge needed |
| Browser-backed WebView smokes | **Partial parity** | 15 wrappers | Chrome/Edge required; skip cleanly if absent; 19 browser-backed Python smoke tests passed on 2026-05-18 with hash-backed no-mutation assertions |
| Local API contract smokes | **Strong parity** | 3 wrappers | Browser-free close-readiness/shutdown contract, Maintenance release/backfill dry-run route contract, and sample-validation preview/append/read/tail contract checks against temporary state |
| Tauri shell scaffold test | **Preview** | 1 file + 1 audit script | Static layout, lifecycle monitor, single-instance guard, WebView lifecycle bridge/banner, production-surface audit, and prohibited pattern checks |
| WebView navigation static test | **Preview** | 1 file | Asset structure and DOM ID checks |

---

## Real-Media Validation

| Item | Status | Notes |
|---|---|---|
| Real-media playbook | **Documented** | `Docs/sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` |
| Worksheet generator | **Documented** | `New-RealMediaValidationWorksheet.ps1` creates Markdown evidence under `Docs\RealMediaValidationRuns`; generated worksheets are excluded from clean releases; 2026-05-18 follow-up planning worksheet created without sample paths |
| Sample validation record flow | **Preview** | Home Validation Log — evidence-only; preview now shows current backend evidence and a read-only real-media pilot plan before append; not automatic acceptance |
| Actual real-media run through WebView | **Partial parity** | PG-2 has limited accepted evidence anchors, but representative category coverage and current accepted-record reconciliation remain open before daily-driver trust |
| FFmpeg route/encode/remux proof | **Not automated** | No smoke or unit test covers this; requires real-media run |
| Subtitle OCR/SRT conversion proof | **Not automated** | Same — requires real samples with BDPGS/TX3G |
| Audio routing proof | **Not automated** | Same — requires real multi-audio samples |

---

## Recommended Next Administrative Tasks

These do not require engineering changes.

1. Copy or rebuild the verified `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` package on the target validation machine and run PG-3 package-mode validation before default-launcher promotion.
2. Keep `Docs/architecture/DEPLOYABILITY_CHECKLIST.md` current with future package-mode/clean-machine results; source/dev status was refreshed on 2026-05-18.
3. Keep future product-version bumps centralized in `Pipeline/Modules/Versioning.ps1`; the stale version-label audit was resolved on 2026-05-18.
4. Fill `Docs/RealMediaValidationRuns/real_media_validation_20260518_transition_followup_plan.md` with operator-selected sample paths, then follow `Docs/sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` with a small known batch.

---

## Recommended Next Engineering Tasks

These require engineering planning.

1. Network page: move coordinator/worker lifecycle behind a backend command contract so lifecycle controls can be added without Tk dependency.
2. Completed/Pending repair: dry-run/rollback/source-policy contracts are now design-published; implement backend dry-run routes before adding any mutation route or WebView control.
3. Real-media proof run: complete the validation playbook before treating the WebView as a daily-driver shell.
4. Audit/Reports export/rerun handoff: decide whether WebView should remain read-only or gain backend-owned command contracts.

---

## CLN2 Task Series Completion — 2026-05-15

All 20 tasks in `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md` (CLN2-01 through CLN2-20) are complete. Documentation-only work; no runtime or media behavior changed.

```
Completed:
  CLN2-01  Validation Ladder Freshness Review
  CLN2-02  Browser Smoke Runner Failure Triage Addendum
  CLN2-03  Root Script Inventory Sync
  CLN2-04  Release Layout Gate Coverage Review
  CLN2-05  Docs Index Delegation Section Cleanup
  CLN2-06  Tauri Preview Status Language Sweep
  CLN2-07  Real-Media Validation Worksheet Dry Run
  CLN2-08  WebView Smoke Boundary Text Sweep
  CLN2-09  API Route Count Consistency Sweep — confirmed 43 routes (21+22) at that time; current route inventory is 50 routes (25+25); corrected DOCS_INDEX stale-count reference
  CLN2-10  Diagnostics Target Count Consistency Sweep — confirmed 20 targets; tail route shares same allowlist
  CLN2-11  Settings Raw-Key Follow-Up Review — corrected count to 6 raw-only (ConsoleLogLevel/FileLogLevel now in builder); ranked 4 builder-priority candidates
  CLN2-12  Rename Documentation Drift Review — confirmed no drift; noted template_preset/template_catalog gap (not stale text)
  CLN2-13  Pending Publish Documentation Drift Review — confirmed dry-run, guard, drain ownership, true repair deferral
  CLN2-14  Network Read-Only Guardrail Review — confirmed no lifecycle controls; networkView.js guardrail text intact
  CLN2-15  Operator Glossary Coverage Addendum — 5 new entries (Active Media Policy Boundary, Browser-Backed Smoke, CDP, Continuous Schedule-Stop Watcher, Publish Reconciliation); 5 rows added to Terminology Consistency Guide
CLN2-16  Changelog Navigation Mini-Index Proposal — mini-index for 2026-05-13 to 2026-05-15 sprint (13 subsystem groups) appended to archive/admin-audits/CHANGELOG_NAVIGATION_HEALTH_REVIEW.md
  CLN2-17  Frontend Module Export Inventory Refresh — 4 modules updated; new total 985 flat exports (was 959, +26)
  CLN2-18  DOM ID Inventory Delta Review — 841 HTML IDs, 247 byId() IDs, 0 phantom references; targeted refresh of ~60 high-value IDs recommended (not done — out of scope for CLN2)
  CLN2-19  Real-Media Validation Evidence Template Review — Real-Media Output Proof table and Publish Reconciliation check added to evidence template
  CLN2-20  Return-To-Transition Handoff Summary (this entry)

Deferred:
  CHANGELOG_NAVIGATION_PROPOSAL.md full TOC insertion into REMEDIATION_CHANGELOG.md — operator review required before insertion
  DOM ID inventory targeted refresh (~60 high-value byId() IDs not yet in WEBVIEW_DOM_ID_INVENTORY.md) — low-risk, not urgent
  RENAME_TOOL_EDGE_CASE_CATALOG.md: template_preset/template_catalog coverage gap — engineering coverage, not a doc error

Validation run:
  All CLN2 tasks are documentation-only. No test suite runs were required; no code was changed.

Docs updated (CLN2-09 through CLN2-19):
  Docs/archive/admin-audits/LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md — freshness recheck appended
  Docs/DOCS_INDEX.md — stale-count reference corrected
  Docs/archive/admin-audits/DIAGNOSTICS_TARGET_SYNC_AUDIT.md — freshness recheck appended
  Docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md — count corrected (8→6 raw-only), Ranked Builder Priority section added
  Docs/archive/admin-audits/RENAME_DOCS_FRESHNESS_REVIEW.md — freshness review appended
  Docs/archive/admin-audits/PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md — freshness review appended
  Docs/archive/admin-audits/NETWORK_READONLY_WORDING_AUDIT.md — freshness review appended
  Docs/operator/OPERATOR_GLOSSARY.md — 5 new entries added
  Docs/operator/TERMINOLOGY_CONSISTENCY_GUIDE.md — 5 vocabulary table rows added
  Docs/archive/admin-audits/CHANGELOG_NAVIGATION_HEALTH_REVIEW.md — mini-index for 2026-05-13 to 2026-05-15 sprint appended
  Docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md — 4 module counts updated (985 total); freshness addendum appended
  Docs/archive/admin-audits/WEBVIEW_DOM_ID_DEAD_REFERENCE_AUDIT.md — delta review appended (841 HTML IDs, 247 byId(), 0 phantoms)
  Docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md — Real-Media Output Proof table + Publish Reconciliation check added
  Docs/archive/completed-audits/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md — CLN2-19 freshness addendum appended

Open questions:
  None blocking transition progress.

Return-to-transition recommendation:
  The next implementation batch should focus on:
  1. Real-media proof run (operator task): all validation infrastructure is ready — worksheet generator, evidence template with Output Proof board and Publish Reconciliation, sample validation flow. Complete Rung 5 of the validation ladder with real samples before treating WebView as a daily-driver shell.
  2. Settings builder: add BdpgsOcrToolPath + BdpgsOcrTessdataPath as a paired builder entry (Priority 1/2 from CLN2-11 — silent OCR failure risk when misconfigured).
  3. DOM ID inventory partial refresh: add the ~60 high-value byId()-accessed IDs identified in CLN2-18 (diagnostics tail/log/state, network rows, launch policy/preflight, pending drain decision, maintenance form inputs) to WEBVIEW_DOM_ID_INVENTORY.md.
4. Version bump readiness review: archive/admin-audits/STALE_VERSION_LABEL_AUDIT.md previously flagged the v5.000 bump as open; resolved 2026-05-18 with product-version labels aligned to v5.000.
```

---

## Key Documents

| Document | Purpose |
|---|---|
| `Docs/active-plans/V5_TAURI_TRANSITION_CURRENT_PLAN.md` | Current engineering transition plan |
| `Docs/architecture/TAURI_WEBVIEW_PARITY_MATRIX.md` | Detailed Tk vs WebView parity status per page |
| `Docs/sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` | Real-media validation procedure |
| `Docs/architecture/V5_MIGRATION_RISK_REGISTER.md` | Risk register with mitigations |
| `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` | What must not be casually changed |
| `Docs/testing/VALIDATION_LADDER_RUNBOOK.md` | What to run for each change type |
| `Docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md` | Shell vs backend lifecycle boundary |
