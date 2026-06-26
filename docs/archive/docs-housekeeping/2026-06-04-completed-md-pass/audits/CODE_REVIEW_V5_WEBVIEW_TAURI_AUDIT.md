# CODE_REVIEW_V5_WEBVIEW_TAURI_AUDIT

Generated: 2026-05-20

Scope: static, read-only audit of the V6 repository with focus on the V5/V6 WebView/Tauri transition, Python local API, PowerShell pipeline, launchers, process lifecycle, state/manifests, release packaging, and tests. I did not modify source code and did not run the full test/smoke suite during the initial audit pass.

Remediation status update, 2026-05-20:

- Closed and validated: release artifact exclusions, shared release policy manifest/module, V6 reliability gate execution, legacy reliability monolith archival with a V6 compatibility wrapper, non-stale repo hygiene gate, active-doc removed-shell wording guard, browser launcher token-on-by-default policy, Tauri token bootstrap hardening, header-only API token acceptance, unauthorized POST body draining, schedule watcher generation guard, native process catch-time cleanup, FFmpeg progress priority evidence/stale polling cleanup, sidecar overwrite fallback, psutil-unavailable close-readiness fail-closed behavior, active legacy desktop-shell UI wording, server/contract public-surface wording, backend-owned rename undo manifest location, rename path authority policy, current network lifecycle design-only/read-only posture, clearer Tauri unverified-close recovery warning copy, local API/Tauri CSP security headers, and non-daemon Local API/coordinator request-handler shutdown posture.
- Current validation: release self-test with required tests passed, package-mode build verification passed, release dry-run passed, active V6 reliability wrapper passed, V6 WebView reliability gate passed, repo hygiene gate passed, active docs reference checks passed, focused network/read-only contract tests passed, Tauri library/scaffold tests passed, focused process/schedule/close-readiness Python unit tests passed, and Local API/coordinator request-handler shutdown posture tests passed.
- Still external/human gates, not stale local protected gates: PG-3 clean-machine package-mode launch, representative real-media validation, real Windows/UNC sidecar stress testing, and any behavioral change to force-close workflow semantics.

## 1) Executive Summary

The current architecture is pointed in the right direction: Tauri/WebView is a shell, the Python local API is the command/query boundary, and the PowerShell pipeline remains the owner of media processing, filesystem mutation, FFmpeg/ffprobe/mkvmerge execution, pending publish, sidecars, completed manifests, and stop/pause flags. The frontend mostly behaves as a read-only evidence and command surface. It does not directly touch the filesystem; meaningful actions go through backend `POST /api/...` routes.

The highest risk is not the basic WebView authority boundary. The highest risk is release and transition hygiene:

| Severity | Finding | Current risk | Status |
| --- | --- | --- | --- |
| BLOCKER | Release packaging does not exclude root verification/runtime artifacts such as `CodexVerification\*`, generated audit files, and possible root runtime clutter. | Packages can leak local paths, bootstrap tokens, operator validation logs, or stale agent artifacts. | Fixed; release dry-run and release self-test now validate these exclusions. |
| BLOCKER | V6 release self-test skipped reliability regression checks when the removed desktop entrypoint was absent. | A package could pass the release gate while the old reliability suite was silently bypassed. | Fixed; the V6 WebView reliability gate runs directly. |
| HIGH | Local API token bootstrap was served inside unauthenticated `/` HTML. | Any local process that discovered the port could fetch the page and obtain the bearer token. | Fixed for Tauri; the public Tauri index omits the token and Rust injects it through WebView initialization. Browser launcher token auth remains explicit browser-mode behavior, with query-string tokens rejected. |
| HIGH | Rename apply rebuilds plans backend-side, but standalone paths can be outside configured media roots. | Without a policy, a tokened request could target arbitrary accessible media paths. | Fixed with an explicit standalone policy: backend injects configured roots, strips spoofable authority keys, blocks outside-root apply unless `allow_outside_configured_roots` is set, and writes undo manifests under backend runtime state. |
| HIGH | Schedule-stop watcher state has a stale-thread overwrite race. | Close-readiness and schedule evidence can report an old process state after a new watcher is armed. | Fixed; watcher state carries a generation id and stale generations cannot overwrite current state. |
| HIGH | PowerShell `Invoke-NativeProcess` can return from a broad catch after `Process.Start` without killing an already-started child. | Rare exceptions after child start can leak FFmpeg/mkvmerge/robocopy-like work. | Fixed; catch path now attempts process-tree cleanup and has a unit gate. |

