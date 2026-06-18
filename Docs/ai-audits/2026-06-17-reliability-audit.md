# 30-Day Reliability Audit

Date: 2026-06-17

Change packet: `MP-CHANGE-2026-0617-902`

Scope: report-only audit of MediaPipelineRemuxEncodeAIO as production software expected to run unattended for 30 days. No reliability behavior, tests, configs, queue logic, worker logic, coordinator logic, media policy, or source/scratch/output movement was changed.

## Executive summary

The current promoted workspace has meaningful reliability guardrails: source mutation is forbidden by default, media movement is backend-owned, pending publish uses manifests and trust checks, disk-space probes fail closed when free space is unknown, native subprocess execution has timeouts and process-tree kill behavior, Local API request-handler threads are non-daemonized, ActiveJobs records protect close readiness, and Tauri validates backend health before opening the WebView.

The strongest 30-day unattended risks are not ordinary UI defects. They are places where the system can either lose operator intent, run the same file movement path twice from independent entrypoints, or stall for hours to indefinitely on external resources without a self-healing path.

Ranked by data-loss/corruption risk first, then operator impact, then likelihood:

1. Priority/hold manifest read corruption fails open to an empty manifest, so operator holds can be silently lost.
2. Pending-publish drain has strong per-transaction safety, but no visible global cross-process mutex around the drain loop.
3. Queue source inventory scans can block on filesystem walk/stat calls and keep close readiness unsafe without a bounded kill path.
4. Long native subprocess timeouts prevent infinite hangs but can still consume most of a 30-day window behind one bad file, copy, or OCR job.
5. Forced active-work shutdown remains necessary as an emergency path, but it is a data-integrity hazard if used as routine unattended recovery.
6. Thirty-day forensic evidence is weaker than runtime safety: JSON command history is capped, log retention defaults to 7 days, and SQLite mirrors are explicitly opportunistic.

The audit conclusion is: single-machine supervised daily use has many fail-closed protections; fully unattended 30-day operation needs additional hardening before it can be treated as production-safe without periodic operator review. Distributed coordinator/worker mode should remain out of unattended production scope until the provider-gated lifecycle work and validation gates are complete.

## Methodology

