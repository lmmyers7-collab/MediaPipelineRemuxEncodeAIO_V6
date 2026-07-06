# Right-Sized Safety Protocol Audit - 2026-07-03

Change packet: `MP-CHANGE-2026-0703-005`

Scope: backend, WebView/Tauri, PowerShell pipeline, config, docs, and tests. This is an audit-only report. It does not authorize implementation changes.

Evidence base:

- Required orientation docs: `AGENTS.md`, `docs/DOCS_INDEX.md`, `docs/architecture/ARCHITECTURE.md`, `docs/architecture/MODULE_MAP.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/testing/VALIDATION_LADDER_RUNBOOK.md`, `docs/CURRENT_PROJECT_STATE.md`, and `docs/OPEN_WORK_CHECKLIST.md`.
- Generated navigation: `docs/generated/PROJECT_INDEX.md`, `docs/generated/FEATURE_FILE_MAP.md`, `docs/generated/PIPELINE_MAP.md`, `docs/generated/DEPENDENCY_GRAPH.md`, and selected generated summaries under `docs/generated/summaries/`.
- Source evidence from representative backend, WebView, Tauri, PowerShell, config, docs, and tests listed below.

## 1. Executive Summary

### Main sources of excessive friction

1. Read-only WebView evidence panels repeatedly use mutation-level language: "blocked", "do not drain", "mutation guardrail", "cannot mutate", "first action", and "backend remains authoritative" appear across Pending Publish, Completed, Launch, Settings, Rename, Diagnostics, Sample Validation, and Network views. The risk is usually real at the system level, but many individual panels are read-only and already covered by backend route ownership and tests. This creates review fatigue without adding a new control.
2. Pending Publish stacks multiple frontend drain gates on top of required backend manifest/drain validation: backend drain scope preview, confidence DTO, decision checklist, button guard, filter-scope warnings, recovery dry-run handoff, command-history evidence, and a browser `confirm()`. The backend drain model is required, but the local WebView block for "evidence incomplete" or "not evaluated" can hard-stop a normal drain before the backend can make the authoritative decision.
3. Launch readiness and sample-validation proof handoffs sometimes treat missing proof or stale evidence like a launch blocker even when the operation is normal Start Pipeline and the backend start route still owns duplicate launch, active work, path health, mode validation, network-role blocks, and config identity. Evidence gaps should usually be review notes, not hard stops.
4. Settings and Launch risk handoff surfaces duplicate backend settings validation and policy readiness in several places. The backend preview/save confirmation and launch preflight are the right controls; repeated frontend "blocked" labels on read-only or staged evidence are candidates to simplify.
5. Tests and smoke catalogs enforce large amounts of boundary wording. These are valuable for mutation boundaries, but some assertions lock in redundant explanatory copy rather than the actual safety property: no mutation route is called, no source/output/scratch path is touched, and backend confirmation is required.

### Controls that are clearly justified

These should stay: source no-delete, scratch isolation, manifest-backed pending publish, subtitle preservation/default review-on-failure, audio/profile ownership, strict backend confirmations for real mutations, command journal, duplicate-command/process locks, close-readiness/shutdown blockers, backend route ownership, configured-root path authority, pending manifest trust checks, repair/reconcile dry-run fingerprints, rename selected-source apply, and network lifecycle provider/precondition guards.

### Controls likely eligible to simplify or cut

Likely low-risk simplifications are mostly frontend/docs/tests:

- Replace repeated "mutation guardrail" paragraphs in read-only panels with a shared concise boundary cue.
- Demote read-only proof/evidence gaps from "blocked" to "review" unless they map to a backend route rejection.
- Consolidate duplicate browser confirmations around Settings save, Pending drain, Rename apply, and Final Library Promotion where backend strict confirmation plus a single operator review already covers the mutation.
- Loosen tests that assert exact safety prose, while preserving tests that assert no mutation POSTs, strict confirmations, no source/output/scratch writes, and backend ownership.

## 2. Safety Control Inventory