Overall health: the backend ownership model is strong. Active WebView/package legacy desktop fallback wording has been cleaned up; any remaining legacy desktop-shell references should be treated as historical/vendor-only unless a fresh active-source scan proves otherwise.

## 2) Current Architecture As Understood From The Code

Launch paths:

- Browser/dev path: `Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat` launches `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1`, which starts `python -m mediapipeline_desktop_app.local_api_main` on fixed port `8765` with token auth enabled by default; `--no-token` is gated behind the explicit `-NoTokenDevMode` switch.
- Tauri preview path: `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat` launches `DesktopApp\tauri_shell\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1`, checks Node/npm/Cargo/Python, then runs `npm run dev`.
- Tauri runtime path: `DesktopApp\tauri_shell\src-tauri\src\lib.rs:49-65` resolves the desktop root, starts the Python backend, validates health/contract/web UI, and opens a WebView pointed at the backend URL.

Process and authority model:

- Rust owns shell lifetime only. `backend_process.rs:112-188` starts Python, captures stdout/stderr, reads the bootstrap URL/token, validates routes, and stores the child process.
- Python local API owns operator commands. `local_api_main.py:202-215` creates `LocalApiServer` with resolved paths, command journal, and shell surface.
- The application facade is the UI-neutral boundary. It owns locks for process launch/control, maintenance, rename apply, settings save, sample validation, and schedule save/watch state.
- PowerShell pipeline remains the media mutation owner. `Pipeline\MediaPipeline.ps1` loads modules, resolves bundled tools, writes progress/events/state, handles flags, runs FFmpeg/ffprobe/mkvmerge, writes sidecars/completed manifests, and drains pending publish.
- Frontend JS is a command client. `apiClient.js:1-10` reads `window.MEDIA_PIPELINE_BOOTSTRAP` and attaches the bearer token to API calls. UI state in `localStorage` is presentation-only.

Important data/control surfaces:

- Launch/start: `/api/pipeline/start` -> facade -> Python process service -> PowerShell pipeline.
- Control: `/api/pipeline/control` writes backend-owned pause/stop/rescan/kill controls.
- Settings: `/api/settings/preview-patch` previews, `/api/settings/save-patch` validates, backs up, atomically writes PSD1, and reloads.
- Rename: `/api/rename/preview` builds a plan; `/api/rename/apply` requires `confirm_apply`, rebuilds the plan, filters `selected_sources`, writes an undo manifest, renames files/sidecars, updates sidecar metadata, and attempts rollback on failure.
- Pending publish: frontend evidence is read-only; actual drain is `/api/pipeline/start` with `mode=drain_pending_pushes`, which invokes the existing PowerShell drain path.
- Close: Tauri asks `/api/backend/close-readiness`; unsafe closes require confirmation, then `/api/backend/shutdown` can force active-work cleanup.
- Release: `Build-MediaPipelineRemuxEncodeAIO-Release.ps1` copies a filtered tree and `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` runs package verification.

## 3) Highest-Risk Issues Ranked By Severity

Status note: this table preserves the initial audit findings. Use the remediation-status update at the top of this file for current closed/open state.