Session entry documents were read first as required:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`

Generated summaries were used before full source reads when available. Full source reads were limited to high-risk paths needed for evidence: process lifecycle, close readiness, ActiveJobs, Local API shutdown, queue source scans, priority manifest handling, pending-publish park/drain, command journaling, SQLite mirror writes, disk/copy behavior, native subprocess execution, network lifecycle contracts, settings/config recovery, and subtitle/OCR handling.

No dynamic 30-day soak, browser run, FFmpeg run, real-media sample, or destructive failure injection was executed for this report. Findings are static source-backed risks plus validation recommendations.

## Top reliability risks

### R1. Priority/hold manifest corruption can fail open

- Scenario: `priority_manifest.json` is truncated, partially written, locked, or contains invalid JSON during queue preview or launch planning. The operator had marked one or more sources as `hold`, expecting them to be excluded from processing.
- Evidence: `src/mediapipeline/core/queue/priority_manifest.py:6` documents the manifest as the non-destructive source of High/Normal/Low/Hold intent, and `:15` says `hold` is excluded from the queue. `read_priority_manifest()` returns an empty manifest on `OSError`, `JSONDecodeError`, or `UnicodeDecodeError` at `src/mediapipeline/core/queue/priority_manifest.py:67-84`. The same module writes via temp file and `os.replace` at `:320-331`, but there is no visible fsync or interprocess lock. PowerShell queue execution treats hold entries as never processed at `ops/pipeline/engine/queue/phase_executor.ps1:97-109`.
- Severity: high for data-safety intent, medium for direct media corruption.
- Likelihood: medium over 30 days, especially with antivirus, sync tools, abrupt power loss, or concurrent UI/backend access.
- Detection signal: sudden drop to zero hold count, queue rows changing from hold/excluded to runnable, missing `manifest_priority_explicit` evidence, or a queue snapshot that no longer lists expected hold rows. There is no obvious fatal error when the Python reader encounters corrupt JSON.
- Current recovery behavior: the reader substitutes an empty manifest; operator intent is not recovered automatically. Existing queue planning will still exclude holds if the manifest is readable.
- Worst-case impact: a source intentionally held for safety, duplicates, bad naming, subtitle review, or output-placement risk is processed unattended and can produce duplicate outputs, pending-publish artifacts, or bad completed evidence.
- Recommended hardening: treat unreadable or invalid priority manifest as fail-closed for queue launch and preview; preserve the corrupt file as `.bad` with timestamp; surface a Diagnostics/Queue blocker; add an owner/lease lock or atomic write with fsync; add a repair path that requires explicit operator acceptance before releasing holds.
- Test/smoke/real-media validation needed: unit tests for corrupt/truncated/locked priority manifest, queue preview smoke proving held rows stay blocked on read failure, and a launch-preflight test proving processing is blocked until manifest recovery. Real-media validation is only needed if launch planning behavior changes.

### R2. Pending-publish drain is transactionally careful but lacks a visible global drain mutex

- Scenario: two independent pipeline/drain processes run `Invoke-RetryPendingPushes` against the same `LocalPendingPush` directory, such as a manual CLI drain while the backend is also draining, a Tauri crash leaving a backend alive followed by a second launch, or future network lifecycle code calling the same drain surface.
- Evidence: `Invoke-RetryPendingPushes` begins at `ops/pipeline/engine/publish/pending_push.ps1:440` and enumerates manifests from the pending root at the start of the run. The drain transaction itself is defensive: it trusts manifests before drain at `ops/pipeline/engine/publish/pending_drain_transaction.ps1:148-156`, copies to a publish partial path at `:183-188`, removes failed partials and updates retry state at `:190-198`, and only completes after reveal/sidecar cleanup at `:251-274`. Manifest contract and destination trust checks live in `ops/pipeline/engine/publish/pending_manifest_store.ps1:241-338` and `:452-495`. The no-touch boundary register treats duplicate command guards as critical because simultaneous pipeline processes can create race conditions and manifest corruption at `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md:157-163`.
- Severity: high, because this is final-output file movement and manifest mutation.
- Likelihood: low to medium for current single-operator Local API flows, higher if manual scripts, crashed shells, scheduled tasks, or future network providers run concurrently.
- Detection signal: overlapping drain command journal entries, same manifest referenced by multiple drain summaries, duplicate `publish_drained` events, retry-state churn, `.mp-publish-partial.*` or sidecar rollback artifacts, or a manifest disappearing while another drain run reports it.
- Current recovery behavior: per-file transactions use trust checks, partial paths, sidecar rollback, retry states, and already-published validation. Pending park has `pending_move` crash recovery and preserves moved media if manifest state update fails.
- Worst-case impact: final media and sidecars disagree, a manifest is removed while another process still acts on stale data, local parked proof is deleted after one process succeeds while another reports failure, or the operator cannot determine which output is authoritative.
- Recommended hardening: add a named system mutex or lease file around the entire pending drain loop and pending index refresh, record lock owner/start time in the drain summary, refuse duplicate drain unless a stale lock is explicitly recovered, and add dual-process adversarial tests.
- Test/smoke/real-media validation needed: unit tests for lock acquisition/release/stale recovery, a dual-process pending-drain fixture with the same manifest directory, WebView pending-drain guard smoke, and representative real-media deferred-publish plus drain validation.

### R3. Queue source scans can stall close readiness on slow or blocked filesystems

- Scenario: a 30-day unattended run starts or refreshes a queue source scan while a source root is a slow SMB/NAS share, an offline drive, a path with files that hang on metadata, or a directory tree with many entries. The scanner blocks inside filesystem traversal or `stat()`.
- Evidence: `build_queue_source_inventory()` walks roots with `os.walk(..., followlinks=False)` at `src/mediapipeline/core/queue/source_inventory.py:177` and calls `path.stat()` during candidate creation at `:129`. The service starts queue source scans on a non-daemon worker thread at `src/mediapipeline/core/queue/service.py:232-236`, and close readiness blocks when a queue source scan is active through `src/mediapipeline/core/processes/guard_facade.py:141`. Queue dry-run subprocess execution does have a 120-second timeout at `src/mediapipeline/core/queue/service.py:71` and `src/mediapipeline/core/queue/dry_run_runner.py:58-79`, but that bounded subprocess pattern is not visible around the source inventory filesystem walk.
- Severity: medium-high for unattended operation, low for direct data loss.
- Likelihood: medium in a Plex-style library that may include USB, NAS, or sleeping disks.
- Detection signal: queue source scan status remains `running`, close readiness reports active queue scan, queue preview timestamp stops changing, Local API thread count stays stable but the scan worker never exits, or path health shows slow/offline roots.
- Current recovery behavior: ordinary `OSError` during scanning is captured as a warning; scan status is updated in normal completion/failure paths. There is no visible way to kill a blocked Python thread in a filesystem call.
- Worst-case impact: the backend refuses safe close for days, queue preview remains stale, scheduled work never starts, and an unattended operator cannot tell whether the process is doing useful work or waiting on an unresponsive filesystem.
- Recommended hardening: run source inventory scans in a bounded subprocess or cancellable worker process, add per-root time budgets, write scan heartbeats with current root/path count, mark stale-running scans as degraded after a threshold, and expose an operator recovery action that does not require force-killing active media work.
- Test/smoke/real-media validation needed: unit tests with fake scanners that block, Local API close-readiness tests for stale scan state, a smoke with a deliberately unavailable root, and an optional NAS/offline-drive manual validation.

### R4. Long subprocess timeouts can turn one bad item into an all-day queue stall

- Scenario: FFmpeg, mkvmerge, OCR, robocopy, or recursive cleanup keeps running but makes no useful progress. The configured timeout eventually terminates it, but the timeout window is large enough to consume most of a day or more.
- Evidence: default timeout values include FFmpeg encode 21600 seconds, CPU encode 43200 seconds, remux/mkvmerge 7200 seconds, OCR 1800 seconds, robocopy 14400 seconds, source/index scan 1800 seconds at `ops/pipeline/engine/config/default_values.ps1:337-362`. Runtime clamps allow encode/copy/source/index scan values up to 86400-172800 seconds at `ops/pipeline/engine/config/runtime_config.ps1:73-125`. `Invoke-NativeProcess` checks timeout and marks killed output at `ops/pipeline/engine/shared/native.ps1:303-443`; `Copy-FileRobocopy` retries after timeout at `ops/pipeline/engine/storage/disk.ps1:576-592`.
- Severity: medium-high for 30-day throughput, medium for operator trust, low direct data-loss risk due transaction guards.
- Likelihood: medium with large media, corrupt files, unstable storage, OCR workloads, or overloaded CPUs.
- Detection signal: no new completed rows, stale progress health, a long-running tool event without matching completion, repeated timeout failure records, unchanged file sizes in staging/partial directories, or one source path repeatedly occupying the active worker.
- Current recovery behavior: native tools are killed on timeout, failure records/logs are written, stop flags are polled, and partial copy artifacts are cleaned or retried in copy paths. Timeout alone does not quarantine a repeatedly bad source from future queue attempts.
- Worst-case impact: the 30-day run spends most of its time retrying a few bad files, scheduled windows miss work, disk fills with logs/staging artifacts before cleanup catches up, and useful queue items starve behind long failures.
- Recommended hardening: add no-progress watchdogs based on FFmpeg progress, stderr activity, output byte growth, and robocopy bytes; quarantine a source after repeated timeouts until manual review; add per-stage retry budgets and exponential backoff; emit stuck-job alerts before the hard timeout.
- Test/smoke/real-media validation needed: PowerShell unit tests with fake native tools that hang, emit output without progress, and stop responding; queue retry/quarantine tests; real-media validation with one corrupt media file and one slow copy target before changing FFmpeg or copy behavior.

### R5. Forced active-work shutdown is an emergency tool, not a safe unattended recovery loop

- Scenario: the shell or operator requests backend shutdown while active media work is still running, then uses `force_active_work_shutdown` or hits a shell force-kill path after a short grace period. If the active-work detector is stale or force is used as routine automation, media work can be killed mid-copy, mid-manifest update, or mid-encode.
- Evidence: backend shutdown blocks when close readiness is unsafe unless `force_active_work_shutdown` is explicitly true at `src/mediapipeline/core/api/commands_process.py:213-227`. Forced cleanup calls active spawned process cleanup at `src/mediapipeline/core/api/commands_process.py:174-193`; `kill_active_spawned_processes()` kills registered processes at `src/mediapipeline/core/processes/lifecycle.py:192-213`. The Tauri lifecycle boundary documents the graceful shutdown then force-kill sequence and warns that killing the backend can leave workers, incomplete logs, or parked outputs partially written at `docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md:60-62`.
- Severity: medium-high.
- Likelihood: low in normal UI flows because close readiness is fail-closed, but medium if unattended automation treats force shutdown as a recovery mechanism.
- Detection signal: command result with `forced_active_work_shutdown`, killed ActiveJobs records, stale progress files, partial/staging artifacts, pending manifests in `pending_move`, failure markers, or missing completion watcher updates.
- Current recovery behavior: close readiness checks ActiveJobs, fresh progress, queue scan, audit progress, and final-library promotion. ActiveJobs records are atomically written, completion/heartbeat watchers update status, pending park/drain has crash windows and repair logic, and startup cleanup removes stale partials.
- Worst-case impact: partial output, incomplete sidecars, manifest state requiring manual repair, duplicated processing on restart, or a source marked failed without enough logs to diagnose.
- Recommended hardening: require a stronger confirmation token and reason for forced active-work shutdown; after force, run a read-only recovery scan for ActiveJobs, pending manifests, partials, and scratch artifacts before accepting new work; extend or stage shell shutdown grace based on active job kind; never use forced shutdown as watchdog automation.
- Test/smoke/real-media validation needed: adversarial kill during encode, remux, copy, pending park, and pending drain; close-readiness tests for all active-work sources; real-media validation after any shutdown or process-control behavior change.

### R6. Thirty-day forensic evidence can age out or drift

- Scenario: a failure occurs on day 3, but the operator only reviews the system on day 30. The authoritative JSON state may still preserve current state, but command history, logs, and SQLite mirror evidence may be incomplete.
- Evidence: `CommandJournal` defaults to `max_entries=50` and trims old entries at `src/mediapipeline/desktop/api/command_journal.py:36-63`. Log retention defaults to 7 days at `ops/pipeline/engine/config/default_values.ps1:328`, and log cleanup removes old rotated logs at `ops/pipeline/engine/observability/logging.ps1:62-65`. SQLite storage is explicitly a mirror while JSON remains authoritative at `src/mediapipeline/core/storage/db.py:1-6`; queue and command mirror failures are caught and logged rather than blocking JSON operation at `src/mediapipeline/core/queue/dry_run_runner.py:119-127` and `src/mediapipeline/desktop/api/command_journal.py:188-202`.
- Severity: medium for recovery and auditability, low for direct media mutation.
- Likelihood: high over 30 days.
- Detection signal: `journal_persistence.degraded`, SQLite mirror status `failed`, missing command history entries, log files older than retention unavailable, or completed/pending proof that points to logs no longer present.
- Current recovery behavior: runtime behavior keeps using JSON authority even if SQLite mirror fails; command journal exposes degraded warnings; completed/pending proof boards provide current placement evidence.
- Worst-case impact: a media-placement discrepancy, duplicate run, or subtitle failure cannot be reconstructed, leading to unsafe reruns, manual deletion, or trust in incomplete completed rows.
- Recommended hardening: retain command outcomes and key tool events for at least 35 days or a bounded size cap; add a daily immutable audit summary; add SQLite drift/rebuild health checks; surface "forensic evidence incomplete" on Diagnostics when logs or mirror history are insufficient.
- Test/smoke/real-media validation needed: unit tests for retention boundaries, SQLite failure/rebuild tests, Diagnostics smoke for degraded persistence, and a synthetic 30-day log/journal aging test.

### R7. ActiveJobs fail closed on uncertainty, which protects data but can block unattended restart

- Scenario: the backend crashes or Windows restarts while a child process is active. On next launch, PID identity cannot be verified because process metadata is unavailable, PID was reused, or `psutil` cannot inspect the process. ActiveJobs stays blocking.
- Evidence: ActiveJob payloads are contract-validated and atomically written at `src/mediapipeline/core/processes/active_jobs.py:61-67`. Close readiness reports unreadable or unverifiable active records as blockers at `src/mediapipeline/core/processes/active_jobs.py:272-324`. Reconciliation marks definitely-gone or mismatched records orphaned, but leaves ambiguous cases active at `src/mediapipeline/core/processes/active_jobs.py:327-389`. Cleanup of stale launch guards intentionally applies only to validate-only launch guards, not continuous/run-once/audit/rerun work, at `src/mediapipeline/core/processes/active_jobs.py:392-533`.
- Severity: medium for unattended availability, low for direct data loss because the behavior is fail-closed.
- Likelihood: medium over 30 days with restarts, sleep/resume, endpoint security, or PID reuse.
- Detection signal: close readiness says ActiveJobs still reports active work, ActiveJobs rows remain `launching` or `active` after restart, or records are marked `orphaned`.
- Current recovery behavior: definitely dead/mismatched PIDs are reconciled; active/unverifiable records block close and launch; operator can inspect ActiveJobs and use backend-owned controls.
- Worst-case impact: the system never resumes unattended processing after a crash because it correctly refuses to assume active work is safe to ignore.
- Recommended hardening: add a restart recovery workflow that summarizes ambiguous ActiveJobs with process identity, progress freshness, scratch/pending evidence, and safe next actions; allow explicit operator recovery to mark verified-dead records after evidence capture; alert on stale active records older than a configured threshold.
- Test/smoke/real-media validation needed: ActiveJobs crash/restart fixtures for dead, reused, and inaccessible PIDs; close-readiness tests; adversarial kill during encode and drain with post-restart recovery proof.

### R8. Network coordinator/worker lifecycle is provider-guarded, not unattended distributed production-ready

- Scenario: the system is configured for coordinator or worker mode and expected to run for 30 days across machines. Lifecycle routes exist, but the real provider gates and remaining distributed-processing validations are incomplete.
- Evidence: the network lifecycle contract says confirmed routes are backend-owned but provider-guarded and should return blocked results when the real provider is unavailable at `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md:5-17`. It explicitly forbids substituting confirmed routes for normal local processing when provider hooks are unavailable at `:32`. Remaining gates include wiring real coordinator/worker providers, duplicate start/stop tests, provider active-state tests, command-journal success/failure tests, process cleanup/orphan tests, and source/scratch/output/pending-publish hash checks at `:107-110`.
- Severity: high if network mode is used unattended, low for single-machine mode where routes remain guarded.
- Likelihood: low unless the operator enables distributed mode, medium during future rollout work.
- Detection signal: network contract status `backend_lifecycle_routes_available_provider_guarded`, blocked confirmed start/stop command results, provider-unavailable cleanup result, or worker/coordinator state that does not have matching provider ownership.
- Current recovery behavior: confirmed lifecycle routes are intentionally blocked without provider availability; normal launch is blocked for network modes; dry-runs are no-mutation.
- Worst-case impact: duplicate distributed claims, orphaned worker scratch, done reports that cannot be reconciled, or final-output/pending-publish drift across machines if provider gates are bypassed.
- Recommended hardening: keep distributed mode out of unattended production until provider lifecycle, claim ownership, idempotent done reporting, orphan cleanup, hash-based source/scratch/output/pending-publish checks, and network-mode close-readiness are complete.
- Test/smoke/real-media validation needed: coordinator/worker lifecycle tests, duplicate start/stop tests, orphaned claim recovery, worker crash/done-report replay, multi-machine or simulated network soak, and real-media distributed validation before any unattended network use.

### R9. Subtitle/OCR failures are review-safe but can still stall throughput and lose context

- Scenario: a media item with ASS, TX3G, BDPGS, or VobSub subtitles hits a missing tool, unknown language, OCR timeout, empty SRT, or validation failure. The system routes this to failure/review instead of silently publishing bad subtitles, but OCR and retry behavior can stall a worker and logs can age out before review.
- Evidence: the no-touch boundary register classifies subtitle conversion as high-risk because silent drops or double conversions are hard to detect without output inspection at `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md:63-69`. BDPGS conversion writes failure records for missing tools, unknown language, failed OCR, empty OCR, and exceptions at `ops/pipeline/engine/subtitles/bdpgs.ps1:313-410`. VobSub has similar failure records and validation at `ops/pipeline/engine/subtitles/vobsub.ps1:666-863`. OCR defaults are 1800 seconds at `ops/pipeline/engine/config/default_values.ps1:343-344`, with runtime clamps up to 14400 seconds at `ops/pipeline/engine/config/runtime_config.ps1:87-88`.
- Severity: medium for unattended throughput and output trust; high if a future change weakens review routing.
- Likelihood: medium in mixed media libraries.
- Detection signal: subtitle failure records, failed subtitle progress stages, BDPGS/VobSub OCR tool/tessdata warnings, empty SRT validation failures, or completed rows needing subtitle review.
- Current recovery behavior: failures are recorded as retryable standard failure records, progress marks failed stages, and configured behavior preserves/reviews instead of silently publishing bad conversions.
- Worst-case impact: a long OCR job blocks a worker for hours, then fails; repeated retries starve the queue; by the time the operator reviews, log context may be expired.
- Recommended hardening: add per-title subtitle retry budgets, quarantine after repeated OCR failures, surface subtitle failure age/count in Diagnostics, keep subtitle failure evidence for at least 35 days, and avoid unattended retry loops for bitmap OCR failures without changed inputs.
- Test/smoke/real-media validation needed: unit tests for missing OCR tools, unknown language, empty OCR output, and timeout behavior; real-media samples with TX3G, ASS, BDPGS, and VobSub before any subtitle policy change.

### R10. Settings/config corruption has recovery paths, but unattended recovery proof is incomplete

- Scenario: the PSD1 config is partially written, syntactically invalid, stale relative to UI metadata, or incompatible with current schema during startup. The backend may fail preflight or require last-known-good recovery before unattended processing can resume.
- Evidence: backend settings ownership is canonical, and WebView staging is display-only per `docs/CURRENT_PROJECT_STATE.md:93`. PSD1 syntax validation uses `Import-PowerShellDataFile` at `src/mediapipeline/core/config/document_runner.py:61-73` and `src/mediapipeline/core/config/load.py:3-65`. Config writes use `atomic_write_text()` in `src/mediapipeline/core/config/save_runner.py:11-52`, backed by `src/mediapipeline/core/config/file_io.py:68-79`. Last-known-good recovery functions exist at `src/mediapipeline/core/config/recovery.py:196-281`.
- Severity: medium-high for startup availability, medium for data safety if wrong paths or policies are accepted.
- Likelihood: low to medium, depending on concurrent edits, power loss, or manual config changes.
- Detection signal: config syntax validation errors, startup warnings, blocked preflight, settings preview/save failures, config identity mismatch, or last-known-good recovery messages.
- Current recovery behavior: validation/preflight can block unsafe launches, config writes are atomic, and last-known-good recovery code exists. This audit did not run a live recovery drill.
- Worst-case impact: unattended restart fails and no work runs; or, worse, an operator manually repairs by copying an old config with wrong source/output roots or unsafe media policy.
- Recommended hardening: run and document an unattended startup drill for corrupt config, missing config, bad path roots, and stale last-known-good; add a clear "running from recovered config" banner; include active config identity in every launch and drain summary; require real-media revalidation after path/media-policy recovery.
- Test/smoke/real-media validation needed: settings corruption tests, Local API startup/preflight smoke, config recovery tests, and real-media validation only if recovery can alter media policy or paths.

## 30-day unattended failure model

Assumptions for this model:

- Single Windows machine is the baseline. Network coordinator/worker mode is out of unattended production scope until provider gates are completed.
- JSON runtime files remain authoritative; SQLite is a mirror.
- Source files must not be mutated unless an explicitly enabled safe-delete setting applies.
- Final output may be unavailable or unsafe; pending publish must park and later drain with manifest evidence.
- The operator may not inspect the UI, logs, or filesystem for 30 calendar days.

Expected 30-day failure shape:

1. Startup usually fails closed. Config syntax, path health, active-work state, and provider-guarded network lifecycle should block unsafe launches rather than mutate media.
2. The dominant steady-state risk is stall, not immediate deletion. Long FFmpeg/copy/OCR timeouts, blocked filesystem scans, file locks, or stale ActiveJobs can halt throughput while preserving safety.
3. The dominant data-integrity risk is operator-intent or manifest evidence loss. Priority manifest fail-open behavior, duplicate drain entrypoints, and aged-out logs weaken the proof needed to avoid unsafe reruns or cleanup.
4. Crash recovery is partially mature. ActiveJobs and pending-publish `pending_move` repair are conservative, but conservative recovery can leave the system blocked until a human classifies the evidence.
5. Disk-full behavior is safer than many systems. Free-space indeterminate conditions fail closed in copy/encode paths, and copy uses staging/partial/backup behavior. The remaining 30-day risk is accumulation of logs, partials, failure artifacts, and repeated retry evidence without a forecast.
6. UI/API desync is mostly mitigated by backend ownership and read-only diagnostics, but 30-day unattended use needs backend-authored health signals that do not depend on an open WebView.

The most plausible unattended outage is a stalled but data-safe backend: one blocked scan, hung copy, long OCR job, or stale ActiveJob stops further useful work and keeps close/readiness unsafe. The most concerning corruption path is not the core pending-publish transaction; it is stale or lost operator/manifest evidence leading a later operator or automated retry to make the wrong recovery decision.

## Recovery matrix

| Failure mode | Existing detection/recovery | Remaining gap | Recommended validation |
| --- | --- | --- | --- |
| Startup failure | Health route validation, config parsing, path preflight, active-work preflight, network provider gates. | Need automated corrupt-config and missing-path recovery drill evidence for unattended mode. | Local API startup smoke with bad config, missing roots, recovered config, and launch preflight. |
| Shutdown failure | Backend shutdown blocks unsafe close unless explicit force; request-handler threads are non-daemonized; Tauri monitors backend health. | Force shutdown can still kill active work if used as recovery automation. | Close-readiness tests plus adversarial kill during encode/copy/drain. |
| Queue stalls | Queue dry-run subprocess timeout; source scan status artifacts; close readiness blocks active scans. | Source inventory filesystem walk can block without subprocess kill. | Fake blocking root test, stale-running scan test, unavailable NAS/manual validation. |
| Worker crashes | ActiveJobs records, completion/heartbeat watchers, progress freshness, failure records. | Ambiguous PID identity can block unattended restart until human review. | Crash/restart fixture for dead, reused, inaccessible, and orphaned PIDs. |
| Coordinator crashes | Network lifecycle is provider-guarded and routes block without real provider. | Distributed processing gates are not complete. | Coordinator provider tests, worker crash/done replay, multi-machine soak before use. |
| Retry loops | Failure records, timeout exit codes, pending retry states. | No global quarantine/backoff proof for repeated bad media/OCR/copy failures. | Repeated-timeout queue test and quarantine/backoff smoke. |
| Deadlocks/livelocks | Native runner avoids stdout/stderr deadlocks and polls stop/timeout; Local API handlers are non-daemonized. | Long no-progress runs can live until the hard timeout. | Fake tool with blocked stdout, noisy stderr, no progress, and stop flag tests. |
| Race conditions | Local process launch lock and duplicate-command guards; backend owns mutation. | Cross-process script/manual drain lock is not visible. | Dual-process drain and duplicate launch from separate processes. |
| Duplicate processing | Launch lock, active-work block, hold entries, network routes blocked. | Priority manifest corruption can remove holds; manual/CLI concurrency can bypass UI expectations. | Corrupt priority manifest launch block and external duplicate-start test. |
| Partial writes | Many JSON writes use temp/replace; copy uses staging/partial/backup; pending manifests use readback validation. | Some writes lack visible fsync; forced shutdown can still interrupt multi-step flows. | Power-loss style temp/truncate fixtures and force-kill recovery tests. |
| Corrupt JSON/state | Pending manifests validate and mark invalid; command journal warns on load/save failure; priority manifest currently fails open. | Inconsistent corruption policy across JSON artifacts. | Corrupt JSON matrix across priority, pending, queue snapshot, command journal, ActiveJobs. |
| SQLite mirror drift | SQLite failures are warning-only; JSON remains authoritative. | No visible drift checker or rebuild flow for 30-day evidence. | Mirror-failure, drift-detection, rebuild, and Diagnostics smoke tests. |
| File locks | Atomic writes retry selected `PermissionError`; copy retries fresh staging; file operations catch/report failures. | Lock storms from antivirus/NAS can exceed retry windows and cause stale state. | Locked-file fixtures for JSON, manifest, sidecar, output, and partial paths. |
| Source/scratch/output movement | Source mutation forbidden; disk/copy paths use boundary guards and staging; pending publish parks unsafe final output. | Any movement changes require real-media validation; manual scripts can still be entrypoints. | Boundary tests plus real-media source/scratch/output movement validation. |
| Pending-publish safety | Trust checks, `pending_move` repair, partial reveal, retry states, drain summaries. | Need global drain mutex and duplicate-drain proof. | Pending publish unit tests, dual-drain adversarial fixture, real-media deferred/drain. |
| Manifest loss | Pending manifests use contract checks and readback; invalid manifests surface rows. | If evidence logs age out, manifest repair can become manual guesswork. | Manifest deletion/corruption fixtures and 35-day evidence retention test. |
| Disk-full behavior | Unknown free space returns fail-closed; copy estimates destination free space; partial cleanup exists. | No 30-day disk forecast for logs, failures, pending, staging, and retry accumulation. | Low-disk tests, unknown-UNC-space tests, artifact-growth soak. |
| Log growth | Log retention defaults to 7 days; stale partial cleanup exists. | Seven days is not enough for 30-day unattended forensic review. | Synthetic 35-day retention/drift test and size-cap validation. |
| Subprocess hangs | Native process timeout, stop polling, process-tree kill, tool events. | No no-progress watchdog before large hard timeouts. | Hanging fake FFmpeg/mkvmerge/OCR/robocopy tests. |
| FFmpeg failure handling | Tool command events, repro-on-failure, timeout kill, failure records. | Repeated failures can starve queue without quarantine. | Corrupt media real sample and repeated-failure backoff test. |
| Subtitle/OCR/conversion failure | Review-safe failure records, per-stage progress, validation before sidecar move. | Long OCR and expiring logs reduce unattended recoverability. | Subtitle-bearing real-media validation plus OCR timeout/missing-tool fixtures. |
| Settings corruption | Atomic config writes, PSD1 syntax validation, last-known-good recovery functions. | Need proof that unattended startup surfaces and recovers safely without bad policy/path acceptance. | Corrupt/missing/stale config startup suite. |
| UI/API desync | Backend owns mutation; WebView uses backend metadata and command routes; Diagnostics read-only. | Long unattended health should not depend on WebView being open. | Backend-only health snapshot and WebView stale-state smoke. |
| Clock/timestamp issues | State files and sample records use UTC-ish ISO strings in many paths. | No 30-day clock-jump/timezone/DST recovery evidence was found in this audit. | Time-skew tests for stale progress, log retention, ActiveJobs, queue snapshots. |
| Restart recovery | ActiveJobs reconciliation, pending `pending_move` repair, stale partial cleanup. | Conservative blockers can prevent unattended resume until classified. | Crash/restart suite across encode, copy, pending park/drain, queue scan. |

## Observability gaps

1. No single 30-day health ledger: current evidence is spread across JSON state, command history, logs, failure records, pending summaries, completed rows, and optional SQLite mirrors.
2. Command history is bounded to 50 entries while log retention defaults to 7 days, which is not enough to reconstruct day-1 failures on day 30.
3. Queue source scan status does not appear to include a heartbeat path/root currently being scanned, so a blocked filesystem call and a large-but-progressing scan can look similar.
4. SQLite mirror drift is visible as warnings/degraded status, but there is no obvious periodic reconciliation or rebuild command.
5. ActiveJobs fail-closed behavior is safe, but ambiguous stale records need a higher-level recovery board that groups process identity, progress freshness, scratch artifacts, pending manifests, and safe next action.
6. Pending publish has good row-level safety evidence, but duplicate-drain detection would be stronger with run-level lock owner, drain transaction ID, and "another drain active" signal.
7. Disk pressure is checked before major copy/encode work, but there is no apparent 30-day forecast for logs, failure reports, staging directories, partials, pending payloads, and SQLite/log growth together.
8. No-progress detection is mostly timeout-based. Operators need early signals for "active but not advancing" before a 6-hour, 12-hour, or 48-hour timeout expires.
9. Time/clock health is not surfaced as a first-class reliability signal, even though stale progress, retention, schedule stop, and ActiveJobs rely on timestamps.

## Hardening roadmap

### P0 - Must fix before fully unattended single-machine use

1. Make priority manifest read failures fail closed for launch/processing and visible in Diagnostics.
2. Add a global pending-drain mutex/lease with stale-lock recovery and run-level evidence.
3. Move queue source inventory scans to a bounded subprocess or equivalent killable execution model.
4. Add no-progress watchdogs and retry quarantine for FFmpeg/copy/OCR failures.
5. Extend forensic retention to 35 days or add a bounded daily health ledger that preserves enough command/tool/failure/pending evidence.
6. Add a restart recovery board for stale ActiveJobs, partials, pending manifests, and scratch evidence before accepting new unattended work.

### P1 - Prove 30-day unattended resilience

1. Build an accelerated soak harness that simulates 30 days of launches, queue refreshes, failed files, pending parks, drains, UI polling, restarts, and log rotation.
2. Add disk-pressure and file-lock test fixtures for JSON state, pending manifests, sidecars, final output, and staging directories.
3. Add corrupt JSON recovery tests across priority manifest, queue snapshot, command journal, ActiveJobs, pending manifest, and completed records.
4. Add time-skew tests for DST, clock rollback, clock jump forward, and stale progress thresholds.
5. Add Diagnostics health summary assertions that the backend, without an open WebView, reports all stop-the-line conditions.

### P2 - Distributed/network unattended readiness

1. Complete the real coordinator and worker lifecycle providers.
2. Add duplicate start/stop, provider active-state, command-journal success/failure, process cleanup/orphan, source/scratch/output/pending hash, and done-report replay tests.
3. Run a multi-machine or faithful simulated-network soak with real media, source immutability checks, worker crash recovery, coordinator restart, and pending-publish safety.
4. Keep network confirmed routes provider-guarded until all gates pass.

## Must fix before unattended use

For single-machine 30-day unattended operation:

- R1: Priority manifest corruption must fail closed.
- R2: Pending-publish drain needs a global duplicate-run guard.
- R3: Queue source inventory scan must become bounded/cancellable or externally recoverable without force-killing active media work.
- R4: Long-running tool work needs no-progress detection plus quarantine/backoff for repeated bad files.
- R6: Evidence retention must cover the unattended review window.
- R7: Restart recovery must provide a safe operator-confirmable path for ambiguous ActiveJobs instead of either blocking forever or encouraging force kill.

For any unattended distributed/network operation:

- R8 is a hard stop. Coordinator/worker lifecycle provider wiring and the listed network validation gates must be complete first.

## Validation ladder recommendations

- Priority manifest fail-closed: targeted Python unit tests, queue preview tests, launch-preflight tests, then WebView Queue smoke. Real-media validation only if launch planning behavior changes beyond blocking.
- Pending-publish mutex: PowerShell unit tests for lock/lease behavior, dual-process drain adversarial test, pending-publish WebView smoke, then representative real-media deferred publish plus drain.
- Queue source scan bounding: Python unit tests with fake blocking scanners, Local API close-readiness tests, smoke with unavailable root, and optional NAS/offline-drive validation.
- No-progress watchdog/quarantine: fake native tool tests for hang/no-progress/noisy-output cases, queue retry tests, PowerShell reliability regression, then corrupt-media and slow-copy real-media validation.
- Forced shutdown/restart recovery: close-readiness tests, ActiveJobs crash fixtures, adversarial kill during encode/copy/pending park/drain, then real-media recovery validation.
- SQLite and 30-day evidence retention: unit tests for mirror failure/drift/rebuild, log/journal aging simulation, Diagnostics degraded-persistence smoke.
- Subtitle/OCR hardening: unit tests for missing tools, unknown language, timeout, empty output, and validation failure; real-media TX3G, ASS, BDPGS, and VobSub samples before any behavior change.
- Settings corruption: config syntax/load/save/recovery unit tests, Local API startup smoke, settings Preview/Save smoke, and real-media validation only when recovered config can affect media policy or paths.
- Network unattended readiness: lifecycle provider tests, duplicate start/stop tests, worker crash/done replay tests, source/scratch/output/pending hash checks, and multi-machine real-media soak.

Any implementation touching FFmpeg command generation, subtitle/audio policy, source/scratch/output movement, pending publish, queue behavior, worker/coordinator lifecycle, cleanup, settings persistence, command journal, or close readiness should use the higher rung from `docs/testing/VALIDATION_LADDER_RUNBOOK.md` and rerun representative real-media validation where the project rules require it.

## Limitations

- Static audit only. No tests, smokes, soak run, browser automation, FFmpeg execution, or real-media samples were run for this report.
- The repository had a broad pre-existing dirty worktree during the audit. Evidence references reflect the files present in this workspace on 2026-06-17, including uncommitted changes.
- The audit did not inspect every file in the repository. It focused on high-risk reliability surfaces using generated summaries, targeted search, and full reads where the summaries were insufficient.
- Runtime environment assumptions such as actual disk size, NAS behavior, antivirus/file-lock behavior, Windows power policy, current operator config, and real library media distribution were not measured.
