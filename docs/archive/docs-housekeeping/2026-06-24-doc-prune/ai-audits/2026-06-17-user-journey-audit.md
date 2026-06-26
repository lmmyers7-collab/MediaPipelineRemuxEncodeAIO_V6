# User Journey Audit

Date: 2026-06-17
Change packet: MP-CHANGE-2026-0617-901
Scope: First-time operator journeys across active docs, WebView UI surfaces, Local API route inventories, launcher scripts, architecture safety docs, and operator runbooks.
Mode: Report-only audit. No UI, active docs outside this report, scripts, source behavior, tests, settings, queue state, media files, or runtime artifacts were changed. A targeted generated summary refresh was run for the change packet.

## Executive Summary

The product has strong backend safety boundaries: source media is immutable by default, mutation routes are backend-owned, close readiness is backend-authoritative, pending-publish drain is manifest-backed, diagnostics are allowlisted/read-only, and high-risk media behavior is explicitly tied to the validation ladder. Those are the right safety foundations.

The first-time operator experience is still hard because the safety model is distributed across too many names, pages, and launch paths. A new operator can find at least three "setup" concepts, two "publish" concepts, several "scan" or "refresh" concepts, and multiple places that look like they start, drain, promote, rerun, or repair work. Most of these are safe by implementation, but the user has to understand backend scope, evidence-only panels, display filters, render caps, pending publish, final-library promotion, completed manifests, and command journals before their first successful run.

No confirmed critical data-loss journey was found in the documented surfaces. The highest usability risks are:

- Confusing first-run order across setup, verify, Local API, browser, and Tauri.
- Publish terminology collisions between pending-publish drain, completed-output review, and final-library promotion.
- Backend scope confusion: filters, selected rows, render caps, and preview panels do not change launch or drain scope.
- Rename apply scope: if no rows are checked, the apply flow targets every applicable non-blocked row.
- Failure, rerun, and recovery flows span Completed, Pending Publish, Diagnostics, Reports, Queue, and Launch without one row-centered resolution path.

## Methodology

- Read the required session entry docs first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, and `docs/generated/PROJECT_INDEX.md`.
- Used generated summaries before source reads where available. Several relevant summaries were unparsed, so targeted full-source or excerpt reads were used for UI partials, launcher scripts, and architecture docs.
- Reviewed operator docs: `README.md`, `docs/DOCS_INDEX.md`, `docs/README_MediaPipelineRemuxEncodeAIO.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/operator/OPERATOR_GLOSSARY.md`, `docs/operator/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md`, `docs/operator/COMPLETED_PENDING_FAILURE_PLAYBOOK.md`, and `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`.
- Reviewed launchers and setup scripts under `ops/scripts/dev/`, `ops/pipeline/entrypoints/`, and `apps/desktop/launchers/`.
- Reviewed WebView partials for Home, Launch, Queue, Completed Output, Pending Publish, Rename, Settings, Libraries, Diagnostics, Maintenance, and navigation.
- Reviewed Local API route inventory and mutation matrix evidence for command boundaries.
- Did not run the app, process media, launch browsers, save settings, scan sources, rename, drain pending publish, promote files, or run live API requests. This is a static journey audit.

## Severity Model

| Severity | Meaning |
|---|---|
| Critical | Likely source data loss, unsafe publish, unsafe rename, or active-work interruption with weak guardrails. |
| High | Likely operator confusion on a mutating or launch-scope workflow that can block successful completion or cause risky action. |
| Medium | Frequent confusion, hidden prerequisite, stale feedback, or recovery friction with low direct data risk. |
| Low | Copy, terminology, or navigation issue that slows understanding but has obvious recovery. |

Implementation effort is ranked `S`, `M`, or `L`.

## Journey Map

