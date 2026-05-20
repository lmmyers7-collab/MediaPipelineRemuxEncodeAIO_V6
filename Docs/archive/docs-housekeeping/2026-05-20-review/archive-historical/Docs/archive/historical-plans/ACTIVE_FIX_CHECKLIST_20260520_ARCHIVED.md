# Active Fix Checklist

Last updated: 2026-05-20

This checklist contains unresolved or partially resolved work only. Completed historical task lists belong in `ARCHIVED_MD_INDEX.md` or the full `REMEDIATION_CHANGELOG.md`.

## Critical

- [ ] **Real-media validation before WebView daily-driver claims**
  - Area: Tauri/WebView2 transition, queue, launch, completed, diagnostics, pending publish.
  - Task: run the `V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` flow against a small known media set and capture evidence using `REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`.
  - Progress: PG-2 now has a queue-backed accepted evidence anchor from the post-fix Trigun S01E05 Tauri/WebView run plus operator playback/subtitle/audio acceptance for Spy x Family S01E10 and Trigun S01E03/S01E04/S01E05. A 2026-05-18 follow-up planning worksheet exists at `Docs/RealMediaValidationRuns/real_media_validation_20260518_transition_followup_plan.md` with planned categories only. This does not close the broader daily-driver item because PG-3 clean-machine proof, representative category coverage, current accepted-record reconciliation, and actual selected-sample execution remain separate gates.
  - Success: WebView evidence matches actual pipeline outcomes for route, encode/remux decision, output size, subtitles/audio, completed manifest, diagnostics, and pending publish behavior.

- [ ] **Preserve Tk fallback during every transition step**
  - Area: desktop app launch, backend services, packaging.
  - Task: keep `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat` operational and avoid WebView-only assumptions in shared backend code.
  - Progress: 2026-05-18 source/dev promotion-gate recheck passed for current V5/Tk posture: contract schema checks, full unskipped release self-test with bundled tool integration and temp end-to-end smoke, bundled Python `unittest`/`pytest`, browser no-mutation smoke suite, Tauri `-CheckOnly`, and Tauri build gate. A fresh current-handoff package named `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` passed copied-bundle package-mode Tauri launch/close locally, but clean-machine PG-3 and broader real-media validation remain separate gates; future validation should use the copied/built package on the target machine, not the original local path.
  - Progress: 2026-05-18 added a static launcher regression to `test_app_bootstrap.py` that verifies the root desktop launcher still delegates to `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-DesktopApp.bat`, the desktop launcher still imports `customtkinter`, prefers bundled Python runtimes, supports console diagnostics, ignores Windows Store aliases, and does not drift into Tauri/local-API-only startup.
  - Success: Tk still launches after WebView/Tauri changes and remains the supported fallback.

- [ ] **Do not add frontend-owned mutation**
  - Area: WebView frontend, local API commands, rename, pending publish, settings.
  - Task: ensure every mutation control posts to backend-owned command routes and backend independently validates scope.
  - Progress: 2026-05-18 added `test_webview_frontend_mutation_boundary.py`, a static gate over WebView assets that fails undocumented/nonliteral `apiPost` calls, wrong owner modules for command routes, raw path keys in shell-open payloads, missing confirmation payloads for write routes, direct `fetch` outside `apiClient.js`, and direct frontend filesystem/process/Tauri API use.
  - Progress: 2026-05-18 added a Local API contract assertion that all effectful POST routes keep `desktop_command_result.v1` responses for operator command-history evidence; only preview-only `/api/rename/preview` and `/api/sample-validation/preview` may use non-command preview schemas.
  - Success: no WebView code directly renames files, writes config, drains publish, modifies queue state, starts pipeline outside route contracts, or edits source/output/scratch.