| Rank | Severity | Issue | Why it matters | What could go wrong if ignored | Likely files | How to test | Safe for AI implementation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | BLOCKER | Release packaging could include root verification/runtime artifacts. | Release packages must strip local state, tokens, logs, validation output, and generated audit clutter. | A shared package could include `CodexVerification` logs with absolute local paths and bootstrap tokens, plus generated housekeeping/audit files. | `Pipeline\Modules\ReleasePolicy.ps1`, `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`, `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` | Release policy, release dry-run, and release self-test validate `CodexVerification`, root `*_AUDIT.md`, root catalog CSV/JSON, `LocalBase`, root logs/state, and quarantine output exclusions. | Fixed. |
| 2 | BLOCKER | V6 release self-test skipped reliability checks when the removed desktop entrypoint was absent. | Removed shell code should not disable backend reliability gates. | Release self-test could pass while process lifecycle, state hygiene, pending publish, or backend contract regressions were not checked. | `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`, `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`, `Pipeline\Tests\Legacy\Invoke-LegacyDesktopReliabilityRegressionChecks.ps1` | Run release self-test on a V6 bundle with `-RequireTests`; it should run backend/app reliability checks or fail loudly. | Fixed; active wrapper now runs V6 checks by default. |
| 3 | HIGH | Public index bootstrapped the API token. | Token protection was weakened when the token was embedded in unauthenticated HTML. | A local process could discover the port, fetch `/`, extract the token, then call mutation routes. Browser dev mode still requires explicit opt-in. | `static_files_policy.py`, `lib.rs`, `Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1`, `test_tauri_shell_scaffold.py`, `test_application_facade_local_api.py` | Tauri public index omits the token, Rust injects it through WebView initialization, query-string tokens are rejected, and packaged/default browser launch keeps token auth enabled. | Fixed. |
| 4 | HIGH | Rename apply accepted standalone paths without a clearly enforced authority policy. | Backend rebuilds and validates plans, but standalone paths needed explicit operator intent. | A tokened request could otherwise rename accessible media outside configured source/output roots. | `facade_rename_policy.py`, `facade_rename.py`, `command_payloads_rename.py`, `service_rename_apply_runner.py`, `test_application_facade_rename.py`, `test_application_facade_local_api.py` | Focused rename tests prove outside-root apply is blocked until explicitly confirmed and Local API strips spoofed backend authority keys. | Fixed; standalone outside-root rename remains possible only with explicit extra confirmation. |
| 5 | HIGH | Schedule-stop watcher had a stale-thread state overwrite race. | Close-readiness depends on watcher state to decide whether work is safe to close. | A canceled old watcher could overwrite the state of a newly armed watcher after the join timeout. | `application\schedule_stop_watcher.py`, `test_schedule_stop_watcher.py` | Watcher generation tests prove stale generations cannot overwrite current state; close-readiness exposes the active generation. | Fixed. |
| 6 | HIGH | `Invoke-NativeProcess` did not kill a child in the broad catch after `Process.Start`. | Native tools are long-running and expensive; wrapper errors should not leave work detached. | FFmpeg/mkvmerge/robocopy-like process could keep running after wrapper failure. | `Pipeline\Modules\Native.ps1`, `Pipeline\Tests\Unit\Invoke-NativeProcessCleanupChecks.ps1` | Native cleanup checks simulate catch-time cleanup and verify process-tree cleanup before returning failure. | Fixed. |
| 7 | MEDIUM | Active UI/tests referenced removed desktop-shell fallback wording. | Operator guidance should not point to a non-existent shell. | The operator could follow dead-end instructions, and release/test logic could preserve old assumptions. | WebView assets, worksheet scripts, and test fixtures touched during remediation | Active-source stale shell scan excluding bundled runtimes/vendor/docs should return zero active hits or only explicitly historical hits. | Fixed for active wording; historical docs remain archive/reference only. |
| 8 | MEDIUM | FFmpeg progress event used priority before it was computed; stale poll code referenced undefined `$lineTask`. | Evidence panels should reflect actual process priority and avoid dead/refactored logic. | Diagnostics could report `inherit` even when priority was requested; future edits could revive broken duplicated stderr handling. | `Pipeline\Modules\FfmpegProgress.ps1`, `Pipeline\Tests\Invoke-V6WebViewReliabilityChecks.ps1` | V6 reliability gate asserts priority is mapped before `tool_started` and `$lineTask` is absent. | Fixed. |
| 9 | MEDIUM | External process detection failed open when `psutil` was unavailable. | Duplicate launch and close-readiness safety depend on related process discovery. | If psutil was missing/broken, externally launched package PowerShell jobs could be invisible to Python guardrails. | `app/processes/kill.py`, `application\facade_process_guard.py`, focused close-readiness tests | psutil-unavailable tests prove process detection degrades visibly and close-readiness fails closed instead of silently ignoring related work. | Fixed. |
| 10 | MEDIUM | Sidecar replace fallback temporarily removed the destination file before remediation. | Sidecars are the durable truth for completed output evidence. | The old delete+rename fallback could let concurrent readers see no sidecar during replacement. | `Pipeline\Modules\Sidecar.ps1`, `Pipeline\Tests\Unit\Invoke-SidecarWriteSafetyChecks.ps1`, `Pipeline\Tests\Invoke-V6WebViewReliabilityChecks.ps1` | Local guard now verifies overwrite move without explicit sidecar delete; real Windows/UNC stress testing is still needed for the actual storage profile. | Fixed locally; UNC stress remains operator validation. |

## 4) Correctness Bugs With File Paths And Line References

1. Fixed after audit: release exclusion policy now lives in `Pipeline\Modules\ReleasePolicy.ps1` and covers `CodexVerification\*`, `LocalBase\*`, docs-housekeeping quarantine output, root audit/report clutter, logs, and state artifacts. Build and self-test both consume the shared policy.

2. Fixed after audit: V6 release self-test no longer skips active reliability checks when removed desktop-shell `app.py` is absent; the active V6 wrapper runs by default.