| # | Journey | Primary entrypoint | Expected goal | Actual operator path | Main usability risk |
|---|---|---|---|---|---|
| 1 | First setup | `ops/scripts/dev/setup.bat`, README, Settings Guided Setup | Produce a valid config and safe local state roots. | Read README, run verify/setup, choose roots, validate, then later repeat similar choices in WebView Settings. | "Setup" exists as script, docs path, and in-app wizard; first-run order is split. |
| 2 | Environment verification | `ops/scripts/dev/verify-env.bat` | Know whether this machine can safely run the app. | Run batch wrapper, interpret runtime/tool/config/OCR/network sections. | CheckOnly, verify-env, release self-test, and real-media validation prove different things. |
| 3 | Launch local API | `ops/scripts/dev/start-local-api.bat` | Start backend-only local API. | Wrapper calls desktop launcher, starts bundled Python API, emits token-auth local server. | API-only mode has little beginner guidance about next browser/UI step. |
| 4 | Launch Tauri/WebView | `start-api-and-browser.bat` or `start-tauri-preview.bat` | Open the operator UI. | Browser launcher opens backend-served UI; Tauri preview adds Node/Cargo/WebView2 prerequisites. | Root docs mix browser and Tauri paths; Tauri `-CheckOnly` is not media readiness. |
| 5 | Configure library roots | Settings Guided Setup, Libraries page, setup script | Define source, scratch/local, and final output roots. | Use script or WebView paths, profiles, route map, staged patch, Preview, Save, reload. | Source roots, final output root, `Outsource`, LocalBase, library profiles, and route map overlap conceptually. |
| 6 | Scan/discover media | Queue `Scan Sources` | Discover new source files and produce launchable queue evidence. | Press Scan Sources, wait for backend-owned source inventory/curation/snapshot. | "Refresh" vs "Scan" vs stale snapshot history is easy to misunderstand. |
| 7 | Queue work | Queue page, Launch page | Decide what will run and in what order. | Review queue rows, filters, priority, manual order, strategy, file overrides, then Launch. | Display filters and selected rows do not define backend launch scope. |
| 8 | Monitor active jobs | Home, Launch, Diagnostics | See active work, progress, and safe next action. | Watch Live Run, progress proof, active jobs, stderr/stdout, command history. | Evidence is spread across many panels; command journal is session evidence, not full recovery state. |
| 9 | Understand remux vs encode | Queue route evidence, Completed route, Settings policy | Know why a file remuxes or encodes. | Inspect route reason, decision trace, profile score, settings, completed manifest, logs. | Route explanation requires cross-page evidence and domain vocabulary. |
| 10 | Handle subtitles/audio | Settings Audio/Subtitles, Queue file overrides, Completed proof | Preserve correct tracks and know when review is needed. | Configure policy, optional file override, inspect subtitle/audio checks and completed evidence. | Defaults are safe but not self-evident; OCR/conversion failure behavior is in docs, not first-run UI. |
| 11 | Review failures | Completed, Pending Publish, Diagnostics, Reports | Diagnose failed or suspicious output. | Use row detail, allowlisted diagnostics tail/open, failure JSON/report, reconciliation. | Failure triage path is correct but multi-page and vocabulary-heavy. |
| 12 | Rerun/retry | Launch CSV Rerun, API `/api/rerun/start`, Queue/Completed evidence | Retry safely with dry-run proof first. | Preview CSV rerun or call rerun route, inspect plan, then launch. | Runbook says dry-run first; route defaults and UI labels require careful reading. |
| 13 | Rename workflow | Rename page | Preview and apply safe filesystem renames. | Stage files, choose mode, preview, check rows, confirm apply, review result/log. | If no rows are checked, apply scope is all applicable non-blocked rows. |
| 14 | Publish workflow | Completed Output, final-library promotion | Move reviewed completed output to final library when safe. | Review trust/proof, select output, promote queue with backend route. | "Publish" also means pending-publish drain; final-library promotion is a separate mutation. |
| 15 | Pending-publish drain | Pending Publish, Launch `Publish Parked` mode | Drain parked output after final root is safe. | Review scope preview, blockers, recovery plan, then drain parked outputs. | "Drain", "Publish Parked", "Pending Publish", and "Deferred Publish" are hard to connect. |
| 16 | Diagnostics/log review | Diagnostics page, diagnostics open/tail routes | Inspect evidence without mutating state. | Choose target, byte limit, Read Tail/Open Target, follow recovery guidance. | Good safety, but many technical targets compete for first-time attention. |
| 17 | Shutdown/close readiness | Topbar close readiness, Tauri close prompt, Diagnostics | Know when it is safe to close. | Backend reports close readiness; Tauri asks backend before graceful shutdown. | Browser mode vs Tauri mode have different close affordances; active-work warnings require trust in backend terms. |
| 18 | Recovery after restart | Home, Diagnostics, Queue, Completed, Pending Publish | Resume after crash/restart without corrupting state. | Read ActiveJobs, progress snapshots, completed manifest, pending manifests, logs, stale state. | Recovery state is durable but distributed; no single "after restart" operator lane. |

## Per-Journey Audit

### 1. First Setup

- Entrypoint: `docs/README_MediaPipelineRemuxEncodeAIO.md`, root `README.md`, `ops/scripts/dev/setup.bat`, Settings Guided Setup.
- Expected user goal: create or validate a config with source roots, scratch/LocalBase, final output root, and safe defaults.
- Actual steps: read docs, run `verify-env.bat`, run `setup.bat`, choose roots, validate config, start WebView, inspect Settings Guided Setup, Preview Patch, Save Settings, reload.
- Terminology confusion: "setup" means a PowerShell wizard and an in-app guided setup; "LocalBase", "scratch", "final output root", "Outsource", "library profile", and "route map" are not beginner terms.
- Hidden prerequisites: bundled Python, PowerShell 7 fallback, FFmpeg/ffprobe, MKVToolNix, Python packages, writable config location, optional PgsToSrt/tessdata for BDPGS OCR.
- Excessive clicks: a cautious first run touches docs, terminal setup, WebView Settings, Preview, Save, Reload, Queue, and Launch before processing one file.
- Unclear defaults: safe defaults exist, but the operator must infer which roots are source, scratch, parked output, and final library.
- Missing feedback: no single "first job ready" status ties verify-env, config validity, queue scan freshness, and launch readiness together.
- Dangerous ambiguity: low direct source risk because backend policies protect source roots, but a wrong final root or scratch root can make output/pending-publish behavior surprising.
- Docs/UI mismatch: root README emphasizes launcher commands; the detailed readme gives a first-run order; the WebView presents Settings and Libraries as separate high-value starting points.
- Recovery weakness: if setup is abandoned halfway, the operator must know where config was written and whether staged WebView changes were saved.