- [ ] **Protect pending publish and source safety**
  - Area: PowerShell publish modules, Python API, WebView Pending Publish.
  - Task: keep manifest, sidecar, drain, orphan payload, missing payload, and do-not-drain behavior backend-owned and evidence-rich.
  - Progress: 2026-05-18 corrected Rename's read-only pipeline handoff to display the canonical `DeleteSourceAfterProcessing` saved setting instead of stale `DeleteOriginalAfterProcessing`; static WebView tests now reject the stale key in `renameView.js`.
  - Progress: 2026-05-18 added a settings risk-policy unit gate that reads `Pipeline\MediaPipeline_config_template.psd1` and fails if the clean template enables source mutation, system-tool fallback, skipped stability checks, disabled integrity checks, remote staging cleanup, or reprocess-all defaults.
  - Progress: 2026-05-18 added a Local API contract assertion that `/api/rerun/start` continues to advertise conservative copy/keep/park defaults (`dry_run=false`, `stage_mode=copy`, `original_mode=keep`, `return_mode=park`) in the backend-published route contract.
  - Progress: 2026-05-19 added focused Pending Publish PowerShell guardrail coverage for media-plus-sidecar parking, missing-payload manifest persistence, weak already-published proof rejection, pending sidecar rollback, and low-space deferred-publish classification; fixed ordered transaction property lookup and sidecar rollback restore behavior.
  - Progress: 2026-05-19 added a pending-publish ownership guard over `MODULE_MAP.md`, the fixture inventory, and the publish/pending PowerShell modules so parked output remains documented and tested as media plus sidecars and drain safety stays backend-owned.
  - Success: no job is presented as safely published unless final output or parked manifest evidence proves it.

## High

- [ ] **Complete WebView daily-use parity without removing safety boundaries**
  - Area: Home, Queue, Launch, Completed, Pending Publish, Rename, Settings, Diagnostics.
  - Task: continue parity improvements from `TAURI_WEBVIEW_PARITY_MATRIX.md`, prioritizing operator trust, clear command results, row details, empty states, and real backend evidence.
  - Progress: Launch now has a read-only Pilot Run Readiness panel that ties selected Queue sample, saved Settings policy, backend preflight, pilot category coverage, real-media proof plan, sample execution checklist, Pending Publish posture, post-run proof plan, and mutation boundary together before a real-media pilot.
  - Progress: Completed now has a read-only Selected Pilot Evidence Packet that turns the selected Completed row into a copyable post-run checklist covering output/sidecar proof, route/size/audio/subtitle evidence, Pending Publish/final-placement proof, Diagnostics/runtime context, Sample Validation readiness, manual playback checks, and mutation boundaries.
  - Progress: Completed now also has read-only saved-policy reconciliation inside the Real-Media Output Proof ladder and Selected Pilot Evidence Packet. It compares the selected completed row's route/size/audio/subtitle/final-placement evidence against the saved policy-alignment categories so Launch pre-run route hints can be checked against post-run output proof.
  - Progress: Home Sample Validation now has a read-only Completed Evidence Handoff that mirrors the selected Completed packet before Preview/Append so post-run proof, saved-policy reconciliation, Pending Publish/final placement, Diagnostics/runtime evidence, manual playback, subtitle/audio checks, and size posture can be compared without adding mutation authority.
  - Progress: Home Sample Validation now has a read-only Acceptance Readiness Gate that exposes accepted-evidence blockers/review items from selected sample proof, checklist coverage, Completed packet posture, backend validation state, manual media checks, and backend-only mutation boundaries before Preview/Append.
  - Progress: Home Sample Validation now has a read-only Accepted Record Proof Review that compares current/accepted records against Completed output/sidecar, size, subtitle/audio, Diagnostics, Pending Publish/final placement, and reconciliation evidence.
  - Progress: Home Sample Validation now has a read-only Pilot Category Validation Summary that groups the five real-media pilot categories by current accepted evidence, worksheet-only planning evidence, historical accepted records, stale/review records, and missing/planned coverage.
  - Progress: `/api/sample-validation` now includes a backend-authored read-only Real-Media Validation Audit roll-up. Home Sample Validation shows one conservative posture over readiness, reconciliation, generated worksheets, sample-set coverage, evidence gaps, pilot runbook, and cutover gate evidence without adding launch, append, accept, publish/drain, repair, settings, rename, manifest, or media mutation authority.
  - Progress: `/api/sample-validation` now also includes a backend-authored read-only Real-Media Policy Alignment roll-up. It maps saved Settings media-policy readiness onto the required pilot categories for H.264 remux, subtitle-to-SRT, audio routing, encode/size policy, and deferred publish so unsafe saved policy is visible before a pilot run.
  - Progress: Launch now compares the selected/representative Queue route against that saved-policy alignment inside the Real-Media Sample Proof Handoff and Pilot Run Readiness panels. The comparison is evidence-only, explicitly advisory, and highlights when Queue route text is too thin to prove subtitle/audio/size/deferred-publish policy before Start.
  - Progress: Diagnostics First Response rows are now selectable and expose detail explaining why each gate matters, what evidence was used, which owner surface to inspect next, and the read-only mutation boundary before repeating commands.
  - Progress: Diagnostics First Response now includes `Sample Validation policy reconciliation`, which routes saved-policy alignment review gaps back to Home Sample Validation, Completed saved-policy reconciliation, and Settings media policy without adding mutation authority.
  - Progress: Queue Launch Decision, Completed Output Acceptance, and Pending Publish Drain Decision summaries now start with explicit daily-use handoff language, operator outcome, and scope boundaries so filtered/selected rows cannot be mistaken for backend launch, output-acceptance, or drain scope.
  - Success: operator can understand what will happen before launch/drain/save/apply without needing to inspect logs manually.

