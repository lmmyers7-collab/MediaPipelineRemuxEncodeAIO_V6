# Open Work Checklist

> **Generated:** 2026-05-19 by full scan of all non-archived Markdown files; reconciled 2026-05-20 after stale-gate review.
> **Sources:** archived housekeeping and transition-review evidence under `Docs/archive/docs-housekeeping/2026-05-20-review/`, `Docs/architecture/V5_MIGRATION_RISK_REGISTER.md`, `Docs/testing/TEST_COVERAGE_MATRIX.md`, `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`, `Docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md`, `Docs/inventories/RENAME_SAFETY_TEST_INVENTORY.md`, `Docs/inventories/PENDING_PUBLISH_FIXTURE_INVENTORY.md`, `Docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md`, `Docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md`, `Docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`, `Docs/DOC_TOUCH_LOG.md`, and `Docs/REMEDIATION_CHANGELOG.md`.
> **Excludes:** `Docs/archive/`, config backups, run logs.

---

## P0 — Blockers (fix before promotion to daily driver / clean-machine handoff)

These remaining open blockers are external/operator validation gates, not stale local protected gates. Local source/dev gates are tracked as closed below unless a later scan reopens them.

- [x] **Backend shutdown safety** — Reconciled as complete: `/api/backend/shutdown` now returns `ok: false` and does not request shutdown when close-readiness is unsafe, including an armed schedule-stop watcher; WebView shutdown stays disabled until backend close-readiness is safe. Validation on 2026-05-19: lifecycle smoke, route inventory, and contract payload tests passed. Source: `REMEDIATION_CHANGELOG.md` row "Shutdown fail-closed" plus 2026-05-19 stale-blocker reconciliation.

- [x] **Queue priority route contract** — Reconciled as complete: `GET/POST /api/queue/priority` remain in V5, are documented in route inventory and ownership map, are present in read/command contracts, and are covered by source-scope/journaling tests. Validation on 2026-05-19: route inventory, contract payload, and focused Local API queue state route tests passed. Source: `REMEDIATION_CHANGELOG.md` row "Queue contract/source scope" plus 2026-05-19 stale-blocker reconciliation.

- [x] **PowerShell reliability regression** — Reconciled as complete: queue priority phase contract and deferred-publish drain smoke are restored. Validation on 2026-05-19: `Invoke-ReliabilityRegressionChecks.ps1` passed and `Invoke-EndToEndSmokeChecks.ps1` passed. Current V6 validation uses `Invoke-ReliabilityRegressionChecks.ps1` as the active WebView/backend compatibility wrapper, with archived legacy desktop-shell checks available only through `-RunLegacyDesktopChecks`. Source: `DOC_TOUCH_LOG.md` row "Queue plan reliability and end-to-end smoke restoration" plus 2026-05-19 stale-blocker reconciliation.

- [ ] **PG-3 clean-machine validation** — Package-mode launch/close on a separate clean Windows machine has not been run. This is a hard gate before promoting WebView/Tauri as the default launcher. Source: `VALIDATION_LADDER_RUNBOOK.md` and `RELEASE_PACKAGE_ADMIN_INVENTORY.md`.

- [x] **Real-media validation playbook** — Closed on 2026-05-28 by operator attestation. Representative real-media validation covered remux, encode/size policy, subtitle conversion, audio policy, and pending-publish/final-placement behavior. `Docs/RealMediaValidationRuns/README.md` records the non-sensitive status anchor; detailed run worksheets may remain local or excluded from release packaging when they contain personal paths. Re-run this validation after any FFmpeg/media-policy, subtitle, audio, publish/drain, source/scratch/output movement, or cleanup behavior change.

---

## High — Fix Now or Before Next Publish / Packaging Work