### 2. Environment Verification

- Entrypoint: `ops/scripts/dev/verify-env.bat` and `ops/scripts/dev/verify-env.ps1`.
- Expected user goal: know whether the machine is ready to run the pipeline.
- Actual steps: run wrapper, read release layout, runtime dependency, Python package, config writability, OCR, network, and summary sections.
- Terminology confusion: "release layout", "AllowSystemTools", "BDPGS OCR readiness", "network mode", and "portable-bundle" require project knowledge.
- Hidden prerequisites: Windows shell behavior, bundled/runtime paths, optional system fallbacks, and profile-dependent OCR/network checks.
- Excessive clicks: terminal-only output does not hand the user into the WebView next step.
- Unclear defaults: `-CheckOnly` for Tauri, verify-env, release test, and validation ladder rungs are easy to over-trust interchangeably.
- Missing feedback: verification output needs one operator-facing conclusion: "safe to open UI", "safe to run non-media UI only", or "blocked".
- Dangerous ambiguity: a passing Tauri prereq check does not prove FFmpeg, subtitles, audio, publish, or real-media behavior.
- Docs/UI mismatch: Tauri docs explicitly say CheckOnly does not validate media behavior, but first-start command lists place it near runtime validation commands.
- Recovery weakness: failed checks tell what failed, but the first-time path back to setup or dependency install is distributed.

### 3. Launching Local API

- Entrypoint: `ops/scripts/dev/start-local-api.bat`.
- Expected user goal: start the Python backend for browser or tool access.
- Actual steps: wrapper calls `apps/desktop/launchers/Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat`, which starts the local API with token protection.
- Terminology confusion: "local API" is distinct from "browser WebView", "Tauri shell", and direct pipeline `run.bat`.
- Hidden prerequisites: importability of `mediapipeline.desktop.local_api_main`, bundled Python path, port availability, token-auth behavior.
- Excessive clicks: API-only launch requires the operator to know a browser URL or choose a second launcher.
- Unclear defaults: token-auth local server is correct, but first-time users may not know whether `-NoToken` is ever appropriate. It is a dev escape hatch, not an operator path.
- Missing feedback: API-only output is backend-centric rather than journey-centric.
- Dangerous ambiguity: low media risk because launching API does not process media, but a second backend or stale process can confuse later UI state.
- Docs/UI mismatch: docs promote browser/Tauri launchers for operators; API-only is useful but less beginner-oriented.
- Recovery weakness: if the API starts but WebView does not, the next troubleshooting step is Diagnostics only after the UI exists.

### 4. Launching Tauri/WebView

- Entrypoint: `ops/scripts/dev/start-api-and-browser.bat`, `ops/scripts/dev/start-tauri-preview.bat`, `apps/desktop/tauri/README.md`.
- Expected user goal: open the primary operator UI.
- Actual steps: browser launcher starts API and opens `http://127.0.0.1:<port>/`; Tauri launcher checks Node/Cargo/node_modules, spawns backend, validates health/contract/assets, opens WebView2.
- Terminology confusion: "WebView", "browser", "Tauri preview", "desktop shell", and "local API" are all valid but not equal.
- Hidden prerequisites: browser availability for browser launcher; Node, npm packages, Cargo/Rust, WebView2, and bundled Python for Tauri preview development.
- Excessive clicks: Tauri first use can require `-CheckOnly`, optional `-InstallNodePackages`, then launch.
- Unclear defaults: first-time users may not know whether browser launcher or Tauri preview is canonical for their situation.
- Missing feedback: if launch fails before UI, diagnostics guidance is in launcher output and docs rather than a visible recovery screen.
- Dangerous ambiguity: Tauri close readiness is stronger than browser-tab close behavior; users may assume both shutdown the backend identically.
- Docs/UI mismatch: `apps/desktop/tauri/README.md` still says network lifecycle is not exposed through the shell, while current project state and UI include Network lifecycle routes/pages.
- Recovery weakness: unexpected Tauri/backend exit has lifecycle banners and ActiveJobs reconciliation, but this is not framed as a first-time recovery path.

### 5. Configuring Library Roots