3. Fixed after audit: Tauri-mode `GET /` still serves startup HTML publicly, but `static_files_policy.py` now withholds the bearer token for `shell_surface="tauri"` and `lib.rs` injects it into the WebView through `initialization_script`. Browser mode still uses the index bootstrap intentionally for the browser launcher.

4. Fixed after audit: rename preview/apply now uses a backend-injected authority policy. Apply blocks outside configured roots unless the operator sends explicit outside-root confirmation, strips spoofable request keys in the Local API layer, and writes undo manifests under backend-resolved runtime state.

5. Fixed after audit: `DesktopApp\mediapipeline_desktop_app\application\schedule_stop_watcher.py` now uses watcher generations so stale watcher threads cannot overwrite current state.

6. Fixed after audit: `Pipeline\Modules\Native.ps1` now attempts process-tree cleanup when the broad catch runs after a child process has started.

7. Fixed after audit: `Pipeline\Modules\FfmpegProgress.ps1` now maps process priority before emitting `tool_started`.

8. Fixed after audit: `Pipeline\Modules\FfmpegProgress.ps1` no longer carries the stale `$lineTask` polling branch.

9. Fixed after audit: `DesktopApp\mediapipeline_desktop_app\api\server.py` now describes the command-capable, token-protected API.

10. Fixed after audit: `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\contractView.js` now distinguishes public API routes from the separate startup HTML/assets bootstrap surface, and Tauri no longer receives the bearer token through public index HTML.

## 5) Stale Legacy Desktop-Shell/V3/V4 Code Or Assumptions

Initial audit stale-reference status after remediation:

- Fixed: `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` no longer gates active V6 reliability checks on the removed `app.py` shell.
- Fixed: `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` is now a V6 compatibility wrapper; historical desktop-shell assertions moved to `Pipeline\Tests\Legacy\Invoke-LegacyDesktopReliabilityRegressionChecks.ps1` and require `-RunLegacyDesktopChecks`.
- Fixed: WebView sample-validation, network, schedule, and cross-page context copy no longer direct operators to removed desktop-shell fallbacks.
- Fixed: real-media validation worksheet generation and parsing now use V6 launch-surface wording.
- Fixed: active backend network comments/docstrings no longer describe removed desktop-shell scheduling as the current architecture.

Bundled Python runtime references to legacy GUI libraries are vendor/runtime files and are not evidence that the application shell still uses a removed desktop shell.

## 6) Backend Authority And Safety Boundary Review

Strengths:

- Command routes are explicit and centralized in `routes_command.py`.
- The command contract in `contract_command.py` is unusually helpful. It documents command effects, expected request keys, and no-mutation boundaries.
- Queue priority and file overrides use `queue_source_path_policy.py:31-43`, which requires absolute paths under configured `SourceMovies`/`SourceTV`.
- Settings save requires `confirm_save`, validates the merged config, creates a backup, and uses atomic write (`facade_settings_patch.py:29-65`, `service_config_save_runner.py:25-53`, `service_utils.py:81-93`).
- Rename apply requires `confirm_apply`, rebuilds the backend plan, filters selected rows, rejects blockers, writes an undo manifest, and attempts rollback (`facade_rename.py:50-81`, `service_rename_apply_runner.py:20-115`).
- Close-readiness checks related processes, active jobs, progress files, audit progress, and schedule watcher state before shutdown.

Gaps:

- Fixed after audit: rename path authority is now explicit. Configured-root rename is normal; standalone outside-root rename requires an extra confirmation flag and Local API strips request-supplied backend authority keys.
- Fixed after audit: Tauri public index HTML no longer carries the bearer token; Rust injects it into the WebView initialization script. Browser-mode bootstrap remains a deliberate launcher compatibility path.
- Fixed after audit: `--no-token` remains a browser-dev-only switch and packaged/default browser launch keeps token auth enabled.
- Fixed after audit: psutil-unavailable close-readiness now fails closed/degrades visibly instead of silently ignoring related processes.
- The close/shutdown path can force-kill app-owned and related processes after user confirmation. That is reasonable, but the UI should clearly label recovery expectations because interrupted pending publish/sidecar work requires operator verification.

## 7) Frontend/WebView/Tauri Review

Strengths:

- Frontend mutation goes through `apiPost`. I did not find JS code directly renaming, publishing, deleting, saving config, or touching media files.
- `apiClient.js:54-72` attaches token headers and disables cache for API calls.
- Queue launch UI explicitly states that selected queue rows and filters do not scope backend launch. `queueView.launch.js` has substantial scope-warning logic.
- Pending publish UI states that filters, selected rows, recovery-plan rows, and rendered caps do not narrow backend drain scope (`pendingPublishView.drain.js:96-154`).
- Rename UI posts `confirm_apply` and `selected_sources` only after readiness and browser confirmation (`renameView.js:1213-1245`).
- Tauri shell capability set is small: `src-tauri\capabilities\default.json` contains only `core:default`.