| ID | Location | Layer | Workflow affected | Trigger condition | Operator-visible behavior | Risk protected against | Risk status | Existing lower-level controls | Blocking level | Invariant? | Need level | Cut eligibility | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SC-001 | `AGENTS.md`; `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`; config metadata | docs/config | All media workflows | Any source delete/overwrite/rename proposal | Source deletion treated as forbidden unless explicitly enabled by a named safe-delete policy | Irreversible source loss | Real | Backend/pipeline normal flow copies to scratch; no normal source delete route | hard-stop | yes | required | keep | Do not weaken. |
| SC-002 | `ops/pipeline/engine/*`; `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` | PowerShell | Processing | Source selected for processing | Source is copied to scratch; processing uses scratch input | Source corruption from partial transcode/remux | Real | Scratch copy, scratch fingerprints, publish from local output | hard-stop for direct source processing | yes | required | keep | Do not weaken. |
| SC-003 | `docs/generated/PIPELINE_MAP.md`; `src/mediapipeline/contracts/stage_mutation.py` | contracts/backend | Stage execution | Mutation stage requested | Only guarded `ingest` is enabled; later mutation stages are modeled with strict confirms but disabled | Accidental execution of unfinished mutation stages | Real | Backend stage dispatcher and strict Pydantic payloads | hard-stop | yes | required | keep | Disabled mutation stages are a correct current-state guard. |
| SC-004 | `src/mediapipeline/contracts/api_commands.py`; `src/mediapipeline/contracts/stage_mutation.py` | local API/contracts | All mutation routes | Missing or non-boolean confirmation fields | Route rejects or returns warning/error command result | Accidental mutation from malformed or scripted request | Real | Route validation, command journal, backend service checks | hard-stop | yes | required | keep | Required by strict JSON confirmation invariant. |
| SC-005 | `src/mediapipeline/desktop/api/command_journal.py`; `src/mediapipeline/desktop/api/handler.py` | local API | Commands | POST command success/failure/validation failure | Command result is journaled with bounded evidence | Hidden failures, unaudited mutation attempts | Real | Journal persistence and handler fallback recording | none/low | yes | required | keep | Low operator friction, high value. |
| SC-006 | `src/mediapipeline/core/processes/guard_facade.py`; `src/mediapipeline/core/processes/pipeline_facade.py` | core backend | Launch/start | Process launch lock unavailable or active work detected | Start returns blocked/busy result | Duplicate pipeline starts and overlapping mutations | Real | Lock, active jobs, progress checks, related process checks | high | yes | required | keep | Correctly lower-stack. |
| SC-007 | `src/mediapipeline/core/processes/guard_policy.py`; `src/mediapipeline/core/api/commands_process.py`; `apps/desktop/tauri/src-tauri/src/backend_process.rs`; `apps/desktop/tauri/src-tauri/src/lib.rs` | core/Tauri | App close/backend shutdown | Active work, armed watcher, unavailable close-readiness, or unsafe snapshot | Close is blocked or requires explicit force confirmation | Killing active pipeline/audit/drain work and losing state | Real | Backend close-readiness DTO, Tauri close dialog, safe-only shutdown path | hard-stop | yes | required | keep | Snapshot-unavailable fail-closed may be noisy but is aligned with invariant. |
| SC-008 | `apps/desktop/tauri/src-tauri/src/single_instance_guard.rs` | Tauri | Shell launch | Second shell process starts | New shell exits with existing-instance message | Duplicate WebView/backend controllers | Real | OS mutex | hard-stop | implicit | useful | keep | Low friction; protects lifecycle confusion. |
| SC-009 | `src/mediapipeline/core/processes/preflight_facade.py`; `apps/desktop/webview/static/assets/launch/commandButtons.js` | core/WebView | Launch buttons | Backend preflight rows blocked/stale/missing | Buttons disabled or allowed depending command/gate | Bad launch mode, active work, invalid paths, network-role misuse | Real | Backend start route repeats authoritative checks | medium/high | yes for duplicate/active work | useful | simplify | Keep backend preflight. Frontend should hard-stop only on rows that map to backend route rejection. |
| SC-010 | `src/mediapipeline/core/config/settings_patch_policy.py`; `apps/desktop/webview/static/assets/settingsView.js` | backend/WebView | Settings save | Patch changes pending | Backend preview confirmation object required; browser review dialog opens; save posts `confirm_save=true` | Wrong settings persisted from stale preview or accidental click | Real | HMAC/digest review confirmation, strict `confirm_save`, backend save policy | high for save | yes for real mutation confirmation | required | keep/simplify UI | Backend confirmation should stay. Review UI can be streamlined. |
| SC-011 | `apps/desktop/webview/static/assets/settingsView.safetyLocks.js`; `src/mediapipeline/core/config/settings_risk_policy.py` | WebView/backend DTO | Settings risk display | Risk metadata or saved policy concerns | Safety lock/risk rows shown, often as blocked/review | Operator may save risky config without noticing | Real in some rows, redundant in read-only rows | Backend preview/save validation and launch preflight | low/medium | no except true source/audio/subtitle policy rows | useful/redundant mixed | simplify | Avoid "blocked" for read-only advisory metadata that does not block save/launch. |
| SC-012 | `src/mediapipeline/core/config/settings_risk_policy.py`; `src/mediapipeline/core/config/settings_risk_policy_rules.py` | core config | Launch media policy | Saved config has subtitle/audio/source-mutation contradictions | Launch risk rows show blocked/review/readiness guidance | Lossy subtitle/audio policy or source mutation | Real | PowerShell media policy, backend launch validation, strict config save | medium | yes for subtitle/audio/source mutation | required/useful | keep | Keep rows that map to actual invariant risk. |
| SC-013 | `apps/desktop/webview/static/assets/launchView.js`; `src/mediapipeline/core/processes/rerun_policy.py` | WebView/backend | CSV rerun | Live rerun requested; preview blocked; replacement/delete policies active | Preview is refreshed; blocked preview prevents start; browser confirm asks before live rerun | Final replacement, rerun scope mistakes, original deletion | Real | Backend rerun policy, strict replacement/original confirmation flags, process launch guard | high | yes for source/final mutation | keep | keep | Correctly cautious; only redundant copy can be simplified. |
| SC-014 | `src/mediapipeline/core/publish/*`; `ops/pipeline/engine/publish/pending_*.ps1`; `ops/pipeline/entrypoints/MediaPipeline.ps1` | core/PowerShell | Pending publish park/drain | Final output cannot be safely placed immediately or drain requested | Output parked with manifest; drain uses manifest trust checks and writes drain summary | Wrong final placement, payload/sidecar loss, hidden publish failure | Real | Pending manifests, trust checks, retry states, durable summary | hard-stop | yes | required | keep | Do not weaken. |
| SC-015 | `apps/desktop/webview/static/assets/pendingPublishView.confidence.js`; `apps/desktop/webview/static/assets/launchView.js` | WebView | Pending drain button | Decision status is "Do not drain", "Evidence incomplete", or "Not evaluated" | Drain button disabled or local `frontend_guard` command result recorded; no `/api/pipeline/start` POST | Draining when local evidence suggests bad/missing manifests | Real for blockers, theoretical/redundant for incomplete evidence | Backend drain route, pending manifest trust checks, PowerShell transaction guards | hard-stop | partially | useful/redundant mixed | simplify/investigate | Hard-stop on backend blocker evidence is useful. Hard-stop on missing local evidence may be too aggressive. |
| SC-016 | `apps/desktop/webview/static/assets/pendingPublishView.drain.js`; `pendingPublishView.confidence.js` | WebView | Pending read-only evidence | Pending filters active, selected row differs from drain scope, recovery dry-run absent | Scope previews and repeated guardrail copy warn that filters do not narrow drain | Operator thinking table filters narrow backend drain | Real but frontend-only | Backend drain ignores WebView filters; route uses current manifests | low/medium | no | useful/redundant mixed | simplify | Keep one concise scope warning; cut duplicate paragraphs. |
| SC-017 | `src/mediapipeline/core/repair_reconcile/dry_run.py`; `src/mediapipeline/core/repair_reconcile/apply.py`; `src/mediapipeline/core/api/commands_repair_reconcile.py` | core/local API | Repair/reconcile apply | Apply requested without dry-run fingerprint, safe dry-run, selected rows, or `confirm_apply` | Apply returns blocked result | Writing bad manifests/sidecars from stale or frontend-inferred data | Real | Backend recomputes dry-run; fingerprint; backups; manifest contract validation | hard-stop | yes for real mutation confirmation/manifest integrity | required | keep | Correct lower-stack design. |
| SC-018 | `apps/desktop/webview/static/assets/pendingPublishView.recovery.js`; `pendingPublishView.js` | WebView | Pending repair/reconcile UI | No safe dry-run selection or blocked dry-run | Apply buttons disabled/blocked | Bad manifest repair from unsafe rows | Real | Backend dry-run/apply gates | medium/high | no | useful | keep/simplify copy | Keep disabled states, trim duplicate explanatory text. |
| SC-019 | `src/mediapipeline/core/rename/facade.py`; `src/mediapipeline/core/rename/apply_results.py`; `src/mediapipeline/core/rename/path_authority.py` | core backend | Rename apply/undo | Missing confirm, no selection, active work, blockers, unscoped paths, outside roots, missing undo manifest | Apply/undo returns blocked/warning result | Wrong file rename, collision, out-of-root path mutation, unsafe undo | Real | Backend rebuilds plan, selected_sources only, path authority, active-work lock, undo manifest | hard-stop | yes for real mutation confirmation/path mutation | required | keep | Backend blockers are appropriate. |
| SC-020 | `apps/desktop/webview/static/assets/rename/applyReadiness.js`; `apps/desktop/webview/static/assets/renameView.js` | WebView | Rename apply | No checked rows, duplicate targets, destination exists, blocked rows, stale preview | Apply disabled; confirmation modal required | Operator applying wrong rows or colliding destinations | Real | Backend selected_sources, plan rebuild, collision/blocker checks | medium/high | no except confirm_apply | useful | keep/simplify | Good staged UX; reduce repeated read-only guardrail prose. |
| SC-021 | `src/mediapipeline/core/network/lifecycle_facade.py`; `src/mediapipeline/core/api/commands_network.py`; `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` | core/local API/docs | Network lifecycle | Start/stop requested without dry-run-safe preconditions, provider hook, command journal, or confirmation | Command blocked; no provider call | Starting wrong lifecycle, losing claims/done reports, bypassing provider | Real | Provider preconditions, active-work guard, strict confirm, command journal, normal Launch block | hard-stop | yes for lifecycle/duplicate/command journal | required | keep | Correctly fail-closed. |
| SC-022 | `apps/desktop/webview/static/assets/networkView.js` | WebView | Network dashboard/lifecycle | State files, drift, close readiness, dry-run missing, pending done report | Status tiles and lifecycle controls show blocked/review | Operator starting network role without evidence | Real/useful but partly redundant | Backend lifecycle route performs authoritative preconditions | medium | no | useful | simplify | Treat dashboard warnings as review unless backend route says blocked. |
| SC-023 | `src/mediapipeline/core/processes/pipeline_facade.py`; `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` | core backend/docs | Normal Launch in network mode | `NetworkRole` coordinator/worker | Normal Launch returns blocked; Network lifecycle controls must be used | Worker/coordinator accidentally scanning local queue or processing wrong scope | Real | Network lifecycle provider routes | high | yes | required | keep | Do not weaken. |
| SC-024 | `ops/pipeline/engine/publish/pending_drain_transaction.ps1`; `pending_manifest_store.ps1`; `pending_push.ps1` | PowerShell | Pending drain cleanup and sidecar reveal | Untrusted manifest, missing payload, sidecar failure, reveal failure, unsafe cleanup boundary | Manifest remains queued; partials/sidecars rolled back or cleanup refused | Final output corruption or loss of parked evidence | Real | Manifest trust, retry state, boundary checks, rollback | hard-stop | yes | required | keep | Core drain safety. |
| SC-025 | `ops/pipeline/engine/process/*`; `ops/pipeline/engine/subtitles/*`; `src/mediapipeline/core/config/settings_risk_policy.py` | PowerShell/config | Subtitles/audio/media policy | OCR/conversion failure, destructive subtitle drop policy, no audio, downmix/transcode settings | Failure routes to review; launch/media-policy rows warn/block | Silent subtitle/audio loss | Real | PowerShell stream policy, settings risk, failure records | high | yes | required | keep | Do not weaken. |
| SC-026 | `src/mediapipeline/core/processes/path_evidence.py`; `src/mediapipeline/core/processes/preflight_facade.py`; `ops/pipeline/engine/paths/*` | core/PowerShell | Path and disk readiness | Roots missing/unreachable, disk below reserve, remote cleanup disabled | Preflight/path-health rows block or review | Writes to wrong/unreachable roots, disk exhaustion | Real | Backend path evidence, PowerShell path capability checks | medium/high | yes for source/scratch/output | required/useful | keep | Some advisory rows can be review, not hard-stop. |
| SC-027 | `src/mediapipeline/core/processes/launch_cleanup.py`; `src/mediapipeline/core/processes/active_jobs.py` | core backend | Stale progress/active jobs | Stale validate-only launch guards or progress artifacts | Cleanup before active-work checks; stale items removed carefully | False duplicate-start block; stale active-job confusion | Real | Staleness thresholds and process checks | low | yes indirectly | useful | keep | Reduces, not increases, friction. |
| SC-028 | `src/mediapipeline/core/api/commands_process.py`; WebView launch single-file UI | local API/WebView | Single-file launch/browse | Selected path missing, non-file, unsupported suffix, not absolute | Validation blocks browse/start | Invalid source selection | Real | Backend start validates again | medium | yes for source handling | useful | keep | Good backend-owned validation. |
| SC-029 | `src/mediapipeline/core/final_library/*`; `apps/desktop/webview/static/assets/settingsView.js` | core/WebView | Final Library Promotion/settings | Promotion settings changed or promotion requested | Confirm/review required; cleanup disabled by default | Copy/delete final-library outputs incorrectly | Real | Backend promotion policy, strict confirms, cleanup-after-verified setting | high | yes for final movement/cleanup | keep | investigate/simplify UI | Keep backend; consolidate duplicate `window.confirm` and review dialogs if stacked. |
| SC-030 | `apps/desktop/webview/static/assets/diagnostics*`; `src/mediapipeline/core/diagnostics/open_policy.py` | WebView/backend | Diagnostics open/tail | Operator opens log, manifest, source/output location | Only allowlisted backend-selected targets open; read-only diagnostics copy shown | Arbitrary path opening or mistaken diagnostics mutation | Real for path opening, redundant for read-only copy | Backend open policy and route validation | low | no | useful | simplify | Keep allowlist. Trim repeated "cannot mutate" prose. |
| SC-031 | `apps/desktop/webview/static/assets/completed*`; `src/mediapipeline/core/publish/reconciliation_policy.py` | WebView/backend DTO | Completed output proof/reconciliation | Missing output, pending proof overlap, same-leaf hints | Read-only proof boards and blockers/warnings | Rerun/cleanup/drain decisions based on stale proof | Real but mostly advisory | Backend publish reconciliation endpoint, pending drain manifests | low/medium | no | useful/redundant mixed | simplify | Read-only proof should rarely hard-stop normal operation. |
| SC-032 | `apps/desktop/webview/static/assets/sampleValidation*`; docs/testing smokes | WebView/docs/tests | Sample validation | Missing sample proof or pending proof still present | Evidence packets, append readiness, accepted decision warnings | Promoting release confidence from insufficient real-media evidence | Real for release validation, theoretical for daily operation | Backend sample-validation append routes and real-media validation runbook | low/medium | no | useful/redundant mixed | simplify/cut daily blockers | Keep release gate, avoid daily launch/publish hard-stops from sample proof absence. |
| SC-033 | `apps/desktop/webview/static/assets/queue*`; queue/launch decision panels | WebView | Queue/launch scope | Filters hide blocked rows or display cap hides rows | Scope warnings say filters do not narrow backend launch scope | Operator misreading UI subset as backend scope | Real | Backend queue source scan/start owns scope | low/medium | no | useful | simplify | Keep one scope warning; avoid repeated daily-use handoffs. |
| SC-034 | `ops/pipeline/engine/config/schema_validation.ps1`; `src/mediapipeline/core/config/metadata_parts/*` | config/PowerShell | Config save/runtime | Invalid numeric ranges, dangerous defaults, cleanup toggles | Settings rows warn/block; runtime clamps/validates | Invalid runtime behavior or over-broad cleanup | Real | Schema validation, defaults, settings preview | medium | yes for policy keys | required/useful | keep | Runtime validation belongs low-stack. |
| SC-035 | `tests/python/desktop/test_tauri_shell_scaffold.py`; `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`; `tests/webview/*` | tests/docs | WebView safety evidence | UI or smokes change | Tests require boundary text and no mutation route calls | Regression in WebView no-mutation boundary | Real for no POST/no touch, redundant for exact prose | Browser smokes, backend contracts, route tests | none to operator, high to dev velocity | no | useful/redundant mixed | simplify tests | Preserve behavioral assertions; loosen exact copy assertions where possible. |
| SC-036 | `docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`; validation runbook | docs/tests | Validation reporting | Smoke test run | Requires mutation boundary confirmation checklist | Ambiguous smoke evidence after test runs | Real for validation records, process friction | Test scripts already avoid mutation | none to operator, medium to agents | no | useful | keep/simplify | Keep for release evidence; not part of runtime operator flow. |
| SC-037 | `apps/desktop/webview/static/assets/launchView.js` | WebView | State journal archive | Event journal oversized/recovery action | Browser confirm before archival; backend route uses `confirm_archive` | Losing recovery evidence | Real but not media-critical | Backend archive route and path scope | medium | no | useful | keep/simplify | Keep one confirmation; wording can be shorter. |
| SC-038 | `ops/pipeline/entrypoints/MediaPipeline.ps1`; `ops/pipeline/engine/process/encode_*` | PowerShell | Encode/remux publish | Subtitle helper failure, encode verification failure, size guard, dynamic HDR failure | Pipeline blocks publish and records failure | Bad/incomplete output published | Real | Failure records, no publish on verification failure | high | yes for media policy | required | keep | Do not weaken media correctness gates in this audit. |
| SC-039 | `src/mediapipeline/core/processes/rerun_policy.py`; `apps/desktop/webview/static/assets/launch/startRequest.js` | core/WebView | CSV rerun source/final policy | Replacement destination/collision or original delete requested | Confirmation flags auto-collected or backend requires explicit confirmation | Final overwrite or source/original deletion | Real | Backend rerun policy and strict flags | high | yes | required | keep | Source delete remains outside normal launch. |
| SC-040 | `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`; `docs/architecture/*`; `AGENTS.md` | docs | Agent/developer workflow | High-risk areas touched | Requires reading boundary register and validation ladder | Unsafe implementation changes | Real | Change packet and validation workflow | none to operator, medium to dev velocity | yes | required | keep | Applies to AI/code changes, not runtime use. |