- Entrypoint: Settings Guided Setup, Settings Paths & Safety, Libraries page, `setup.bat`.
- Expected user goal: tell the product where source libraries, scratch/local state, pending output, and final output live.
- Actual steps: add or edit library roots, choose output mode, set final output root, validate paths, Preview Patch, Save Settings, reload, inspect route map.
- Terminology confusion: "library roots" can mean source roots, final library root, library profiles, or route-map profiles.
- Hidden prerequisites: roots must be writable/readable as appropriate; output roots must not accidentally point at source roots; per-user config may override bundle config.
- Excessive clicks: Settings Guided Setup and Libraries profile editing overlap for first-time root work.
- Unclear defaults: `Staged / pending publish`, output-exists behavior, scratch reserve, output reserve, keep-all-audio, and subtitle language defaults need plain-language previews.
- Missing feedback: the UI stages Changes JSON and backend preview/save separately, but a new user may not understand whether changes are active.
- Dangerous ambiguity: wrong final root or profile assignment can route publish to an unexpected destination, though backend pending-publish guards reduce risk.
- Docs/UI mismatch: detailed docs describe setup script first; WebView offers both Settings Guided Setup and Libraries as plausible first configuration surfaces.
- Recovery weakness: after a bad save, the rollback path is config backup/reload knowledge rather than a visible "restore previous settings" journey.

### 6. Scanning/Discovering Media

- Entrypoint: Queue page `Scan Sources`.
- Expected user goal: find source files and produce an authoritative queue snapshot.
- Actual steps: press Scan Sources, backend performs or observes scan, curation writes queue artifacts, UI shows queue rows/status.
- Terminology confusion: "Refresh Queue" reads existing state; "Scan Sources" should rebuild evidence; "inventory" candidates are not launchable queue rows.
- Hidden prerequisites: configured source roots, backend queue planner, duplicate-command guard, queue snapshot path under state/progress.
- Excessive clicks: after scan, operator still needs filters, route evidence, Launch preflight, and Start Pipeline.
- Unclear defaults: stale snapshots can be displayed while scan is running; user must know when rows are current.
- Missing feedback: historical queue architecture notes show this has been a mismatch area; the UI needs clear last-scan time, curation status, and stale snapshot wording.
- Dangerous ambiguity: launching from uncurated inventory would be unsafe, but docs require backend curation before rows are launchable.
- Docs/UI mismatch: older queue plan docs discuss prior "scan" wording mismatch; current audit should verify the live UI consistently uses "Scan Sources" for the backend command.
- Recovery weakness: after failed scan, the fallback is Diagnostics/queue scan status rather than one local "why file is missing" explanation.

### 7. Queueing Work

- Entrypoint: Queue page and Launch page.
- Expected user goal: choose what will run and in what order.
- Actual steps: inspect rows, status filters, investigation filters, priority, manual order, strategies, file overrides, backend scope preview, then start from Launch.
- Terminology confusion: "selected row" is display context; "visible rows" are not backend scope; "loaded rows" are not necessarily all backend rows.
- Hidden prerequisites: backend snapshot freshness, source-root containment for priority/overrides, route decisions from backend policy.
- Excessive clicks: priority/order/strategy/file overrides are powerful but dense for first-time use.
- Unclear defaults: standard strategy, backend queue scope, run once vs continuous, and schedule override need first-run explanation.
- Missing feedback: scope preview is evidence-only; users may miss that filters and selections do not narrow launch.
- Dangerous ambiguity: a user can filter to one row and start thinking only one file will run when backend scope is broader.
- Docs/UI mismatch: docs correctly warn about backend scope; the UI must repeat this at every launch/drain decision point, not only in guide docs.
- Recovery weakness: after launching unintended scope, recovery depends on Stop After Current, Force Stop, and queue evidence review.

### 8. Monitoring Active Jobs

- Entrypoint: Home, Launch, Diagnostics.
- Expected user goal: know what is running, progress, current file, and safe next action.
- Actual steps: watch Live Run, Run Progress, Progress Proof, Current Run, Active Jobs, Run Logs, Last Stderr, command history, close readiness.
- Terminology confusion: "ActiveJobs", "runtime progress", "progress proof", "command journal", and "snapshot" are technical.
- Hidden prerequisites: backend progress files, process tracking, log availability, polling refresh health.
- Excessive clicks: same evidence appears across Home, Launch, and Diagnostics with different emphasis.
- Unclear defaults: manual Refresh vs automatic refresh cadence is not prominent enough for stale panels.
- Missing feedback: optional read failures can leave last-good data looking credible unless stale markers are obvious.
- Dangerous ambiguity: closing during active work is guarded, but users must trust backend close-readiness vocabulary.
- Docs/UI mismatch: Home says controls navigate/open allowlisted evidence and Launch owns starts/stops; that division is good but should be visually stronger.
- Recovery weakness: command journal is valuable session evidence, but durable recovery after restart uses state/log files, not the in-memory UI story.

### 9. Understanding Remux vs Encode Decisions

- Entrypoint: Queue route evidence, Completed Output route columns, Settings route policy.
- Expected user goal: understand why a file will remux or encode and what that means.
- Actual steps: inspect queue route reason, decision trace, route profile, estimated bitrate, Plex score, component actions, fallback attempt, completed manifest, FFmpeg stderr/logs.
- Terminology confusion: "remux", "encode", "Direct Play", "Stream", "route decision", "route proof", "component action", and "fallback attempt" are expert terms.
- Hidden prerequisites: FFmpeg/ffprobe, MKVToolNix, profile settings, sidecar overrides, audio/subtitle policy.
- Excessive clicks: explanation spans Queue, Settings, Completed, Diagnostics, and logs.
- Unclear defaults: H.264 remux-safe and Plex Direct/Stream defaults are documented but not a first-run UI teaching moment.
- Missing feedback: no single "Why this route?" packet is presented as the canonical explanation for one file.
- Dangerous ambiguity: changing policy without understanding route impact can trigger high-validation media behavior changes.
- Docs/UI mismatch: docs explain backend owns media policy; file override controls can look like UI-owned media policy unless copy is explicit.
- Recovery weakness: if the route is surprising after completion, the correction loop is triage plus dry-run rerun rather than an obvious route review action.