Gaps:

- Fixed after audit: `tauri.conf.json` no longer leaves `csp` null, and Local API responses add a Content Security Policy plus `nosniff` and `no-referrer` headers. The policy still permits inline/eval script because the current WebView bootstrap and Tauri debug automation use those paths; treat a stricter nonce/external-bootstrap policy as a future hardening item, not a backend-authority change.
- Tauri opens `WebviewUrl::External(url)` (`lib.rs:59`). That is workable, but it means the same public localhost URL model is used by both Tauri and browser dev.
- Fixed after audit: active UI text no longer points operators to removed desktop-shell fallback flows.
- Fixed after audit: contract/public-surface wording now distinguishes public startup HTML/assets from token-protected API routes, and Tauri token bootstrap no longer relies on public index HTML.

## 8) Python Local API Review

Strengths:

- `LocalApiServer` binds to `127.0.0.1` by default and uses a per-run random token unless provided (`server.py:35-58`).
- Request body parsing rejects oversized JSON and non-finite JSON values (`http_helpers.py:56-83`).
- Asset path resolution blocks traversal/backslashes and verifies paths stay under the asset root (`http_helpers.py:116-128`).
- Command journal writes bounded summaries only and uses temp-file replace with fsync (`command_journal.py:66-96`).
- `BackendResolvedState` reload is locked (`local_api_main.py:21-40`), which keeps settings reloads from partially updating resolved state.

Gaps:

- Fixed after audit: the server docstring now describes the command-capable, token-protected read/command API surface.
- Fixed after audit: auth no longer accepts query-string tokens; token use is header-only.
- Fixed after audit: Tauri public-index token bootstrap is hardened; browser-mode index bootstrap remains a deliberate launcher compatibility path.
- Fixed after audit: Local API request-handler threads are no longer daemonized, so backend shutdown does not abandon in-flight command handlers before their cleanup/journaling path can finish.

## 9) PowerShell Pipeline Review

Strengths:

- `MediaPipeline.ps1` continues to own actual media work and pipeline modes, including `drain_pending_pushes`.
- Native command execution generally uses `ProcessStartInfo.ArgumentList`, stdout/stderr redirection, polling, stop flag checks, timeout checks, and bounded drains (`Native.ps1:330-430`).
- Native process defaults are conservative: ffprobe 30s, ffmpeg 86400s, mkvmerge 21600s, python 3600s, OCR 1800s.
- Disk copy logic uses staging/partial/backup semantics and `File.Replace` in important paths (`Disk.ps1:363-478`).

Gaps:

- Fixed after audit: `Invoke-NativeProcess` now attempts catch-time cleanup if `$proc` exists and is still running.
- Fixed after audit: `FfmpegProgress.ps1` now emits priority evidence after priority mapping and removed the stale duplicated progress polling branch.
- Fixed after audit: Sidecar fallback no longer uses delete+rename. `Move-SidecarTempIntoPlace` uses same-directory overwrite move, and both `Invoke-SidecarWriteSafetyChecks.ps1` and the V6 reliability gate guard that no explicit sidecar delete is reintroduced. Real Windows/UNC storage stress testing remains separate operator validation.
- Fixed after audit: release policy now includes generated root artifacts, verification output, local runtime state, and docs-housekeeping quarantine folders.

## 10) Process Lifecycle, Cancellation, Timeout, And Logging Review

Strengths:

- Rust drains backend stderr and eventually stdout after bootstrap (`backend_process.rs:252-284`).
- Rust validates backend health, route contract, and web UI before building the window (`backend_process.rs:163-183`).
- Tauri close calls close-readiness first and only then requests backend shutdown (`lib.rs:72-82`, `backend_process.rs:94-109`).
- Python process services track app-owned children and have force-kill helpers with `taskkill /T /F` on Windows (`app/processes/kill.py`).
- The schedule-stop watcher writes the backend stop flag at the schedule boundary rather than having the frontend mutate flags.

Gaps:

- Fixed after audit: schedule watcher state now has a generation guard so stale watcher threads cannot overwrite current evidence.
- Fixed after audit: related-process discovery degradation is surfaced and close-readiness fails closed when process detection is unavailable.
- Fixed after audit: native process broad catch now cleans up already-started children.
- Fixed after audit: Local API and coordinator request-handler threads are non-daemon while their listener threads remain daemonized, preserving process exit flexibility without abandoning command handlers during normal shutdown.
- Tauri shutdown posts `force_active_work_shutdown=true` after close confirmation. Fixed after audit: the prompt now treats failed close-readiness checks as unsafe and repeats the same recovery warning used for known active work. Any behavioral change beyond copy/tests should still be treated as a dangerous recovery-path decision.