## 3. Grouped Recommendations

### Must keep

- Source no-delete and scratch isolation: SC-001, SC-002.
- Manifest-backed pending publish and drain transaction safety: SC-014, SC-024.
- Strict backend confirmations for real mutations: SC-003, SC-004, SC-010, SC-017, SC-019, SC-021, SC-029, SC-039.
- Command journal, duplicate-command guard, and close-readiness: SC-005, SC-006, SC-007, SC-027.
- Backend media policy ownership for subtitles/audio/encode verification: SC-012, SC-025, SC-038.
- Network lifecycle provider/precondition model and normal Launch block in network mode: SC-021, SC-023.
- Backend path authority and scoped selected-source rename: SC-019.

### Simplify

- Pending Publish WebView drain evidence stack: SC-015 and SC-016. Keep true blocker rows and backend drain validation; reduce duplicated scope/guardrail text and reconsider local hard-stops for "not evaluated" or "evidence incomplete".
- Launch/Settings risk handoffs: SC-009, SC-010, SC-011, SC-012. Keep backend preflight/save validation; demote advisory/read-only rows to review and make hard-stop rows traceable to backend route rejections.
- Rename UI readiness and outcome review: SC-020. Keep disabled states for duplicate/collision/blocker cases; reduce repeated boundary copy.
- Network dashboard wording: SC-022. Keep route preconditions; avoid making every dashboard problem look like a lifecycle hard-stop when the backend route will provide the actual result.
- Diagnostics, Completed, Queue, Sample Validation read-only proof panels: SC-030 through SC-033. Keep one boundary cue and backend ownership; remove duplicate daily-use handoffs.