### 10. Handling Subtitles/Audio Options

- Entrypoint: Settings Audio & Subtitles, Queue file override drawer, Completed proof panels.
- Expected user goal: preserve original tracks, add preferred SRT where configured, and avoid bad audio/subtitle output.
- Actual steps: review default audio/subtitle policy, set languages, keep forced/unknown options, optionally override one file, inspect checks and completed evidence.
- Terminology confusion: ASS/SSA, TX3G, BDPGS OCR, SRT sidecar, passthrough, downmix, transcode, forced subtitles, and no-audio acknowledgement are specialized.
- Hidden prerequisites: `pysubs2`, PgsToSrt/tessdata for BDPGS OCR, source track metadata, sidecar policy, profile settings.
- Excessive clicks: audio/subtitle checks are split between Settings, Queue overrides, Completed evidence, and sample validation.
- Unclear defaults: "preserve originals by default" is safe, but first-time users may not know when SRT is added or review is required.
- Missing feedback: OCR/conversion failures route to review by policy, but the first-time UI should state this near subtitle controls.
- Dangerous ambiguity: enabling no-audio output requires acknowledgement, which is good; casual audio/downmix policy changes remain high-risk.
- Docs/UI mismatch: docs emphasize representative real-media validation for subtitle/audio changes; Settings should make that cost visible before policy edits.
- Recovery weakness: subtitle/audio failures require Completed/Pending/Diagnostics evidence and rerun planning, not a row-local repair lane.

### 11. Reviewing Failures

- Entrypoint: Completed Output, Pending Publish, Diagnostics, Reports.
- Expected user goal: determine whether a failed/suspicious item is safe, retryable, parked, missing evidence, or needs manual review.
- Actual steps: select row, inspect manifest, sidecars, route reason, stderr/stdout, failure JSON/report, publish reconciliation, recovery plan, and runbook guidance.
- Terminology confusion: "failure marker", "failure report", "completed manifest", "publish reconciliation", "DeferredPublish", "Do Not Drain", and "safe next action" are many concepts.
- Hidden prerequisites: logs and manifests must exist, diagnostics targets are allowlisted, failure roots are readable.
- Excessive clicks: the documented path is correct but crosses at least three pages for many failures.
- Unclear defaults: route disagreement alone is not a failure; this is subtle and easy to miss.
- Missing feedback: there is no one-click row-centered triage packet combining the recommended evidence sequence.
- Dangerous ambiguity: clearing or retrying before evidence review can hide the root cause, though mutation routes remain guarded.
- Docs/UI mismatch: runbooks are strong; UI should surface the same ordered evidence path from the selected row.
- Recovery weakness: after partial evidence or missing manifests, the operator must choose among recovery plan, dry-run rerun, reconciliation, and manual inspection.

### 12. Rerunning/Retrying

- Entrypoint: Launch CSV Rerun, rerun API, failure playbook.
- Expected user goal: retry a failed item without touching source media or corrupting output.
- Actual steps: collect evidence, preview CSV rerun or dry-run rerun, inspect plan, then start actual rerun if safe.
- Terminology confusion: "dry_run", "stage_mode: copy", "original_mode: keep", "return_mode: park", "CSV rerun", and "pipeline start" overlap.
- Hidden prerequisites: failure evidence, source availability, scratch/output space, current config, route planner.
- Excessive clicks: a safe retry involves failure page, Diagnostics, possibly Queue/Completed, Launch preview, then Launch start.
- Unclear defaults: playbooks say never skip dry-run; API inventory notes `/api/rerun/start` has media-safe defaults but `dry_run:false`, which is a scripting hazard unless callers are explicit.
- Missing feedback: after a retry starts, the handoff to monitoring/recovery should name the retried evidence path.
- Dangerous ambiguity: retry without a dry-run can repeat a bad policy or output collision.
- Docs/UI mismatch: UI offers Preview CSV Rerun, which is good; API docs and runbook need harmonized "dry-run first" wording.
- Recovery weakness: failed rerun recovery returns to the same multi-page failure triage path.

### 13. Rename Workflow