- [ ] **Keep Network mode read-only until lifecycle ownership is designed and tested**
  - Area: Network page, backend coordinator/worker state, Tauri lifecycle.
  - Task: expose safe read-only coordinator/worker state only. Do not add start/stop controls until backend contracts, auth, tests, and failure recovery exist.
  - Progress: WebView Network now has a read-only Lifecycle Handoff that ties close-readiness, role/auth/path-map config, persisted worker claims, pending done reports, state-file metadata, diagnostics route availability, and future promotion requirements together before any operator trusts distributed work or expects WebView lifecycle controls.
  - Success: Network page cannot mutate coordinator or worker lifecycle.

- [ ] **Improve real output-size validation evidence**
  - Area: remux/encode policy, size guard, completed output review.
  - Task: validate size-growth guard behavior against real examples, including low-bitrate H.264 sources that should remux/copy by default unless policy requires encode.
  - Progress: Completed preview/WebView now exposes recorded backend `size_policy` evidence from completed sidecars, including actual mode, routing profile, applicable growth limit, exceeded/enforced status, and message. Compatibility growth above the legacy +5% line is no longer treated as a blocker when the backend recorded it as within the applicable size policy.
  - Remaining: run real samples and compare sidecar `size_policy`, Completed rows, Diagnostics logs, and actual output sizes.
  - Success: Completed/Diagnostics explain when an encode grew beyond configured thresholds and whether it was allowed, rejected, or needs review.

- [x] **Reconcile active Claude handoff files**
  - Area: documentation hygiene.
  - Task: decide whether the three `CLAUDE_HANDOFF_TRANSITION_SUPPORT_*` docs are closed, active, or partially merged.
  - Completed 2026-05-15: All three docs confirmed closed; moved to `Docs/archive/old-ai-directives/`; `DOCS_INDEX.md` and `ARCHIVED_MD_INDEX.md` updated to reflect archive paths.
  - Success: no future agent treats stale Claude task lists as current marching orders.

## Medium

- [x] **Promote config glossary from draft**
  - Area: settings/config docs.
  - Task: reconcile `CONFIG_KEY_GLOSSARY_DRAFT.md` with `SETTINGS_KEY_OWNERSHIP_MAP.md` and structured builder coverage.
  - Completed 2026-05-15: Added missing keys (`CreateTVSubfolder`, `MkvmergeRemuxTimeoutSeconds`, `ConsoleLogLevel`, `FileLogLevel`, `SubSDHTitleKeywords`, `SubSupplementalKeywords`, `WorkerSourcePathMap`, `WorkerConfigOverrides`); draft renamed to `CONFIG_KEY_GLOSSARY.md`; `DOCS_INDEX.md` updated.
  - Success: there is one trusted glossary for high-impact settings and raw/hidden keys.