### Move lower

- Any frontend-only decision that determines whether a real mutation is safe should either map to a backend route rejection or become a non-blocking review message. Candidate areas: Pending drain "not evaluated" hard-stop, Launch sample-proof blocking, Settings read-only policy labels, and Network dashboard dry-run cache warnings.
- Browser confirmations should submit explicit backend confirm fields, but the real accept/reject logic should remain in backend handlers. Where the UI has both a modal and a `window.confirm()` around the same mutation, consolidate to one operator review before posting the strict backend confirm.

### Cut candidates

- Duplicate "Mutation guardrail: this panel is read-only..." paragraphs across read-only boards.
- Exact-copy tests that require repeated boundary wording instead of verifying behavior.
- Launch/sample-validation proof blockers for daily operation when the backend start route would accept the request.
- Pending Publish local hard-stop for "not evaluated" or "evidence incomplete" when no backend blocker row is present.
- Settings/Launch "blocked" labels for read-only/staged evidence that does not affect saved backend configuration or launch route acceptance.

### Needs investigation

- Whether `pendingDrainGuardState()` should allow POST when status is "Evidence incomplete" or "Not evaluated", relying on backend drain validation to reject actual unsafe manifests.
- Which Launch Start Decision rows currently disable Start Pipeline versus only render warnings.
- Whether Final Library Promotion currently stacks a custom `window.confirm()` on top of the shared settings preview/save review in the same workflow.
- Whether smoke tests can be updated to assert common boundary components instead of per-panel prose.