- [x] **Phase 6 destructive legacy removal gate** — Closed on 2026-05-29 for the local legacy surface burn-down: config-schema compatibility files, former command-payload adapters, flat Python facades/services, root launcher shims, `Pipeline` root launcher shims, and `Pipeline\Modules` are removed or empty, with active implementations under `app\<domain>` and `engine\<domain>`. Post-deletion validation covered active-reference cleanup, full source release wrapper validation, copied package-mode Tauri launch/close, Local API health plus WebView open, and fresh representative real-media validation for remux, encode/size, subtitles, audio, deferred pending publish, drain, and rename-output safety. PG-3 clean-machine validation remains a separate default-launcher promotion gate. Guardrails still block reintroducing old root launcher shim names and new dotted `Pipeline\Modules` files.

- [x] **Rename undo manifest state-root cleanup** — New rename undo manifests now resolve under `State\RenameUndo` when service state or app root is available; focused rename tests passed. Source: `DOC_TOUCH_LOG.md` row "Rename undo state-root safety cleanup".

- [x] **Rename safety test gaps** — Closed with backend-side duplicate-destination blocking for every colliding planned row plus Local API `rename.apply` absent/false `confirm_apply` rejection coverage that verifies no rename mutation occurs. Files: `service_rename_planner.py`, `test_service_rename_planner.py`, `test_application_facade_local_api.py`, `RENAME_SAFETY_TEST_INVENTORY.md`.

- [x] **Pending publish module ownership** — `MODULE_MAP.md`, pending-publish fixture inventory, and focused PowerShell guards now document/test parked media-plus-sidecars and backend-owned drain safety. Source: `DOC_TOUCH_LOG.md` rows "Pending publish safety guardrail tests and rollback fix" and "Pending Publish Ownership Boundary Guard".

- [x] **Dashboard command-surface drift** — Reconciled as complete: the rendered Home/Dashboard page does not expose pipeline start/control or pending-drain command controls, while the Launch/Pending Publish owning pages still expose the backend-owned command controls. `test_application_facade_web_static.py` pins this command-surface boundary.

- [x] **Evidence panel type violations and H1 title drift** — Closed with rendered WebView static checks: all panels declare `data-panel-type="evidence"` or `data-panel-type="interactive"`, evidence panels contain no buttons, and all 13 rendered page H1 titles match `V5_UI_DESIGN_REFERENCE.md` canonical page titles.

- [x] **No adversarial duplicate-instance test** — Closed with a process-launch facade test that starts one pipeline, simulates the first child process still running from the same bundle, then verifies the second pipeline start is rejected and the service launcher is not called again. Source: `TEST_SUITE_SUBSYSTEM_INVENTORY.md`.

---

## Medium — Fix Before Packaged Handoff or Wave 6

- [x] **WebView advisory logic duplicates backend policy** — Settings/Launch frontend risk helpers are now labelled/tested as advisory-only; backend Preview/Save and Launch validation remain authoritative. Source: `DOC_TOUCH_LOG.md` row "Frontend media-policy advisory boundary guard".

- [x] **Hardcoded server paths** — active audit and legacy GUI defaults no longer seed `\\LAYNE-SERVER\Video`; audit defaults derive from config source roots or fail clearly, with `Invoke-PortablePathChecks.ps1` guarding drift.

- [x] **Analytics state in source folder** — encode-speed history now lives under `LocalBase\State\App`; stale app-root state was archived and `Invoke-RuntimeStateHygieneChecks.ps1` guards drift. Source: `DOC_TOUCH_LOG.md` row "Runtime Analytics State-Root Hygiene".

- [x] **Unknown disk space should fail closed** — Reconciled as complete: `Test-DiskSpace` fails closed when free space is indeterminate, `Copy-FileRobocopy` refuses copy before robocopy/staging when destination free space is unknown, records `OUTPUT_DESTINATION_SPACE_UNKNOWN`, and publish completion parks verified local output as output-space deferred when possible. Source: `DOC_TOUCH_LOG.md` row "Unknown destination space fail-closed copy preflight" and current V6 reliability-wrapper coverage.

- [x] **Frontend readiness inference should move to backend DTOs** — Closed: `GET /api/launch/preflight` now publishes backend-authored `operator_readiness` (`desktop_launch_readiness.v1`) and the Launch readiness card/start-decision summary prefer that DTO; the old Launch inference is labelled frontend advisory fallback only. Diagnostics tail already returns backend `evidence_authority=backend` evidence and labels older/no-evidence text scans as frontend advisory only. Focused unit/static tests and the browser-backed Launch/Queue readiness smoke passed.