- Entrypoint: Rename page.
- Expected user goal: safely preview and apply file renames for one movie or one TV season.
- Actual steps: stage paths, choose TV/movie naming mode and templates, preview plan, check rows, confirm filesystem rename, apply, review result/log.
- Terminology confusion: "scrubbed", "pipeline naming preview", "applicable", "blocked", and "apply readiness" require explanation.
- Hidden prerequisites: staged files, path containment or explicit outside-roots permission, backend rename plan, output sidecar choices.
- Excessive clicks: the rename flow is deliberately multi-step and appropriate for filesystem mutation.
- Unclear defaults: if checked rows exist, apply checked rows; if none are checked, apply all applicable non-blocked rows.
- Missing feedback: the apply-scope legend exists, but the default-all fallback is risky enough to deserve a separate explicit mode.
- Dangerous ambiguity: a user can think "no rows checked" means "nothing selected", while the backend will apply all applicable non-blocked rows after confirmation.
- Docs/UI mismatch: docs correctly state backend rename apply owns mutation; UI should make the all-applicable fallback harder to miss.
- Recovery weakness: rename mistakes rely on logs and manual filesystem recovery, not a built-in undo.

### 14. Publish Workflow

- Entrypoint: Completed Output page and final-library promotion controls.
- Expected user goal: review completed output evidence and promote verified output to the final library when appropriate.
- Actual steps: review current output status, trust decision, sidecars, route/size evidence, final paths, then queue/pause/resume promotion.
- Terminology confusion: "completed output", "publish", "final library promotion", "trust ready", and "evidence incomplete" overlap with pending publish.
- Hidden prerequisites: completed manifest, final output root, output proof, sidecar evidence, backend promotion queue.
- Excessive clicks: trust, row selection, evidence, promotion status, and diagnostics links are separate mental steps.
- Unclear defaults: "Promote Selected Reviewed Output" can sound like the normal publish path, while pending publish drain is separate.
- Missing feedback: first-time users need a simple distinction between already-final completed outputs, reviewed local outputs, and parked outputs.
- Dangerous ambiguity: final-library promotion is a high filesystem mutation, distinct from draining parked output.
- Docs/UI mismatch: docs and route inventories identify final-library promotion separately; operator copy should avoid using generic "publish" for both workflows.
- Recovery weakness: promotion failure triage uses Completed/Pending/Diagnostics/Reconciliation rather than a single promotion recovery path.

### 15. Pending-Publish Drain

- Entrypoint: Pending Publish page, Launch `Publish Parked` mode, Maintenance references.
- Expected user goal: move parked outputs to final root after final output is safe and reachable.
- Actual steps: inspect pending rows, blockers, risk summary, recovery preview, drain scope, checklist, then Drain Parked Outputs or Launch publish-parked mode.
- Terminology confusion: "pending publish", "Deferred Publish", "parked output", "drain", "Publish Parked", "pending push", and "manifest" all describe related but different parts.
- Hidden prerequisites: final root safety, pending manifests, parked media and sidecars, enough space, destination availability.
- Excessive clicks: many safety panels are necessary, but first-time users may not know which are blockers versus evidence.
- Unclear defaults: display filters do not define drain scope; hidden blocked/review rows must be considered before drain.
- Missing feedback: the drain page has strong evidence, but it should keep one dominant "safe next action" visible.
- Dangerous ambiguity: draining hidden or misunderstood scope is the highest publish-related confusion risk, though backend manifest guards are strong.
- Docs/UI mismatch: docs mention Maintenance `Publish Parked`; current UI centers Pending Publish and Launch drain mode, so naming should be reconciled.
- Recovery weakness: do-not-drain and missing-payload paths are documented, but the recovery decision tree is not one linear UI flow.

### 16. Diagnostics/Log Review

- Entrypoint: Diagnostics page and diagnostics open/tail API.
- Expected user goal: inspect evidence without mutating state.
- Actual steps: choose log/state target, select byte limit, read tail, open allowlisted folder/file, follow Recovery Steps and Page Handoff.
- Terminology confusion: target names like `latest_failure_json`, `cluster_log`, `active_jobs`, `sample_validation_log`, and `tdarr matrix` are technical.
- Hidden prerequisites: allowlisted paths, existing runtime state, readable logs, correct row context.
- Excessive clicks: diagnostics is dense and advanced by design.
- Unclear defaults: byte limit and target selection need a recommended default for first-time triage.
- Missing feedback: when a target is missing, the UI should explain whether that is healthy, stale, or a problem.
- Dangerous ambiguity: low direct mutation risk because diagnostics routes are read-only/open-only, but advanced cleanup/delete labels in Diagnostics-adjacent Tdarr proof tools can alarm new users.
- Docs/UI mismatch: diagnostics runbook is clear that this page cannot retry/launch/drain/save/rename/repair/delete/publish/open arbitrary paths; the UI should repeat that boundary near advanced tools.
- Recovery weakness: diagnostics gives evidence, not a resolution workflow, so users must navigate to the owning page.

### 17. Shutdown/Close Readiness