## 4. Cut Candidate Detail

### CC-001: Repeated read-only mutation guardrail prose

- Why it appears safe to remove or reduce: The panels are read-only and already cannot mutate without calling backend routes. The no-mutation boundary is enforced by WebView route tests and backend API ownership.
- Lower-level control remaining: Route inventory, Local API handlers, strict mutation confirmations, browser smokes that block mutation POSTs.
- Expected operator benefit: Less visual noise and less habituation to warnings.
- Regression risk: Low. Main risk is losing visible reassurance for new operators.
- Tests/smokes needed: WebView static/browser smokes for affected panels, updated to assert a shared boundary cue plus no forbidden POST routes.

### CC-002: Pending drain local hard-stop for incomplete local evidence

- Why it appears safe to reduce: Backend drain does not trust WebView evidence. The PowerShell drain path re-reads manifests, validates trust, leaves unsafe manifests queued, and writes a drain summary.
- Lower-level control remaining: `/api/pipeline/start` mode `drain_pending_pushes`, pending manifest trust checks, retry states, transaction rollback, drain summary.
- Expected operator benefit: Operator can submit a drain and receive authoritative backend rejection instead of being blocked by stale/incomplete local evidence.
- Regression risk: Medium. If local "not evaluated" is masking truly missing scan data, operators could submit more backend drain attempts. The backend must return clear no-op/reject evidence.
- Tests/smokes needed: Pending drain guard smoke, backend pending publish route tests, PowerShell pending drain unit/reliability checks. Add a case where incomplete WebView evidence submits and backend rejects without moving files.