- [x] **Repo artifact cleanup** — root log/jsonl captures and DesktopApp root API validation captures are ignored/guarded; stale root desktop log was archived under ignored `RunLogs`; active DesktopApp live log remains deferred while processes may own it. Source: `DOC_TOUCH_LOG.md` row "Generated log hygiene guard".

- [x] **Wave B code cleanup — completed for current Python/PowerShell scope** — Config-key constants are complete for the Python desktop host and PowerShell pipeline: `test_config_keys.py` guards Python schema/network/PowerShell-order alignment plus Network runtime, settings/media-policy, and package-wide registered-key raw lookup drift; and `Invoke-ConfigKeyRegistryChecks.ps1` guards PowerShell registry/order, PSD1 known-key coverage, and literal PowerShell config-reference drift. Current Python package code no longer has raw registered-key config lookups for keys in `ALL_CONFIG_KEYS`; legacy sample-validation aliases (`OutsourcePath`, `ServerOut`, `OutputRoot`) are isolated as compatibility-only names. `FailureCodes.ps1` now exposes a 37-code classifier registry plus a 119-code broader outcome registry with family, stage, when-fires, retryability, operator severity, handler, and operator-action metadata guarded by `Invoke-FailureCodeRegistryChecks.ps1`. `service_runner_protocols.py` now types path/config/audit-rerun, process lifecycle, queue, rename, and status runner boundaries, and low-level process logger parameters use explicit logger Protocols. Application facade/DTO boundary modules now declare literal `__all__` lists guarded by `test_application_public_api.py`. A desktop-app scan no longer finds `service: Any`, `_service: Any`, `logger: Any`, or `run_capture_func: Any` signatures. JS namespace tiering remains deferred to the separate namespace/JSDoc/dead-export cleanup stream. Source: `Docs/DOC_TOUCH_LOG.md`, `Docs/REMEDIATION_CHANGELOG.md`, and the focused config/failure/protocol guard tests.

- [x] **Adversarial force-kill during encode test** — Closed with `Pipeline\Tests\Invoke-AdversarialForceKillEncodeChecks.ps1`: generated-media backend `-Once` run reaches CPU fallback encode, a byte-bearing `encode_temp_cpu_*.mkv` is observed, the PowerShell/FFmpeg process tree is force-killed, source hash is unchanged, no Outsource/local encoded/completed-manifest/pending-publish artifact is accepted, and the source remains in a backend-authored queue plan. Source: `V5_MIGRATION_RISK_REGISTER.md` R-001.

- [x] **Settings raw-only high-priority keys** — `BdpgsOcrToolPath` and `BdpgsOcrTessdataPath` are now covered by the Subtitle Settings builder as staged text fields. The WebView still does not browse or resolve arbitrary paths; backend Preview/Save plus saved path evidence remain authoritative. Source: `SETTINGS_RAW_KEY_TRIAGE.md`.

---

## Low — Acknowledged Deferred / Improvement Backlog

- [x] **Wave C code cleanup — finite checklist scope closed** — Namespace object boundary comments are in place for all 29 `window.mediaPipeline* = { ... }` objects and guarded by `test_webview_inventory_docs.py`; the dead-export audit plus nine high-confidence flat-export removal chunks are complete, leaving 756 generated flat compatibility exports; completed god-file split waves now have focused child tests while parent facade/controller files serve fixture/import-boundary roles; and logging convention is complete. Remaining per-member JSDoc and medium-confidence flat-export decisions are intentionally opportunistic per touched module, not a standalone bulk cleanup mandate. No UI/backend/media behavior changed. Source: `Docs/audits/DEAD_EXPORT_AUDIT_2026-05-19.md`, `Docs/architecture/LOGGING_CONVENTION.md`, `Docs/DOC_TOUCH_LOG.md`, and `Docs/REMEDIATION_CHANGELOG.md`.