- Entrypoint: topbar close-readiness pill, Tauri close prompt, Diagnostics shutdown readiness.
- Expected user goal: know whether closing the UI/backend is safe.
- Actual steps: backend reports close readiness, Tauri asks backend before close, graceful shutdown posts to backend, force termination is bounded only after failed graceful shutdown.
- Terminology confusion: "close readiness", "active work", "schedule-stop watcher", "backend shutdown", and "force stop" are distinct.
- Hidden prerequisites: running under Tauri for native close interception; browser mode may leave backend process behavior less obvious.
- Excessive clicks: stopping work safely may require Launch controls, Diagnostics, and close prompt.
- Unclear defaults: first-time users may not know whether closing browser, Tauri window, or terminal stops processing.
- Missing feedback: a single "what closes what" note would reduce surprise.
- Dangerous ambiguity: forced close during active work can leave partial outputs or workers; backend readiness reduces this risk when respected.
- Docs/UI mismatch: Tauri lifecycle docs are accurate about backend ownership, but browser launcher docs should set expectations for backend lifetime.
- Recovery weakness: if a process is killed externally, recovery relies on ActiveJobs reconciliation and logs, not a user-facing restart wizard.

### 18. Recovery After Restart

- Entrypoint: Home, Diagnostics, Queue, Completed Output, Pending Publish.
- Expected user goal: after crash/reboot/relaunch, know what happened, what is safe, and what to do next.
- Actual steps: inspect live state, ActiveJobs, progress snapshots, close readiness, queue snapshot, completed manifest, pending manifests, failure reports, command history if available.
- Terminology confusion: "stale runtime state", "orphaned status", "ActiveJobs", "completed manifest", "pending manifest", and "reconciliation" are recovery-specific.
- Hidden prerequisites: durable state files, process reconciliation, manifest integrity, source files still present for retry.
- Excessive clicks: restart recovery is distributed across at least five pages.
- Unclear defaults: stale queue or progress state may be expected, but first-time users need a clear "trust these artifacts first" order.
- Missing feedback: no single restart recovery panel summarizes last run, orphaned work, parked output, partial output, and safe next action.
- Dangerous ambiguity: relaunching processing before understanding previous partial/pending state can duplicate work or confuse output trust.
- Docs/UI mismatch: architecture docs discuss stale ActiveJobs and backend-owned cleanup; operator UI should expose that as restart guidance.
- Recovery weakness: current recovery is evidence-rich but not task-linear.

## Prioritized Usability Findings

| Rank | Finding | Severity | Why it matters | Effort |
|---|---|---|---|---|
| 1 | Backend scope is hard to understand across Queue, Launch, and Pending Publish. | High | Filters, selected rows, and render caps can look like execution scope. Confusion can start or drain more than the operator intended. | M |
| 2 | Publish language collides across pending-publish drain, completed-output review, and final-library promotion. | High | These are different filesystem workflows with different risks, but all can be read as "publish". | S |
| 3 | First-run order is split across setup script, verify-env, browser launcher, Tauri launcher, Settings, and Libraries. | High | A new operator lacks one authoritative "first successful file" path. | M |
| 4 | Rename apply has an all-applicable fallback when no rows are checked. | High | "Nothing checked" can be read as "nothing selected"; filesystem rename has no built-in undo. | M |
| 5 | Failure/rerun recovery is evidence-rich but not row-linear. | Medium | Correct triage spans several pages and terms, increasing abandoned or unsafe retries. | L |
| 6 | Remux/encode decisions require cross-page vocabulary and log evidence. | Medium | Users need a one-file route explanation before trusting or changing policy. | M |
| 7 | Subtitle/audio policy is safe but opaque for first-time users. | Medium | OCR, sidecar, passthrough, and review behavior are high-validation domains. | M |
| 8 | Verification commands prove different readiness levels without a shared readiness label. | Medium | Tauri CheckOnly, verify-env, release test, browser smoke, and real-media validation can be over-generalized. | S |
| 9 | Restart recovery lacks a single lane. | Medium | Durable evidence exists, but the user has to assemble state across pages after the most stressful event. | L |
| 10 | Stale docs and glossary inconsistencies create avoidable distrust. | Medium | Tauri/network status, Maintenance publish wording, desktop module path wording, and glossary count/text drift should not compete with active UI. | S |
| 11 | Settings staging semantics are not beginner-obvious. | Medium | Users may not know when Changes JSON, preview, save, and reload become active policy. | M |
| 12 | Diagnostics is safe but too technical as a first failure surface. | Low | Read-only evidence is good, but first-time target names need guided presets. | S |

## Terminology And Glossary Issues

- Use "Drain Parked Outputs" instead of generic "Publish Parked" where the action is pending-publish drain.
- Use "Final Library Promotion" only for completed-output promotion, and avoid calling it simply "publish".
- Use "Completed Output Review" for evidence review before any promotion, not "publish workflow".
- Reserve "Scan Sources" for backend curation or inventory-plus-curation. Use "Refresh Queue" only for reading existing backend state.
- Always pair "selected row" with "display only" where it does not change backend scope.
- Replace beginner-facing "Outsource" with "final output root" or "final library root" in docs/UI copy where possible.
- Define "LocalBase" as "local runtime state folder" at the point of first use.
- Define "scratch" as "local working copy area; sources are copied here before processing".
- Explain "remux" as "copy streams into the output container without video re-encode" near route results.
- Explain "encode" as "create a new video stream according to policy" near route results.
- Glossary cleanup: the Encode/Evidence-only text appears mispositioned, and browser smoke count history is inconsistent across active docs.