### CC-003: Launch/sample-validation proof as daily-operation blockers

- Why it appears safe to reduce: Sample-validation proof is release/readiness evidence, not a runtime source-protection invariant for every normal Start Pipeline. Backend start still checks active work, mode, path health, network role, config identity, and media policy.
- Lower-level control remaining: Launch preflight, pipeline start backend validation, process lock, command journal, PowerShell media policy.
- Expected operator benefit: Normal daily starts are not blocked by missing sample worksheet or proof packets.
- Regression risk: Low to medium. Risk is operators starting unattended work without enough release proof; that should remain a release gate, not an ordinary start blocker.
- Tests/smokes needed: Browser Launch/Queue readiness smoke, sample-validation smoke, route tests for `/api/launch/preflight`.

### CC-004: Settings/Launch read-only "blocked" labels for staged/advisory evidence

- Why it appears safe to reduce: Staged settings are inactive until backend preview/save/reload. Saved settings still go through backend launch risk policy and launch preflight.
- Lower-level control remaining: Settings patch digest confirmation, strict `confirm_save`, backend launch risk policy, PowerShell runtime validation.
- Expected operator benefit: Clearer distinction between "review before save" and "backend will reject".
- Regression risk: Low if true source/subtitle/audio blockers remain hard blockers.
- Tests/smokes needed: Settings patch evidence smoke, live-config handoff smoke, settings risk policy tests.