- [x] **Resolve settings raw-key follow-ups**
  - Area: Settings WebView, backend config.
  - Task: use `SETTINGS_BUILDER_COVERAGE_MATRIX.md` and `SETTINGS_RAW_KEY_TRIAGE.md` to decide which raw-only keys need builders, which should stay hidden, and which need warnings only.
  - Progress: BDPGS OCR tool/tessdata keys now have backend-authored read-only path evidence in `/api/settings/workspace` and structured WebView Subtitle builder text fields. Path editing remains backend Preview/Save owned; no WebView path picker was added.
  - Progress: Diagnostics State Artifact Summary now surfaces blocked/review BDPGS OCR path evidence from saved backend config when OCR is enabled, so subtitle-OCR path blockers appear in Diagnostics read order without adding mutation or arbitrary path reads.
  - Progress: WebView Settings now includes a read-only Raw-Key Action Plan that separates schema drift, OCR path evidence, subtitle keyword builder coverage, intentionally excluded auth secrets, remaining advanced raw keys, and backend-owned mutation boundaries.
  - Progress: Home External Dependency Digest and Diagnostics First Response now include loaded Raw-Key Action Plan posture, making schema drift/high-review raw-key issues visible during run triage without adding settings-save or media mutation.
  - Completed 2026-05-19: `BdpgsOcrToolPath` and `BdpgsOcrTessdataPath` moved from raw-only follow-up to the Subtitle builder as staged text fields, while saved path evidence remains backend-authored.
  - Completed 2026-05-19: `SubSDHTitleKeywords` and `SubSupplementalKeywords` moved from raw-only follow-up to the Subtitle builder as staged list fields, while backend subtitle classification remains authoritative.
  - Success: non-secret settings are structured; raw JSON remains reserved for advanced/manual cases and intentionally hidden auth secrets.