## Onboarding Improvements

1. Add a single "First Successful File" path that starts with `verify-env.bat`, then `setup.bat` or Settings Guided Setup, then `start-api-and-browser.bat`, then Queue Scan Sources, then Launch Run Once.
2. Add a Home first-run checklist with four states: environment verified, settings saved/reloaded, queue scan current, launch preflight ready.
3. Put "what this proves" labels beside verification actions: environment readiness, shell readiness, UI smoke readiness, media-policy proof, real-media proof.
4. Make Settings Guided Setup the recommended first-time configuration path, and position Libraries as profile tuning after initial roots work.
5. Provide one "first media sample" row walkthrough: route decision, audio/subtitle decision, output proof, completed manifest, and what to inspect if it parks.
6. Add a restart recovery checklist to Home or Diagnostics: active work, partial outputs, pending manifests, completed manifest, latest failure, safe next action.

## UI Copy And Docs Recommendations

- Add a persistent scope sentence beside Start Pipeline and Drain Parked Outputs: "Display filters and selected rows do not change backend scope."
- Rename Launch mode label `Publish Parked` to `Drain Parked Outputs` or add that phrase directly in the button text.
- On Completed Output, separate "Review completed evidence" from "Promote to final library" visually and verbally.
- On Pending Publish, keep one dominant status line: `Safe to drain`, `Review blockers`, or `Do not drain`.
- On Rename, replace the no-checked-row fallback with an explicit scope control: `Checked rows only` or `All applicable rows`.
- On Queue, show last scan time, snapshot age, scan status, and whether rows are authoritative.
- On Settings, show an active/draft banner: `Draft changes only`, `Preview passed`, `Saved and active`, or `Reload required`.
- In launcher docs, state that `start-tauri-preview.bat -CheckOnly` is shell prerequisite validation only, not media processing readiness.
- Update stale Tauri/Desktop docs that say network lifecycle is not exposed or use outdated package path wording.
- Add one docs page that maps actions to mutation class: read-only evidence, shell-open/dialog, queue-state write, config write, process launch, filesystem rename, pending drain, final promotion, shutdown.

## Operator Safety Recommendations

- Keep backend ownership of media policy, queue mutation, settings save, rename apply, pending drain, final promotion, rerun, and shutdown.
- Keep strict JSON confirmation and duplicate-command guards for all high-risk routes.
- Treat any change to FFmpeg, remux/encode decisions, subtitles, audio, publish/drain, source/scratch/output movement, cleanup, or restart recovery as high validation.
- Make source immutability visible in first-run setup: source roots are read/probe/copy only by default.
- Do not let source inventory rows become launchable until backend curation produces authoritative queue rows.
- Require explicit dry-run proof before rerun/retry workflows in UI and scripts.
- Require explicit row scope for rename and final-library promotion.
- Keep pending-publish drain manifest-based and blocked when hidden/review rows exist.
- Make close-readiness fail closed: if backend readiness cannot be read, the UI should not imply safe close.

## Quick Wins

| Recommendation | Effort | Impact |
|---|---|---|
| Add a concise first-run checklist to README and Home. | S | High |
| Rename or clarify `Publish Parked` as `Drain Parked Outputs`. | S | High |
| Add "what this proves" readiness labels to verify-env, Tauri CheckOnly, release test, browser smokes, and real-media validation docs. | S | Medium |
| Add a Settings banner for draft/preview/saved/reload state. | S | Medium |
| Add "filters do not change backend scope" copy directly beside Start and Drain controls. | S | High |
| Fix stale Tauri/Desktop network lifecycle wording and glossary drift. | S | Medium |
| Add a Diagnostics beginner preset: "Investigate selected failed row". | M | Medium |

## Larger Product Work

| Recommendation | Effort | Impact |
|---|---|---|
| Build a guided first-job workflow that moves from setup to scan to route proof to launch to completed evidence. | L | High |
| Build a row-centered failure resolution drawer that gathers manifest, logs, route reason, reconciliation, recovery plan, and rerun dry-run. | L | High |
| Build a one-file route explanation packet for remux/encode/audio/subtitle decisions. | M | High |
| Build a restart recovery dashboard that consolidates stale ActiveJobs, partial output, pending manifests, failures, and safe next action. | L | High |
| Replace rename no-check fallback with explicit scope selection and an optional undo/rollback plan artifact. | M | High |
| Add role/experience modes so first-time operators see Home, Settings, Queue, Launch, Completed, Pending, Diagnostics first, with advanced surfaces collapsed. | L | Medium |

## Limitations

- This audit did not launch the Local API, browser WebView, or Tauri shell.
- This audit did not run Playwright/browser smokes or live UI click paths.
- This audit did not process media, scan actual source roots, rename files, save settings, promote completed outputs, drain pending publish, or test restart recovery.
- Findings are grounded in active docs, script behavior, UI partials, and route inventories; live runtime behavior should be verified before implementing UX changes.
- The repository had many pre-existing dirty and untracked files unrelated to this audit. This report and its change packet intentionally do not absorb or modify them.