### CC-005: Duplicate browser confirmations around one backend-confirmed mutation

- Why it appears safe to consolidate: Backend routes require strict confirm fields and recompute/revalidate the mutation. A single modal or confirm before posting is enough UI ceremony.
- Lower-level control remaining: Backend strict confirmation, route validation, command journal, service-specific preconditions.
- Expected operator benefit: Fewer double prompts for experienced operators.
- Regression risk: Medium for destructive-ish actions like drain, rename, and final promotion. Keep an explicit review, but avoid two stacked prompts.
- Tests/smokes needed: Rename browser smoke, Pending drain guard smoke, Settings LibraryProfiles save smoke, final-library promotion tests if affected.

### CC-006: Tests that lock in duplicate wording instead of safety behavior

- Why it appears safe to reduce: Behavioral safety is no mutation POSTs, strict backend confirmation, backend route ownership, no source/output/scratch writes, and specific route inventory coverage. Exact prose can change without weakening safety.
- Lower-level control remaining: Browser smokes, route contract tests, strict JSON tests, command journal tests, PowerShell safety tests.
- Expected operator benefit: Indirect, through easier UI simplification and less warning copy.
- Regression risk: Low. Risk is accidentally removing all visible boundary cues; keep one shared cue assertion.
- Tests/smokes needed: Update affected tests to assert shared boundary components and forbidden-route behavior.