- [x] **Code-management Wave B cleanup**
  - Area: Python desktop host, PowerShell classifier helpers, docs/tests.
  - Task: continue `CODE_MANAGEMENT_CLEANUP_PLAN.md` Wave B by turning duplicated high-risk string registries into owned, testable constants before broader refactors.
  - Progress: 2026-05-19 added `DesktopApp\mediapipeline_desktop_app\config_keys.py`, migrated first path/numeric safety call sites to those constants, and added `DesktopApp\tests\test_config_keys.py` to guard Python schema keys, network defaults, and PowerShell config-key order.
  - Progress: 2026-05-19 added `Pipeline\Modules\ConfigKeys.ps1` and `Pipeline\Tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1` to guard PowerShell config-key order, template/live PSD1 known-key coverage, and literal PowerShell config-reference drift.
  - Progress: 2026-05-19 added classifier-code registry helpers in `Pipeline\Modules\FailureCodes.ps1` and `Pipeline\Tests\Unit\Invoke-FailureCodeRegistryChecks.ps1` so failure classifiers cannot return undocumented codes silently.
  - Progress: 2026-05-19 expanded `FailureCodes.ps1` with a broader outcome-code registry and expanded `Invoke-FailureCodeRegistryChecks.ps1` so emitted PowerShell outcome/error codes must be known before they drift into failure markers, process results, or runtime evidence.
  - Progress: 2026-05-19 added `service_runner_protocols.py` and applied the first explicit Protocol contracts to path resolution, PowerShell-host resolution, app-state migration, config document/save, and audit/rerun metadata/export helper runners, replacing unbounded `service: Any`/`run_capture_func: Any` on those load-bearing boundaries.
  - Progress: 2026-05-19 applied explicit Protocol contracts to process control, ActiveJobs, launch, runtime cleanup, and spawn helper runners, replacing the remaining load-bearing `service: Any` signatures in the process lifecycle runner layer while leaving JSON payload types flexible.
  - Progress: 2026-05-19 applied explicit Protocol contracts to queue preview/dry-run, rename preview/planning/apply, and status reader/snapshot helpers, replacing the remaining load-bearing `service: Any` signatures in those runner layers.
  - Progress: 2026-05-19 replaced low-level process helper `logger: Any` annotations with explicit logger Protocols and confirmed a desktop-app scan no longer finds `service: Any`, `_service: Any`, `logger: Any`, or `run_capture_func: Any` signatures.
  - Progress: 2026-05-19 migrated Network coordinator/worker runtime config lookups to named constants for role, auth, port/bind/heartbeat, worker URL/name/poll/path-map, worker encode overrides, and encode snapshot keys; `test_config_keys.py` now blocks those raw `.get("...")` lookups from returning.
  - Progress: 2026-05-19 migrated settings/media-policy evidence, sample-validation policy posture, telemetry encoder display, completed/audit outsource-root access, and valid-extension layout to named config constants; `test_config_keys.py` now blocks those raw registered-key lookups from returning.
  - Progress: 2026-05-19 closed the practical config-key workstream by adding a package-wide registered-key raw-lookup guard; current Python package code no longer has raw `.get("CurrentConfigKey")`, `values["CurrentConfigKey"]`, or helper-value calls for keys in `ALL_CONFIG_KEYS`.
  - Progress: 2026-05-19 expanded failure/outcome registry rows with derived family, stage, when-fires, retryability, operator severity, handler, and operator-action metadata; `Invoke-FailureCodeRegistryChecks.ps1` now guards metadata completeness, representative high-risk rows, and fail-closed metadata lookups.
  - Progress: 2026-05-19 added literal `__all__` declarations to application facade/DTO boundary modules and added `test_application_public_api.py` to guard package exports, per-module export uniqueness/completeness, and importability.
  - Remaining: JS namespace tiering is intentionally deferred to the namespace/JSDoc/dead-export cleanup stream.
  - Success: future config, failure-code, or Python facade boundary edits fail focused tests before they drift from backend-owned contracts.

- [x] **Define repair/reconcile dry-run and rollback contracts before mutation**
  - Area: Completed, Pending Publish, maintenance.
  - Task: if repair controls are needed later, implement backend dry-run diff commands first, then atomic write/journal-backed mutation commands with explicit operator confirmation.
  - Boundary: `/api/contract` now publishes design-only repair/reconcile contracts with `mutation_enabled=false` and `frontend_allowed=false`; WebView may display those boundaries but must not repair/reconcile from frontend logic.
  - Progress: 2026-05-18 expanded `test_webview_frontend_mutation_boundary.py` so repair/reconcile remains design-only and not WebView-callable: no POST route path may expose repair/reconcile/reconciliation, the only reconciliation route remains GET/effect none, no `apiPost` call can target repair/reconcile, and the Contract page must keep the dry-run/atomic-journal/rollback guardrail text.
  - Progress: 2026-05-19 added explicit design-only `dry_run_contract`, `rollback_contract`, `source_file_policy`, and `route_exposure_gates` fields to every repair/reconcile contract; added `Docs/architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md`; tests now require dry-run-only schema fields, rollback journal fields, source media immutability, and no repair/reconcile POST route exposure.
  - Success: future repair/reconcile implementation is gated behind tested backend dry-run routes, preconditions, backup/rollback evidence, command journal records, inventory/doc updates, and only then WebView controls. No mutation route or WebView repair control exists yet.