- [x] **Test god-file splits (Wave 5)** — Wave 5 test-file splits are complete; `test_application_facade.py` and `test_controllers.py` are now shared fixture/import-boundary modules with focused child test files. Full split history is quarantined at `Docs\archive\docs-housekeeping\2026-05-20-review\archive-historical\Docs\archive\completed-checklists\GOD_FILE_SPLIT_PLAN.md`.

- [x] **Tauri production-hardening lifecycle** — Closed on 2026-05-19 for the V5 preview shell: spawn/bootstrap resilience remains bounded, Tauri now emits backend health/crash lifecycle events, WebView renders a visible read-only recovery banner through an event-only Tauri bridge, a per-user Windows mutex rejects second Tauri shell instances before backend startup, ActiveJobs orphan reconciliation remains backend-owned and guarded, and `Test-TauriShell-ProductionSurface.ps1` checks no production devtools flags, no token-adjacent runtime logging, one dynamic main window, the single-instance guard, and event-only bridge posture. This does not prove PG-3 clean-machine launch; representative real-media validation was later closed by operator attestation on 2026-05-28. Source: `TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`.

- [x] **Network page lifecycle controls** — Closed as a backend-contract gate, not as WebView buttons. WebView Network remains read-only; `/api/contract` now publishes design-only Network lifecycle contracts for coordinator start, coordinator stop, and worker polling lifecycle, `Docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` records the dry-run/cleanup/journal/source-policy gates, and static/API tests prove no Network lifecycle POST route or WebView control is exposed yet. Future controls still require backend dry-run routes, command journaling, cleanup/orphan tests, browser no-mutation coverage, and inventory updates.

- [x] **Repair/reconcile mutation contract** — Completed/Pending repair/reconcile remains design-only, but `/api/contract` now defines explicit dry-run, rollback, source-file, and route-exposure gates before any backend mutation route or WebView control can be added. Source: `Docs/architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md` + archived active-fix evidence.

- [x] **Settings builder for remaining raw-only keys** — `SubSDHTitleKeywords` and `SubSupplementalKeywords` are now covered by the Subtitle Settings builder as staged list fields. The WebView only stages list text; backend Preview/Save and backend subtitle classification remain authoritative. Auth tokens remain intentionally hidden. Source: `SETTINGS_RAW_KEY_TRIAGE.md`.

- [x] **Active docs consolidation** — Closed on 2026-05-20. `Docs/CURRENT_PROJECT_STATE.md` is the single current-state source, root `OPEN_WORK_CHECKLIST.md` is the single active checklist, and the prior active-fix checklist, Tauri transition current plan, transition status board, and transition-review fix checklist bodies were quarantined under `Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/historical-plans/` with compatibility redirect stubs left at their old paths. Source: archived housekeeping evidence.

- [x] **UI improvement backlog** — Closed on 2026-05-20 for the active 23-item low-priority backlog. State-aware Launch controls, emergency topbar Force Stop, progress/status handling, WebView root-cause summaries, telemetry render diagnostics, status-chip/tooltips, and layout decisions are recorded in `Docs/DOC_TOUCH_LOG.md` and `Docs/REMEDIATION_CHANGELOG.md`; no active standalone UI-improvement checklist remains in `Docs/ui/`.

- [x] **Layout manager edge cases** — Closed on 2026-05-20. Stored page order now resets to authored default order when a page's panel-key set changes, so newly added panels are no longer appended below every stored panel; dragging an advanced-gated panel now shows a transient "Still gated" hint in the customize bar. Source: `Docs/DOC_TOUCH_LOG.md`, `Docs/REMEDIATION_CHANGELOG.md`, and guarded WebView layout-manager tests.

- [x] **Housekeeping report archival** — Superseded housekeeping reports and delete candidates were quarantined under `Docs\archive\docs-housekeeping\2026-05-20-review\`; active handoff guidance now lives in `README.md`, `AGENTS.md`, `Docs\CURRENT_PROJECT_STATE.md`, and `Docs\DOCS_INDEX.md`.

---

## Summary Count

| Priority | Open Count |
|---|---:|
| P0 — Blocker | 1 |
| High | 1 |
| Medium | 0 |
| Low | 0 |
| **Total Open** | **2** |