## 11) State, Manifest, Sidecar, And Pending-Publish Review

Strengths:

- Runtime state is moving under `LocalBase\State`, with tests and reliability checks around state layout.
- Pending publish scan is read-only in Python and flags duplicates/missing payloads (`service_pending_publish.py:90-199`).
- Pending publish drain is not scoped by frontend filters or selected rows; frontend text repeatedly says the backend owns all parked payload validation.
- Rename writes an undo manifest before applying operations and updates sidecar metadata after rename.
- Settings, command history, and many Python state writes use atomic replace helpers.

Gaps:

- Completed manifest append is best-effort after sidecar write. That may be correct, but UI trust should continue to treat sidecar/output evidence as stronger than manifest-only evidence.
- Fixed after audit: Sidecar write fallback no longer explicitly removes the existing sidecar before replacement. The remaining risk is storage-specific behavior on the real Windows/UNC share profile, which still needs operator-run stress validation.
- Fixed after audit: rename undo manifests are routed through the backend-resolved runtime state root when `LocalBase\State` is available, with fallback behavior kept only for unavailable state roots.
- Pending publish recovery planning is dry-run only, which is good, but there is no exposed backend repair transaction yet. Keep it that way until copy/move/delete transaction semantics are explicit and tested.

## 12) Settings, Config, And Release Packaging Review

Settings/config:

- Preview/save split is good.
- `confirm_save` is required (`facade_settings_patch.py:29-32`).
- Save validates before write and creates backups (`service_config_save_runner.py:34-53`).
- Raw token handling appears intentionally guarded by settings builders and raw triage text.

Release packaging:

- Fixed after audit: release exclusion logic is shared through `Pipeline\Modules\ReleasePolicy.ps1`, and the release builder writes the policy metadata into the release manifest.
- Fixed after audit: `CodexVerification`, `LocalBase`, root generated reports/audits, logs, state files, and docs-housekeeping quarantine output are default exclusions unless intentionally building an engineering handoff where allowed options include more material.
- Fixed after audit: release self-test imports the same policy module and verifies hygiene through shared rules.
- Fixed after audit: V6 release self-test runs the active V6 reliability wrapper by default instead of depending on the removed desktop-shell entrypoint.

Current release exclusion classes:

- Root verification/runtime: `CodexVerification\*`, `LocalBase\*`, root `RunLogs\*`, root `*.log`, root `*.state.json`.
- AI/generated audit artifacts: `DOCS_HOUSEKEEPING_AUDIT.md`, `docs_housekeeping_catalog.*`, `DOCS_HOUSEKEEPING_MOVE_PLAN_BLOCKED.md`, `CODE_REVIEW_*_AUDIT.md`, `*_POST_MOVE_REPORT.md`, unless explicitly included as dev docs.
- Quarantine/archive review folders created by documentation housekeeping, unless explicit `-IncludeDevDocs`.
- Tokens/startup logs wherever they are generated.

## 13) Test And Smoke Coverage Review

Observed coverage inventory:

- `DesktopApp\tests`: large Python unittest suite, including API contract, static files, Tauri scaffold, WebView browser smoke helpers, settings patch smoke, rename smoke, pending publish, network modules, path resolution, and process services.
- `Pipeline\Tests`: PowerShell integration/regression checks, including tool integration, end-to-end smoke, adversarial force-kill encode checks, and runtime state hygiene checks.
- `SmokeTests`: many no-mutation browser/local API smoke scripts with explicit boundary text.

Strengths:

- There are explicit frontend mutation boundary tests (`test_webview_frontend_mutation_boundary.py`) and read-only network boundary tests.
- Local API lifecycle smoke checks token enforcement and shutdown rejection around unsafe close-readiness.
- Settings patch smoke actually exercises preview, denied save, confirmed save, backup existence, reload, and command history on temporary config.
- Rename frontend smoke checks duplicate-target blockers and that blocked previews do not post `/api/rename/apply`.

Gaps:

- Fixed after audit: tests now assert Tauri shell token injection and backend WebView validation rejects token leakage in public index HTML; browser-mode static tests still assert the explicit browser bootstrap path.
- Fixed after audit: release tests cover `CodexVerification`, root generated audit/report artifacts, root runtime logs/state, docs-housekeeping quarantine output, and root `LocalBase` through the shared release policy module.
- V6 release self-test reliability skipping was fixed by running the V6 compatibility wrapper by default.
- Rename off-root adversarial coverage now exists for configured-root blocking, explicit outside-root confirmation, backend-owned root injection, and spoofed authority-key stripping. UNC/junction behavior can still be expanded if real filesystem testing shows a gap.
- Fixed after audit: schedule watcher generation-race tests exist.
- Fixed after audit: native process catch-leak tests exist.
- Fixed after audit: psutil-unavailable/fail-closed tests exist.
- Active-code stale legacy desktop-shell wording scan is now covered, excluding bundled Python runtime/vendor files.
- Fixed after audit: active-docs reference checks now block reintroducing old removed-shell framework wording in current non-archive guidance and the Tauri shell README, while leaving generated audits and change-history logs intact.
- Fixed after audit: frontend static coverage now pins Settings Save Patch, Launch Start, and Pending Publish drain result rendering so backend rejections stay visibly blocked/failed and refresh/persistence evidence is tied to `result.ok`.

## 14) Maintainability And Refactor Opportunities

- Keep `Invoke-ReliabilityRegressionChecks.ps1` as the V6 compatibility wrapper and move any future legacy desktop-shell assertions into `Pipeline\Tests\Legacy` behind explicit switches.
- Fixed after audit: release exclusion policy is now centralized in `Pipeline\Modules\ReleasePolicy.ps1`, and both build and self-test consume it.
- Fixed after audit: repo hygiene now distinguishes default leak checks from opt-in strict build-artifact cleanup, so ignored Tauri `target`/`node_modules` output does not make the normal V6 reliability wrapper stale or noisy.
- Fixed after audit: `Docs\architecture\LOCAL_API_SECURITY_SURFACE.md` documents localhost auth, the browser no-token dev path, public startup assets, security headers, Tauri token bootstrap, and the WebView mutation boundary.
- Fixed after audit: active network lifecycle copy now says lifecycle routes are not promoted and the Network page remains read-only/design-only.
- Add a dedicated `PathAuthorityPolicy` helper for mutation routes. Queue already has root policy; rename/settings/open commands should have similarly explicit policy objects.
- Fixed after audit: schedule watcher state now carries a generation id and exposes it in close-readiness/schedule payloads for diagnostics.
- Normalize all timestamp/undo/runtime artifacts under `LocalBase\State` where possible so cleanup/release/test rules can be simple.

## 15) Dead Code And Duplication Candidates

Initial candidates and current status:

- Fixed after audit: the stale `$lineTask` polling branch was removed from `FfmpegProgress.ps1`, and the V6 reliability gate guards against reintroducing it.
- Fixed after audit: the removed desktop entrypoint gate is no longer active V6 release logic; the active wrapper runs V6 WebView/backend reliability checks by default.
- Fixed after audit: historical desktop architecture assertions live under `Pipeline\Tests\Legacy` behind explicit legacy switches.
- Fixed after audit: active WebView fallback copy was rewritten for the V6 WebView/Tauri reality.
- Fixed after audit: active documentation now has a guard against old removed-shell framework wording in current guidance.
- Fixed after audit: active network comments/docstrings no longer contain removed-shell scheduling wording in `DesktopApp\mediapipeline_desktop_app\network`.
- Fixed after audit: root housekeeping/audit artifacts are excluded by release policy and package verification.

## 16) Quick Wins

Status as of 2026-05-20: the initial quick-win list is closed and guarded.

1. [x] Add release exclusions and self-test absence checks for `CodexVerification`, root generated audit files, root runtime logs/state, and `LocalBase`.
2. [x] Replace active UI/operator text that says legacy desktop fallback with V6-accurate language.
3. [x] Change release self-test so missing `app.py` does not skip all reliability checks.
4. [x] Move `$priorityClassEnum` calculation before `tool_started` in `FfmpegProgress.ps1` or write the event after priority mapping.
5. [x] Remove the stale `$lineTask` branch in `FfmpegProgress.ps1`.
6. [x] Add catch-time process cleanup in `Native.ps1`.
7. [x] Add a schedule watcher generation id.
8. [x] Update `server.py` docstring to reflect command-capable API.
9. [x] Update contract UI wording to say public web assets are separate from protected API routes.
10. [x] Make Local API and coordinator request-handler threads non-daemon for normal shutdown cleanup.

## 17) High-Confidence Fixes Safe To Implement Now

Status as of 2026-05-20: these high-confidence fixes have been implemented and tested.