- [ ] **Keep frontend module cohesion under control**
  - Area: WebView JavaScript.
  - Task: follow `FRONTEND_MODULE_SIZE_COHESION_REPORT.md` policy: do not split files only for size, but extract cohesive components when a real change makes a file harder to reason about.
  - Progress: 2026-05-19 completed the planned god-file split waves through Wave 6; remaining command-adjacent Queue priority/strategy/file-overrides behavior intentionally stays in the parent Queue module.
  - Progress: 2026-05-19 removed broad test-only/runtime-unreferenced direct WebView flat exports while preserving canonical `window.mediaPipeline*` namespace objects; flat export total is now 756 across 64 files.
  - Progress: 2026-05-19 added adjacent `Public namespace` boundary comments to all 29 primary `window.mediaPipeline* = { ... }` namespace objects and guarded future namespace exports in `test_webview_inventory_docs.py`.
  - Progress: 2026-05-20 closed the finite Wave C checklist scope: namespace boundary guards, dead-export audit/high-confidence removals, completed split test mapping, and logging convention are documented as complete; remaining member JSDoc and medium-confidence export removals are maintenance guardrails per touched module.
  - Success: no architecture-astronaut pass-through modules; no god-file growth without ownership clarity.

## Low

- [ ] **Manual operator docs polish**
  - Area: operator-facing copy.
  - Task: keep `OPERATOR_GLOSSARY.md`, `TERMINOLOGY_CONSISTENCY_GUIDE.md`, and manual scripts aligned with new WebView text as features mature.
  - Success: operator wording stays consistent without repeated one-off audits.

- [ ] **UI idea triage**
  - Area: UI backlog.
  - Task: review `UI_IMPROVEMENT_CHECKLIST.md` and move desired items into this active checklist or archive the file.
  - Progress: 2026-05-19 status-labelled `Docs/ui/UI_IMPROVEMENT_CHECKLIST.md` as a low-priority future UI polish backlog, not a daily-driver promotion gate unless an item is copied here.
  - Success: future UI improvements are not split across old checklists.

## Recently Completed