## 5. Implementation Plan For A Follow-Up Pass

No implementation is included in this audit. A follow-up pass should be staged and validated separately.

### Stage 1: Low-risk removals/simplifications

Likely files:

- `apps/desktop/webview/static/assets/pendingPublishView.drain.js`
- `apps/desktop/webview/static/assets/pendingPublishView.confidence.js`
- `apps/desktop/webview/static/assets/rename/preview.js`
- `apps/desktop/webview/static/assets/rename/applyReadiness.js`
- `apps/desktop/webview/static/assets/completed*`
- `apps/desktop/webview/static/assets/queue*`
- `tests/webview/*`
- `tests/python/desktop/test_tauri_shell_scaffold.py`
- `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`

Work:

- Replace repeated read-only guardrail paragraphs with a shared short boundary cue.
- Change advisory read-only labels from "blocked" to "review" where no backend route is blocked.
- Update tests to assert no mutation POSTs and the shared cue, not per-panel prose.

Validation:

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_pending_drain_guard_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_rename_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_tauri_shell_scaffold -q
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --changed
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

### Stage 2: Medium-risk consolidation

Likely files:

- `apps/desktop/webview/static/assets/pendingPublishView.confidence.js`
- `apps/desktop/webview/static/assets/launchView.js`
- `apps/desktop/webview/static/assets/launch/commandButtons.js`
- `apps/desktop/webview/static/assets/settingsView.js`
- `apps/desktop/webview/static/assets/settingsView.safetyLocks.js`
- `src/mediapipeline/core/config/settings_risk_policy.py`
- `src/mediapipeline/core/processes/preflight_facade.py`

Work:

- Make frontend hard-stop rows traceable to backend route rejection.
- Consolidate duplicate UI confirmations to one review step per mutation.
- Demote sample-validation/release proof gaps from daily-operation blockers to review-only unless the backend route rejects.

Validation:

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_process_launch -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_settings_patch_policy -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_launch_queue_readiness_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_settings_patch_evidence_smoke -q
.\ops\scripts\smoke\Test-WebViewBrowserPendingDrainGuardSmoke.ps1
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --changed
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

### Stage 3: Controls needing deeper validation

Likely files:

- `apps/desktop/webview/static/assets/pendingPublishView.confidence.js`
- `src/mediapipeline/core/publish/pending_drain_confidence.py`
- `ops/pipeline/engine/publish/pending_*.ps1`
- `src/mediapipeline/core/network/lifecycle_facade.py`
- `apps/desktop/webview/static/assets/networkView.js`
- Tauri close/readiness files only if close UX is changed

Work:

- Decide whether Pending drain should submit to backend on incomplete local evidence and rely on backend no-op/reject evidence.
- Audit Network dashboard warnings versus actual lifecycle route blockers.
- Do not change close-readiness hard-stop semantics unless a backend false-positive fix is proven.

Validation:

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_pending_publish -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_command_contracts -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_process_launch -q
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoLogo -NoProfile -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishSafetyChecks.ps1
.\ops\scripts\dev\start-tauri-preview.bat -CheckOnly
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

Real-media validation is not required for Stage 1 wording-only changes. Stage 2 remains WebView/backend validation unless it changes backend route acceptance. Stage 3 pending-drain behavior changes may require representative pending-publish validation, but should still not weaken manifest-backed drain or source/scratch protections.