- Release exclusion/self-test patch for generated artifacts and `CodexVerification`.
- Active legacy desktop-shell wording cleanup in UI strings, worksheet labels, and tests that are only checking text.
- `Native.ps1` catch cleanup for already-started child processes.
- `FfmpegProgress.ps1` priority/logging fix and stale poll removal.
- `ScheduleStopWatcherManager` generation guard.
- `server.py` docstring update.
- Local API and coordinator request-handler thread shutdown posture.
- Tests for the above small fixes.

These are bounded, preserve backend authority, and should not require broad architecture changes.

## 18) Risky Fixes That Need Human Approval

- Fixed after audit: Tauri token bootstrap now passes the token from Rust to the WebView without serving it in public HTML. A broader one-time nonce/static-asset-auth redesign remains optional, not a current blocker.
- Fixed after audit: rename path authority allows standalone operator folders only with explicit outside-root confirmation, strips request-supplied backend authority keys in the Local API layer, and keeps undo manifests under backend-resolved runtime state.
- Closed as current design: Network lifecycle start/stop/reclaim/release/abort remains read-only/design-only in WebView. Promotion remains a future feature and still requires backend dry-runs, cleanup transactions, command journal behavior, and recovery tests before any mutation route is added.
- Force-close semantics. Tauri currently force-cleans active work after unsafe close confirmation. Fixed after audit: unverified close-readiness now gets explicit unsafe/recovery wording. Any behavioral change still needs operator workflow approval because it affects shutdown recovery behavior.
- Sidecar replacement semantics on Windows/network shares. The local delete-gap fallback was improved and guarded, but it still needs stress testing against the actual storage targets before treating the share behavior as proven.

## 19) Prioritized Remediation Checklist

Small chunks:

- [x] Add `CodexVerification\*`, root generated audit/report files, root logs/state, and `LocalBase\*` to release exclusions.
- [x] Add release self-test absence checks for the same paths.
- [x] Replace active legacy desktop-shell fallback wording in WebView JS/HTML and worksheet scripts.
- [x] Update `server.py` docstring and contract UI public-route wording.
- [x] Fix `FfmpegProgress.ps1` priority event ordering.
- [x] Remove or rewrite stale `$lineTask` poll branch.
- [x] Add targeted tests for each quick win.
- [x] Add Local API/Tauri CSP security headers while preserving current bootstrap/debug automation compatibility.
- [x] Add frontend static coverage proving Settings Save Patch, Launch Start, and Pending Publish drain render backend rejections as blocked/failed rather than success.
- [x] Make Local API request-handler threads non-daemon so shutdown does not abandon in-flight command cleanup/journaling.
- [x] Make coordinator request-handler threads non-daemon so shutdown does not abandon claim/done/log handler cleanup.

Medium chunks:

- [x] Split `Invoke-ReliabilityRegressionChecks.ps1` into a V6 backend/process/state wrapper and archived legacy desktop-shell checks.
- [x] Make V6 release self-test run backend reliability checks even when `app.py` is absent.
- [x] Add schedule watcher generation id and stale-thread tests.
- [x] Add `Invoke-NativeProcess` child cleanup in broad catch and a simulated process-leak test.
- [x] Add psutil-unavailable close-readiness/degraded-health tests.
- [x] Add active-source stale legacy desktop-shell scan test excluding bundled runtime/vendor/docs.
- [x] Add active-doc stale removed-shell wording guard and refresh current docs that still described removed UI-framework ownership.
- [x] Make repo hygiene usable as a default reliability gate by moving ignored Tauri build-output checks behind explicit strict mode.
- [x] Replace the sidecar overwrite fallback delete gap with overwrite move and guard it in the V6 reliability gate.

Large chunks:

- [x] Decide and implement Tauri token bootstrap hardening.
- [x] Decide and implement rename path authority policy.
- [x] Design backend-owned network lifecycle mutation routes or explicitly remove/hide lifecycle affordances from WebView until ready. Current decision: keep Network lifecycle design-only/read-only, expose only `GET /api/network/workers`, and reject WebView lifecycle/mutation affordances until backend promotion gates exist.
- [ ] Stress-test sidecar/manifest writes on the real Windows/UNC storage profile.
- [x] Build a release-policy manifest shared by build, self-test, and docs.

Final recommendation: do not make broad rewrites yet. Continue with human-reviewed force-close workflow decisions plus operator-run PG-3, real-media, and real Windows/UNC sidecar stress validation. The safe release hygiene, reliability-gate split, stale desktop-shell cleanup, process-lifecycle fixes, Tauri token/CSP hardening, rename path authority policy, sidecar overwrite fallback guard, stale frontend-result coverage, and current Network read-only/design-only posture are now closed.