- [x] **Wave C finite code-cleanup reconciliation (2026-05-20)** — Closed Wave C as a standalone open checklist item without changing runtime behavior: namespace boundary comments are guarded, high-confidence flat-export removals are complete, completed split tests have focused ownership, and remaining JSDoc/export cleanup is explicitly opportunistic per touched module.
- [x] **Tauri production-hardening lifecycle guardrails (2026-05-19)** — Tauri now emits backend health/crash lifecycle events, WebView renders an event-only read-only recovery banner, a per-user Windows mutex rejects second Tauri shell instances before backend startup, and `Test-TauriShell-ProductionSurface.ps1` audits no production devtools flags, no token-adjacent runtime logging, one dynamic main window, the single-instance guard, and bridge posture.
- [x] **Adversarial force-kill encode safety smoke (2026-05-19)** — `Pipeline\Tests\Invoke-AdversarialForceKillEncodeChecks.ps1` now force-kills a real generated-media backend encode after a byte-bearing CPU fallback temp output exists, verifies no completed/pending/published/local accepted output was written, preserves the source hash, and confirms the source remains backend-queued.
- [x] **Settings BDPGS OCR path builder (2026-05-19)** — `BdpgsOcrToolPath` and `BdpgsOcrTessdataPath` now stage through the Subtitle Settings builder while saved backend path evidence remains authoritative; backend config validation warns when OCR is enabled with a blank tool path; no frontend file picker/path resolver/OCR execution was added.
- [x] **Frontend readiness inference to backend DTOs (2026-05-19)** — `GET /api/launch/preflight` now publishes nested backend `operator_readiness` (`desktop_launch_readiness.v1`) and Launch readiness/Start Decision Summary prefer that DTO; the older Launch text scan remains advisory fallback only. Diagnostics tail already uses backend `evidence_authority=backend` evidence with advisory-only fallback wording.
- [x] **WebView UI command surface and page title compliance (2026-05-19)** — stale High UI rows are closed: Home/Dashboard no longer duplicates Launch/Pending Publish command controls, rendered panel types are limited to evidence/interactive, evidence panels remain button-free/read-only, and all 13 rendered page H1 titles match `V5_UI_DESIGN_REFERENCE.md`.
- [x] **Unknown destination space stale-row reconciliation (2026-05-19)** — `OPEN_WORK_CHECKLIST.md` now marks the unknown-space fail-closed row complete because `Disk.ps1`/`Copy-FileRobocopy` already refuse unknown destination free-space copies before robocopy/staging, record `OUTPUT_DESTINATION_SPACE_UNKNOWN`, and reliability coverage passed.
- [x] **Rename and duplicate-launch safety coverage (2026-05-19)** — backend rename planning now blocks every row in a duplicate-destination group, Local API `rename.apply` rejects absent/false `confirm_apply` without mutating the source file, and process-launch tests now prove a second pipeline start is rejected while the first bundle-owned child process is still running.
- [x] **Transition blocker reconciliation: lifecycle, queue priority, and reliability gates (2026-05-19)** — `OPEN_WORK_CHECKLIST.md` now marks the stale P0 rows closed after confirming backend shutdown fail-closed behavior, documented `GET/POST /api/queue/priority` contracts/source-scope journaling, and restored PowerShell reliability/deferred-publish smoke coverage. Focused lifecycle/route/contract/unit tests plus `Invoke-ReliabilityRegressionChecks.ps1` and `Invoke-EndToEndSmokeChecks.ps1` passed.
- [x] **God-file split campaign complete through Wave 6 (2026-05-19)** — all original production-code god files, HTML/CSS partial splits, large test-file splits, and safe JS child splits are complete; Queue command-adjacent priority/strategy/file-overrides paths intentionally remain parent-owned.
- [x] **WebView namespace-first flat-export cleanup (2026-05-19)** — removed test-only/runtime-unreferenced direct `window.*` aliases while preserving canonical namespace objects and inventory/static/browser smoke coverage.
- [x] **Pending publish safety guardrail tests and rollback fix (2026-05-19)** — added focused PowerShell safety checks and fixed ordered transaction lookup plus sidecar rollback restore behavior.
- [x] **Rename undo state-root safety cleanup (2026-05-19)** — new undo manifests prefer `State\RenameUndo` when service state/app root is available, including legacy app-state startup.
- [x] **Repo hygiene generated artifact cleanup (2026-05-19)** — removed rebuildable ignored `.pytest_cache` and Tauri Rust `src-tauri\target` output after path-boundary verification; archived the stale root `MediaPipelineRemuxEncodeAIO_DesktopApp.log` capture under ignored `RunLogs`; expanded `.gitignore` and `Invoke-RepoHygieneChecks.ps1` to catch root log/jsonl captures plus DesktopApp root API validation captures.
- [x] **Portable audit-root defaults cleanup (2026-05-19)** — active audit and legacy GUI scripts no longer seed `\\LAYNE-SERVER\Video`; audit defaults derive from config source roots or fail clearly, with `Invoke-PortablePathChecks.ps1` guarding drift.
- [x] **Frontend media-policy advisory boundary guard (2026-05-19)** — Settings/Launch frontend risk helpers are explicitly advisory-only, and mutation-boundary tests now require backend-authority wording for preview/save, launch validation, source-deletion policy, queue scope, route safety, publish/drain safety, and PSD1 writes.
- [x] **Runtime analytics state-root hygiene (2026-05-19)** — stale app-root `DesktopApp\encode_speed_history.json` was archived under ignored RunLogs after confirming the live `LocalBase\State\App` copy exists; `.gitignore`, runtime artifact inventory, and `Invoke-RuntimeStateHygieneChecks.ps1` now guard against return.
- [x] **Active docs reference hygiene (2026-05-19)** — non-archive docs now point to the post-reorg source-of-truth paths for inventories, runbooks, operator guides, active plans, and archived audit references; superseded housekeeping reports were moved under `Docs\archive\admin-audits`; `Invoke-ActiveDocsReferenceChecks.ps1` guards those moved-root references and root-level housekeeping report name drift.
- [x] **High-level current-handoff path hygiene (2026-05-19)** — current-state/status/deployability/checklist docs now describe `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` as transfer evidence by package name rather than embedding the original local build path; `Invoke-ActiveDocsReferenceChecks.ps1` guards this high-level path drift.
- [x] **V5 UI Stage 14: Diagnostics Page Tab Navigation** — Diagnostics panel sectioned into tabbed sub-pages (Overview / State / Lifecycle / Targets / Logs). Tab nav wired in `app.js`; index.html panel groupings updated; all Diagnostics-page JS and state preserved.
- [x] **V5 UI Stage 15: Light Mode Toggle + Colour System** — `body.light-mode` CSS overrides added to `styles.css`; `initThemeToggle()` added to `app.js` to persist choice in `localStorage`; top-bar toggle button wired in `index.html`; `telemetryView.js` canvas renderer respects the `light-mode` class on each repaint.
- [x] **V5 UI Stage 16: UI Design Reference Audit (7 spec gaps closed)** — `styles.css` and `index.html` updated: disabled-button opacity removed (colour-change approach used instead); panel heading size/case/tracking corrected; data-status row backgrounds added (schedule-scoped to avoid Queue/Rename cross-contamination); `.num` tabular-numeral class added to numeric `<th>` headers; form label weight/size corrected; input inset shadow added; `.note` max-width capped. Tracking doc at `archive/completed-audits/STAGE16_UI_REF_AUDIT.md`.
- [x] **Docs folder restructure (2026-05-17)** — 60+ Markdown files sorted into topic subfolders (`inventories/`, `testing/`, `operator/`, `architecture/`, `sample-validation/`, `ui/`, `active-plans/`) plus two new archive sub-folders (`archive/completed-audits/`, `archive/ui-impl-specs/`). `DOCS_INDEX.md` fully rewritten. `ARCHIVED_MD_INDEX.md` updated.
- [x] WebView selected-row scroll stability fixed for Home, Completed, and Launch.
- [x] Effective policy trust surfaced in Settings.
- [x] Backend-owned diagnostics tail/open allowlist surfaced in WebView.
- [x] WebView smoke mutation-boundary documentation expanded.
- [x] Markdown cleanup audit created.
- [x] Smoke wrappers moved from repository root into `SmokeTests/` and inventoried in `inventories/SMOKE_TEST_INVENTORY.md`.
- [x] Completed/archive-classified Markdown files moved into `Docs/archive/` and indexed in `ARCHIVED_MD_INDEX.md`.
- [x] V4/V5 feature-outline wording reconciled in `Docs/DesktopApp/docs/FEATURE_OUTLINE_AND_SOFTWARE_COMPARISON.md`.
- [x] Docs source-of-truth adoption completed with `AI_AGENT_START_HERE.md`, `CURRENT_PROJECT_STATE.md`, `ACTIVE_FIX_CHECKLIST.md`, `DOCS_INDEX.md`, and `TLDR.md` as the active onboarding path.
- [x] Vendor/generated Markdown cleanup decision recorded: `node_modules/` remains for immediate Tauri preview work, but `.rgignore` excludes it from normal project docs/search inventory.
- [x] Changelog navigation added to `Docs/REMEDIATION_CHANGELOG.md` with current-doc warning, date bands, subsystem search terms, and command examples.
- [x] Completed output-size evidence now surfaces recorded backend `size_policy` fields so WebView distinguishes compatibility growth within policy from actual exceeded/advisory/blocked size-guard rows.
- [x] Backend-owned repair/reconcile command boundaries are now published in `/api/contract` as design-only contracts and rendered in WebView API Contract safety review with mutation disabled.
- [x] Completed Selected Pilot Evidence Packet added as read-only copyable post-run evidence for selected Completed rows.
- [x] Stale product-version labels resolved: `Versioning.ps1`, audit default, contract fixtures, and reliability-note header now align with V5/v5.000 while V4 fallback references remain intentional.
- [x] Fresh PG-3 current-handoff package built on 2026-05-18 with packaged Tauri preview binary; copied-bundle package-mode launch/close passed locally, and the local boundary report correctly keeps PG-3 open because developer tools were present on the development workstation.

## Required Test References

- `testing/VALIDATION_LADDER_RUNBOOK.md`
- `testing/TEST_COVERAGE_MATRIX.md`
- `inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md`
- `testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- `testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
- `sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
