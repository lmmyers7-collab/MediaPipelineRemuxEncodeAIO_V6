# Network Worker/Coordinator Hardening & Multi-Library Plan

- Status: Implementation plan with Phases A-D complete and Phase E code complete/pending operator real-media validation as of 2026-06-15
- Created: 2026-06-14
- Origin: live debugging of the LAN coordinator(layne-server)/worker(GamingPC) cluster on 2026-06-14
- Related: Docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md, NETWORK_MODE_READ_ONLY_DOCUMENTATION.md
- Memory: worker-stale-coordinator-url-restart, network-worker-coordinator-review

## 0. How an AI agent should use this document

1. Read AGENTS.md (esp. §§1-3, §7) and docs/SESSION.md BEFORE editing. Several items touch §7 (network claim contract, coordinator path identity) — those require a written plan + the AGENTS §5 validation rung and must NOT be self-certified.
2. Do ONE work item per session. Each item below is self-contained: Problem, Target, Files+Symbols, Sketch, Data example, Acceptance, Validation, Tests.
3. Respect the execution order in §3 (dependencies flow downward). The path-mapping cluster (C1/C2) is the operator priority; it may be front-loaded after the Phase A enablers it relies on for validation.
4. TOOLING GOTCHA (verified 2026-06-14): the Edit/Write tools write to a sandbox OVERLAY for local C:\ paths; the running app and PowerShell do NOT see those writes. UNC (\\HOST\...) edits DO pass through. => For real edits to LOCAL config/state files use the PowerShell tool ([System.IO.File]::WriteAllText, preserve UTF-8 BOM state). Source-code edits under the repo are fine to author with Write/Edit, but VERIFY on disk with PowerShell (Get-Item mtime) before assuming they landed.
5. Validation runtime: apps\desktop\runtime\Python\python.exe (never system Python). Network tests: tests/python/desktop/test_network*.py.
6. Always back up any config/psd1 before editing (Copy-Item to *.bak_<ISO>). Never commit/push unless asked.

## 1. Ground truth (real system data this plan is built on)

Cluster (2026-06-14):
- Coordinator host: Layne-Server = 192.168.0.161, NetworkRole='coordinator', CoordinatorPort=7830, CoordinatorBindAddress='0.0.0.0'. Runs the portable build.
- Worker host: GamingPC (user lmmye), NetworkRole='worker', WorkerName='GamingPC desktop', WorkerPollIntervalSecs=10. Runs the dev build from the repo (apps\desktop, mediapipeline-tauri-shell.exe + local_api_main on 127.0.0.1:31004).

Config files (PowerShell-data .psd1):
- Worker:      C:\Users\lmmye\AppData\Local\MediaPipelineRemuxEncodeAIO\MediaPipeline_config.psd1
- Coordinator: \\LAYNE-SERVER\Users\Layne\AppData\Local\MediaPipelineRemuxEncodeAIO\MediaPipeline_config.psd1

Library roots (THE multi-library problem in one table):
| library_id | Coordinator source root (local)            | Worker source root (UNC)                          | Output root (UNC)                                  |
|------------|--------------------------------------------|---------------------------------------------------|----------------------------------------------------|
| movies     | C:\Users\Layne\Videos\Encode\Movies        | \\LAYNE-SERVER\Users\Layne\Videos\Encode\Movies   | \\LAYNE-SERVER\Users\Layne\Videos\outsource\Movies |
| tv         | C:\Users\Layne\Videos\Encode\TV            | \\LAYNE-SERVER\Users\Layne\Videos\Encode\TV       | \\LAYNE-SERVER\Users\Layne\Videos\outsource\TV     |

Current manual bridge on the worker (the thing to make automatic):
  WorkerSourcePathMap = '{"C:\\Users\\Layne\\Videos\\Encode": "\\\\LAYNE-SERVER\\Users\\Layne\\Videos\\Encode"}'

Network config keys (in MediaPipeline_config.psd1): NetworkRole, CoordinatorPort, CoordinatorBindAddress, CoordinatorAuthToken, CoordinatorAlsoEncodeLocally, CoordinatorHeartbeatTimeoutMins, WorkerCoordinatorUrl, WorkerAuthToken, WorkerName, WorkerPollIntervalSecs, WorkerSourcePathMap, WorkerEncoderMap, WorkerHonorCoordinatorPolicy, CoordinatorMaxJobRetries, and WorkerConfigOverrides (compatibility-only/backend-disabled). Key constants live in src\mediapipeline\desktop\config_keys.py (e.g. KEY_COORDINATOR_AUTH_TOKEN, KEY_WORKER_AUTH_TOKEN); confirm exact symbol names there before referencing.

Key code locations (file : symbol):
- src\mediapipeline\desktop\network\protocol.py:52  -> class ClaimResponse includes strict job/source metadata, library_id/relative_path, accessible_library_ids, retry_after_seconds, and strict boolean/integer parsing.
- src\mediapipeline\desktop\network\path_map.py:18  -> parse_source_path_map(raw)  ; :48 apply_source_path_map(path, mappings)  (prefix, case-insensitive)
- src\mediapipeline\desktop\network\worker.py:98 reads token ; :242 _parse_source_path_map ; :245 _apply_path_map ; :254 update_source_path_map ; :270 update_auth_token ; :152 "WorkerDispatcher started ... path_map_entries=%d"
- src\mediapipeline\desktop\network\worker_loops.py  -> _poll_loop ; GET /api/claim ; _apply_path_map(claim.source_path) ; logs "Path map rewrote A -> B"
- src\mediapipeline\desktop\network\coordinator_auth.py:13-31 -> _load_or_generate_token (config CoordinatorAuthToken -> app_state coordinator_auth_token -> generate+persist) ; :79 update_auth_token
- src\mediapipeline\desktop\network\coordinator_queue.py / coordinator_http_handlers.py -> builds the ClaimResponse and serves /api/claim, /api/heartbeat, /api/done, /api/log
- src\mediapipeline\desktop\application\network_lifecycle_provider.py:304 start_network_worker ; :323 stop_network_worker
- src\mediapipeline\contracts\api_commands.py:222-239 NetworkLifecycle*Payload ; routes /api/network/worker/{start,stop,start-dry-run,stop-dry-run}
- src\mediapipeline\core\api\commands.py:63-65 route->handler map ; commands_network.py command handlers
- src\mediapipeline\desktop\api\http_helpers.py:96 request_authorized (X-MediaPipeline-Token / Bearer) ; host+origin checks
- src\mediapipeline\desktop\api\static_files_policy.py:32-35 (token withheld from served HTML on shell_surface=tauri)
- src\mediapipeline\desktop\local_api_main.py:362 emits bootstrap+token to stdout ; :56 --token ; :59 --no-token
- src\mediapipeline\core\kernel\models.py:112 class QueueRecord {source_path, is_priority, relative_path(:121), size_gb}  (relative_path ALREADY exists)
- Auth scheme: src\mediapipeline\desktop\network\auth.py HMAC-SHA256, X-MediaPipeline-* headers, +/-300s skew, nonce replay cache.

Endpoints today (coordinator HTTP, default :7830, all auth-required except where noted): /api/ping (GET), /api/libraries (GET), /api/claim (GET), /api/heartbeat (POST), /api/done (POST), and /api/log (POST). Worker local API (127.0.0.1, per-run token) includes /api/health (public), setup/test routes such as /api/network/worker/test-connection, /api/network/worker/discover-coordinators, /api/network/coordinator/join-blob, /api/network/worker/join-cluster, and provider-guarded lifecycle routes /api/network/{worker,coordinator}/{start,stop,start-dry-run,stop-dry-run}.

Three failure modes observed and fixed on 2026-06-14 (the motivation):
1. Stale dispatcher URL (ran 192.168.1.50, saved Layne-Server) -> all-timeout, no claims. Fixed by worker restart.
2. Auth token mismatch -> 401 auth_failed. Fixed by setting CoordinatorAuthToken in coordinator config = worker token.
3. Local-vs-UNC path mismatch -> encodes failed in 3-5s (file not found), coordinator re-queued forever. Fixed by WorkerSourcePathMap.

## 2. Conventions for each work item

ID | Goal | Depends-on | Effort(S/M/L) | Risk | AGENTS-§7? then Problem / Target / Files / Sketch / Data example / Acceptance / Validation / Tests.

## 3. Execution order (phases; dependencies flow downward)

Phase A (low-risk enablers + immediate pain relief; build the harness that validates everything else):
  A1 = drift banner (#6)
  A2 = test-connection preflight (#7)
  A3 = per-layer status + structured failure reasons (#12)
  A4 = quarantine repeated same-reason failures (#11)
Phase B (kills the stale-process class):
  B1 = hot-apply settings to the live dispatcher (#5)
Phase C (OPERATOR PRIORITY: multi-library path mapping):
  C1 = advertise library roots + auto-derive path map (#2)   <- delivers "add libraries, no manual map"
  C2 = library-relative claims (#1)                          <- durable fix; §7 contract change
  C3 = path-map row editor UI (#4)
  C4 = (alternative strategy) UNC-canonical addressing (#3)
Phase D (zero-touch setup):
  D1 = pairing code / join file (#9)
  D2 = mDNS auto-discovery (#8)
  D3 = capability/accessibility handshake (#10)

If only three things ship: C1 + B1 + A1. That makes libraries self-configuring, settings apply live, and drift is visible.

---

## Phase A - Enablers & safety

### A1 (#6) - "Running != saved" drift banner
Depends-on: none | Effort: S | Risk: low | §7: no
Problem: On 2026-06-14 the live dispatcher used http://192.168.1.50:7830 while saved WorkerCoordinatorUrl was http://Layne-Server:7830. Nothing surfaced the mismatch; it was only found in the log line worker.py:152.
Target: When the running dispatcher's URL/token/path-map differ from resolved config, show a banner on Home + Network tab with a one-click "Apply & reconnect" (calls B1; until B1 exists, "Restart worker").
Files: src\mediapipeline\desktop\network\worker.py (expose getters: base_url, auth_token fingerprint, path_map_entries); network evidence builder (the payload the Network tab reads); ui_web network tab component.
Sketch: add WorkerDispatcher.runtime_descriptor() -> {coordinator_url, token_fingerprint(sha256[:8]), path_map_entries}. In the evidence payload add running_vs_saved = compare(runtime_descriptor, resolved config). Frontend renders a warning row when any field differs. Never print full tokens; compare sha256 fingerprints only.
Data example: running={url:'http://192.168.1.50:7830', token_fp:'9a3f...', map:0} vs saved={url:'http://Layne-Server:7830', token_fp:'9a3f...', map:1} -> banner: "Worker is running with settings that differ from saved (URL, path map). Restart worker to apply."
Acceptance: with a deliberate mismatch the banner appears and names the differing fields; with matching state no banner.
Validation: unit test the comparator; manual: change WorkerCoordinatorUrl, do not restart, confirm banner.
Tests: tests/python/desktop/test_network_drift_descriptor.py (new).

Status 2026-06-14: complete in change packet MP-CHANGE-2026-0614-005. Implemented WorkerDispatcher runtime descriptors with token fingerprints, network payload running-vs-saved drift evidence, Home and Network drift banners, and unit/WebView coverage. Manual deliberate live-worker mismatch validation remains operator-side because this session did not attach to a running two-machine worker.

### A2 (#7) - Test-connection preflight (all three layers)
Depends-on: none | Effort: M | Risk: low-med | §7: no (adds a read-only ping endpoint + a diagnostic command)
Problem: Diagnosing required reading logs to tell timeout (URL) vs 401 (auth) vs file-not-found (path) apart.
Target: One command that reports per-layer PASS/FAIL: (L1) TCP reach coordinator; (L2) auth via a signed no-op; (L3) path access: stat each worker library source root + output root.
Files: coordinator: add auth-required GET /api/ping returning {ok:true, server_time} (coordinator_http_handlers.py + protocol). worker: add command route /api/network/worker/test-connection (contracts\api_commands.py + commands.py + commands_network.py) that runs L1/L2/L3 and returns a structured report. Reuse auth.sign_request for L2 and the worker library roots for L3.
Sketch L3 example (worker libraries from §1): for each of {'\\LAYNE-SERVER\\...\\Encode\\Movies','...\\Encode\\TV','...\\outsource\\Movies','...\\outsource\\TV'} -> os.path.isdir(); collect {path, ok}.
Data example output: {l1_tcp:'pass', l2_auth:'pass', l3_paths:[{path:'...Encode\\Movies', ok:true}, {path:'...Encode\\TV', ok:false}]}.
Acceptance: with the coordinator down -> l1 fail; wrong token -> l2 fail (reason auth_failed); a library root unreachable -> that l3 entry false; all good -> all pass.
Validation: tests/python/desktop/test_network_test_connection.py; manual run from the worker UI button.

Status 2026-06-14: complete in change packet MP-CHANGE-2026-0614-006. Implemented auth-required coordinator GET /api/ping, worker POST /api/network/worker/test-connection, WebView button/result rendering, Tauri required-route coverage, command ownership docs, and targeted unit/static tests. Agent-side validation passed for the targeted Python/WebView/Tauri checks and the full tests/python/desktop/test_network*.py discovery suite. Manual live worker UI button validation remains operator-side because this session did not connect to the live cluster.

### A3 (#12) - Per-layer status + structured failure reasons
Depends-on: A2 | Effort: M | Risk: low | §7: no
Problem: The coordinator "Issues: 2" counter was ambiguous; pipeline failures reached the coordinator only as "failed".
Target: Network evidence exposes distinct indicators {url_reachable, auth_ok, paths_ok, queue_fresh, last_claim_result}. The pipeline failure reason is propagated to the coordinator done/failed report and shown per job.
Files: protocol.py DoneRequest/done report (add reason:str, reason_code:str e.g. SOURCE_NOT_FOUND|OUTPUT_UNWRITABLE|AUTH|TIMEOUT|ENCODE_ERROR); worker_loops.py + the pipeline failure parsing to populate reason_code; coordinator registry/evidence to store+surface it; ui_web dashboard.
Data example: instead of "Pipeline failed for The Mask ... after 3.1s: failed" -> reason_code=SOURCE_NOT_FOUND, reason="C:\\Users\\Layne\\...\\The Mask...mkv not found on worker".
Acceptance: the three historical failure modes each map to a distinct reason_code visible in the dashboard.
Tests: extend test_network_workflow.py with reason propagation.

Status 2026-06-14: complete in change packet MP-CHANGE-2026-0614-007. Implemented structured DoneRequest reason_code/reason fields, conservative failure classification for TIMEOUT/AUTH/SOURCE_NOT_FOUND/OUTPUT_UNWRITABLE/ENCODE_ERROR, coordinator registry last-failure persistence, worker/coordinator cluster-log propagation, read-only diagnostic layer indicators {url_reachable, auth_ok, paths_ok, queue_fresh, last_claim_result}, and WebView dashboard/detail rendering. Validation passed for targeted Python network/application tests, WebView static boundary tests, npm WebView asset/lint checks, and the WebView browser Network smoke. Quarantine/retry suppression remains out of A3 scope and belongs to A4.

### A4 (#11) - Quarantine repeated same-reason failures
Depends-on: A3 (reason_code) | Effort: S-M | Risk: med | §7: borderline (queue behavior) -> treat as §7, plan+validate
Problem: A worker that cannot access sources failed every job in ~3-5s and the coordinator re-queued forever (25 claims/25 failures observed before the path fix).
Target: Coordinator tracks per-job and per-worker failure counts + last reason_code. After N (config CoordinatorMaxJobRetries, default 3) consecutive same-reason failures: stop re-dispatching that job to that worker (or mark job blocked) and raise a cluster alert. If EVERY recent claim from a worker fails with the same reason_code, flag the worker as "misconfigured (reason)".
Files: coordinator_queue.py / registry.py (failure ledger), new config key CoordinatorMaxJobRetries, cluster log event worker_quarantined.
Acceptance: simulate a worker that always returns SOURCE_NOT_FOUND -> after 3 the job stops being re-handed and an alert is emitted; queue does not infinite-loop.
Tests: test_network_inflight_registry.py / new test_network_quarantine.py.

Status 2026-06-14: complete in change packet MP-CHANGE-2026-0614-008. Implemented CoordinatorMaxJobRetries across Python, PowerShell, contract, metadata, and WebView config surfaces; added a coordinator failure ledger keyed by worker/source/reason; suppresses same-worker redispatch after the configured consecutive same-reason threshold; emits one worker_quarantined cluster alert; persists failure-streak and worker-misconfigured evidence for the Worker Board. Validation passed for targeted Python network/config contract tests, network protocol/runtime and WebView boundary tests, npm WebView asset/lint checks, and the WebView browser Network smoke. No source, scratch, publish, drain, or media-policy behavior was changed.

## Phase B - Live application

### B1 (#5) - Hot-apply settings to the running dispatcher
Depends-on: A1 (to clear the banner) | Effort: S-M | Risk: med | §7: no (no contract change)
Problem: URL changes only apply on worker Stop/Start; that single gap caused the stale-IP outage. (token + path map already hot-swap via worker.py:270 / :254 but are not reliably wired to settings save.)
Target: Saving WorkerCoordinatorUrl / WorkerAuthToken / WorkerSourcePathMap updates the live dispatcher with no restart.
Files: add WorkerDispatcher.update_coordinator_url(url) mirroring update_auth_token (worker.py:270) and update_source_path_map (worker.py:254) - it must validate via coordinator_url.validate_coordinator_url and swap _base_url under the poll lock, then wakeup(). Wire the settings.save_patch path (the handler that processes changed_keys) so that when changed_keys intersects {KEY_WORKER_COORDINATOR_URL, KEY_WORKER_AUTH_TOKEN, KEY_WORKER_SOURCE_PATH_MAP} and a worker dispatcher is running, it calls the matching update_* method on the live dispatcher.
Data example: save WorkerCoordinatorUrl 'http://Layne-Server:7830' while running -> next poll hits the new URL; log "Coordinator URL hot-swapped A -> B".
Acceptance: change each of the three keys while the worker runs; the running dispatcher uses the new value on the next poll without Stop/Start; A1 banner clears.
Validation: tests/python/desktop/test_network_lifecycle_fixes.py (extend); manual two-machine.
Risk note: thread-safety - swap under the existing _active_job_lock/poll guard; do not break an in-flight claim.

Status 2026-06-14: complete in change packet MP-CHANGE-2026-0614-009. Implemented save-patch hot-apply wiring for WorkerCoordinatorUrl, WorkerAuthToken, and WorkerSourcePathMap when a worker dispatcher is already running; tightened dispatcher URL/token/path-map snapshots under the worker runtime lock; wakes the poll loop after hot swaps; returns token-safe network_worker_hot_apply evidence in the settings save result; updates running worker resolved-config evidence so the drift banner can clear after reload. Validation passed for focused lifecycle/worker-runtime/drift/settings-patch tests and the full desktop test_network*.py discovery suite. Manual two-machine validation remains operator-side.

## Phase C - Multi-library path mapping (OPERATOR PRIORITY)

### C1 (#2) - Advertise library roots + auto-derive the path map
Depends-on: A2 (path checks help validate) | Effort: M | Risk: med | §7: adds a read endpoint (no claim-contract change)
Problem: Every new library needs a hand-written WorkerSourcePathMap prefix. With movies+tv it is one prefix today only because both sit under ...\Encode; libraries on different roots/drives would each need a manual entry.
Target: The worker auto-builds the prefix map by pairing library_id between coordinator and worker config; operator adds a library on both sides and it just works. Manual WorkerSourcePathMap remains an override (manual entries win).
Files: coordinator: new auth-required GET /api/libraries -> [{library_id, source_root, output_root, designation}] from the coordinator's resolved library profiles (the same source the queue uses; coordinator source_root example movies=C:\Users\Layne\Videos\Encode\Movies). worker: on dispatcher start and on a refresh timer, GET /api/libraries; build auto_map = { coord.source_root -> worker.source_root for library_id in (coord ∩ worker) }; effective map = manual WorkerSourcePathMap merged over auto_map. Reuse parse_source_path_map / apply_source_path_map shape (path_map.py).
Data example: coord returns [{library_id:'movies', source_root:'C:\\Users\\Layne\\Videos\\Encode\\Movies'}, {library_id:'tv', source_root:'C:\\Users\\Layne\\Videos\\Encode\\TV'}]; worker movies root '\\LAYNE-SERVER\\Users\\Layne\\Videos\\Encode\\Movies', tv root '...\\Encode\\TV' -> auto_map has BOTH entries; WorkerSourcePathMap can be left blank.
Acceptance: with WorkerSourcePathMap='' but /api/libraries reachable, a claimed movies AND a claimed tv file both rewrite to accessible UNC paths (log "Path map rewrote"); adding a third library on both sides needs no manual map.
Validation: tests/python/desktop/test_network_path_auto_map.py (new); manual: blank WorkerSourcePathMap, restart worker, confirm path_map_entries>=2 and both libraries encode.
Migration note: keep WorkerSourcePathMap honored; document precedence (manual > auto).

Status 2026-06-14: complete in change packet MP-CHANGE-2026-0614-010. Implemented auth-required coordinator GET /api/libraries using resolved library profiles, worker-side automatic coordinator-root to worker-root mapping by matching library_id, manual WorkerSourcePathMap precedence over auto-derived entries, periodic worker refresh before idle claim attempts, and runtime descriptor evidence through the existing effective path-map fields. Validation passed for new tests/python/desktop/test_network_path_auto_map.py, targeted worker/coordinator/drift tests, and the full tests/python/desktop/test_network*.py discovery suite. Manual two-machine blank-map validation remains operator-side.

### C2 (#1) - Library-relative claims (durable fix)
Depends-on: C1 (library_id semantics) | Effort: M | Risk: HIGH | §7: YES (claim contract change)
Problem: ClaimResponse (protocol.py:52) ships only an absolute, coordinator-local source_path; the worker must reverse-map it.
Target: ClaimResponse also carries library_id and relative_path. Worker resolves worker.library_root(library_id) + relative_path FIRST; falls back to auto/manual prefix map (C1); falls back to raw source_path. Eliminates prefix matching entirely for in-library files.
Files: protocol.py:52 ClaimResponse add fields library_id:str, relative_path:str (to_dict/from_dict + a contract/schema version bump); coordinator_queue.py populate them from QueueRecord.relative_path (models.py:121 ALREADY EXISTS) and the record's library_id; worker_loops.py claim handling prefer (library_id, relative_path); update Docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md; bump any contract baseline (Docs/generated/WEBVIEW_PUBLIC_CONTRACT_BASELINE.json if claim is covered).
Data example: claim {job_id:'...', library_id:'movies', relative_path:'Cast Away (2000)...mkv', source_path:'C:\\Users\\Layne\\Videos\\Encode\\Movies\\Cast Away (2000)...mkv'}; worker movies root '\\LAYNE-SERVER\\...\\Encode\\Movies' -> resolved '\\LAYNE-SERVER\\...\\Encode\\Movies\\Cast Away (2000)...mkv'.
Acceptance: old workers ignore new fields (additive, back-compatible); new worker uses library-relative resolution with no path map at all; mixed-version cluster still works.
Validation: AGENTS §7 - do NOT self-certify. Run the full network suite (tests/python/desktop/test_network*.py) + contract tests; add test_network_library_relative_claim.py; require operator two-machine sign-off.

Status 2026-06-14: implementation complete in change packet MP-CHANGE-2026-0614-011. Implemented additive ClaimResponse library_id and relative_path fields with protocol version 2, coordinator population from queue records/resolved library roots, worker resolution that prefers library-relative paths before C1/manual prefix maps and raw source_path, snapshot-row library_id carry-forward, and safe relative-path rejection. Agent-side validation passed for the new tests/python/desktop/test_network_library_relative_claim.py coverage, targeted protocol/coordinator/path-map tests, the full tests/python/desktop/test_network*.py discovery suite, and contract payload/config tests. Operator two-machine sign-off remains required.

### C3 (#4) - Path-map row editor UI
Depends-on: none (complements C1/C2) | Effort: S | Risk: low | §7: no
Problem: WorkerSourcePathMap is a raw JSON string with backslash escaping (operator-hostile: '{"C:\\\\Users..." : "\\\\\\\\LAYNE-SERVER..."}').
Target: A table editor: rows of {From prefix, To prefix} + a "Test" button that resolves a sample claimed path locally and clearly labels the backend check as a generic saved-config preflight; serializes to the same JSON the backend expects.
Files: ui_web network/worker settings component; serialize to WorkerSourcePathMap; reuse A2 path check for "Test".
Acceptance: operator adds two rows without typing JSON; saved value parses via parse_source_path_map; Test shows accessibility per row.

Status 2026-06-14: complete in change packet MP-CHANGE-2026-0614-012. Implemented a WebView row editor for WorkerSourcePathMap in the Network settings panel and Worker setup dialog, backed by the existing hidden JSON setting so backend parsing/persistence remains unchanged. Rows collect From prefix, To prefix, and sample claimed path; staging serializes complete rows to WorkerSourcePathMap JSON and blocks partial rows; row Test shows a local rewrite preview plus the existing backend-owned saved-config preflight, not row-specific accessibility proof. Validation passed for targeted WebView/static Local API tests, npm WebView asset/lint checks, the WebView Network browser smoke, the Settings builder browser smoke, and an in-app Browser sanity check against the backend-served Network setup dialog.

### C4 (#3) - (Alternative) UNC-canonical addressing on the coordinator
Depends-on: none | Effort: M | Risk: med-high | §7: YES (coordinator path identity)
Problem/Target: Instead of per-worker mapping, the coordinator normalizes library roots to their share (UNC) form at enqueue so coordinator AND every worker use identical paths; no mapping anywhere. This is an EITHER/OR with C1+C2 - choose one strategy; do not ship both. Recommended only if the operator prefers a single canonical addressing scheme over per-worker library roots.
Risk: changes media path identity (AGENTS §9) - dedupe/hash/sidecar logic keys on path; full validation required.

Status 2026-06-14: skipped by design in change packet MP-CHANGE-2026-0614-013. C1 and C2 implement the recommended per-worker library-root strategy, and this item is explicitly alternative-to C1+C2 with a "do not ship both" constraint. UNC-canonical addressing remains available only as a future operator-selected strategy that would require a separate high-validation path identity change.

## Phase D - Zero-touch setup

### D1 (#9) - Pairing code / join file
Depends-on: C1 (library advertise) | Effort: M | Risk: med | §7: handles secrets
Problem: Setup means hand-copying a 64-hex token AND typing a URL - the exact source of failure modes 1 and 2.
Target: Coordinator generates a one-time join blob = base64(JSON {coordinator_url, token, libraries[]}) or a short pairing code resolved over the LAN. Worker "Join cluster" imports it -> sets WorkerCoordinatorUrl + WorkerAuthToken + seeds auto-map, then runs A2 test-connection.
Files: coordinator command to mint a join blob (rotate-aware via coordinator_auth.update_auth_token); worker import command; never log the blob; treat as a secret.
Acceptance: paste blob on a fresh worker -> connected + paths verified with zero manual field entry.

Status 2026-06-14: complete in change packet MP-CHANGE-2026-0614-014. Implemented secret-safe coordinator join blob creation and worker join import routes, strict command payloads, unjournaled contract metadata, backend join-blob encode/decode validation, app-state/generated coordinator token handling, optional token rotation, worker settings save plus auto path-map seeding from advertised libraries, immediate worker test-connection execution, and WebView create/copy/import controls with token/blob-safe result rendering. Validation passed for focused Python backend/API/WebView tests, WebView asset/lint checks, the browser Network smoke wrapper, and the Local API lifecycle contract smoke when run with `PYTHONPATH=src`. No source, scratch, output, pending-publish, FFmpeg, subtitle, audio, queue-processing, or media-policy behavior was changed.

### D2 (#8) - mDNS auto-discovery
Depends-on: none | Effort: S (packaging) | Risk: low | §7: no
Problem: Coordinator log: "mDNS advertisement unavailable; ... zeroconf is not installed." Workers must type IP/host; DHCP changes (192.168.1.50 vs .0.161) break them.
Target: Bundle zeroconf; coordinator advertises _mediapipeline._tcp; worker discovers and offers coordinators to pick. Survives IP changes.
Files: requirements\*.txt add zeroconf into apps\desktop\runtime\Python; the advertisement code path already exists (it only warns when the import fails) - verify and enable; add a worker discovery UI list.
Acceptance: worker with blank WorkerCoordinatorUrl sees the coordinator in a discovery list and one-click connects.

Status 2026-06-14: complete in change packet MP-CHANGE-2026-0614-015. Added `zeroconf` to the Python dependency declarations, exposed backend-owned POST `/api/network/worker/discover-coordinators`, normalized/deduplicated mDNS coordinator URLs with malformed-result warnings, kept the command read-only and unjournaled, and added a Network WebView discovery list whose Use action stages Worker mode and `WorkerCoordinatorUrl` through the existing Distributed Settings patch flow. Validation passed for focused mDNS/API/WebView tests, the browser Network smoke wrapper, WebView asset/lint checks, and the full `tests/python/desktop/test_network*.py` suite. Manual live LAN mDNS discovery remains operator-side.

### D3 (#10) - Capability / accessibility handshake
Depends-on: C1, A2 | Effort: M | Risk: med | §7: affects dispatch
Problem: A worker that cannot reach a library still gets those jobs (then fails+requeues).
Target: On register/heartbeat the worker reports accessible_library_ids (A2 L3 check); coordinator only dispatches jobs whose library_id the worker can access and shows per-worker capability ("Movies,TV ok; Anime unreachable").
Files: register/heartbeat payload (protocol.py) + coordinator dispatch filter (coordinator_queue.py) + dashboard.
Acceptance: a worker missing the TV share is never handed TV jobs; dashboard shows why.

Status 2026-06-14: complete in change packet MP-CHANGE-2026-0614-016. Added additive `accessible_library_ids` protocol fields, worker-side library source-root reachability reporting during claim and heartbeat, coordinator registry persistence for active/idle worker capability evidence, dispatch filtering that skips library-tagged jobs outside a requesting worker's reported accessible IDs, and Network WebView detail rendering for accessible libraries. Validation passed for focused protocol/workflow/worker tests, the full `tests/python/desktop/test_network*.py` suite, WebView asset checks, browser Network smoke, and library-relative/auto-map regression tests. No source, scratch, output, pending-publish, FFmpeg, subtitle, audio, publish/drain, cleanup, or media-policy behavior was changed.

## 4. Dependency graph (text)

A1, A2 independent. A3 -> A2. A4 -> A3. B1 -> A1. C1 -> A2. C2 -> C1. C3 independent. C4 alternative-to (C1+C2). D1 -> C1. D2 independent. D3 -> C1,A2.

## 5. Rollback / safety
- Back up every psd1 before edit (Copy-Item *.bak_<ISO>). Today's backups: coordinator MediaPipeline_config.bak_claude_20260614_120011.psd1; worker MediaPipeline_config.bak_realedit_20260614_121356.psd1.
- Contract changes (C2, C4) must be additive and version-bumped so a mixed-version cluster keeps working; keep a feature flag to disable library-relative resolution if a regression appears.
- After each item: run tests/python/desktop/test_network*.py with apps\desktop\runtime\Python\python.exe and record the result in docs/SESSION.md.

## 6. Open questions for the operator
- C2 vs C4: prefer per-worker library roots (C1+C2) or one UNC-canonical scheme (C4)? (Recommended: C1+C2.)
- CoordinatorMaxJobRetries default (proposed 3) and quarantine behavior (block job vs flag worker)?
- Should outputs also be library-relative (publish to worker-local output root vs coordinator-canonical output)?

---

## Phase E - Coordinator as source of truth (centralized processing policy)

Added 2026-06-14 per operator direction: the coordinator should be the single source of truth for HOW media is processed; workers should contribute ONLY hardware-specific execution.

Principle - split POLICY from HARDWARE EXECUTION:
- POLICY (coordinator-authoritative, per library): target codec FAMILY (hevc/av1/h264), quality tier, output container, routing profile + thresholds, size guards, audio policy, subtitle policy, naming/output structure, promotion.
- HARDWARE EXECUTION (worker-only): which local encoder implements the family (hevc_nvenc / hevc_qsv / hevc_amf / libx265), encoder-specific preset, hardware decode, concurrency/resource limits.

Current state (the inversion to fix): the worker IGNORES the claim encode_config and runs `start_pipeline(resolved=worker_config, single_file=...)` (`application/network_lifecycle_provider.py:574`). `snapshot_encode_config` (`network/encode_config_snapshot.py:51`) ships only GLOBAL keys and the coordinator LITERAL codec; per-library overrides are not captured. So each worker decides everything from its own config. Verified 2026-06-14: worker GamingPC global `VideoCodec=hevc_nvenc`, movies+tv inherit it; coordinator `VideoCodec=libx265`, `CoordinatorAlsoEncodeLocally=$false`.

CRITICAL design constraint: do NOT ship the coordinator literal codec for the worker to apply verbatim. The coordinator is `libx265` (CPU); applying that on the NVIDIA worker would FORCE CPU x265 and lose NVENC. Codec MUST travel as a hardware-neutral FAMILY and be mapped to an encoder per worker.

### E1 (#13) - Coordinator ships per-library RESOLVED, hardware-neutral policy
Depends-on: C1, C2 | Effort: M | Risk: HIGH | §7: YES (settings schema + claim contract)
Problem: `snapshot_encode_config` captures only global keys and a literal encoder string; per-library coordinator settings never reach the worker.
Target: when building a claim, resolve the claimed file's library policy via `core/config/library_profile_normalization.py:307 library_profiles_from_config` (effective per-library values) and ship a hardware-neutral policy block: `target_codec_family`, `quality_tier`, `output_container`, `routing_profile`, route thresholds, size guards, audio/subtitle policy, with a `policy_schema_version`.
Files: `network/encode_config_snapshot.py` (per-library resolve + family mapping), `network/coordinator_http_handlers.py` claim build (already calls `claim_library_fields_for_record`; add the policy), `network/protocol.py` ClaimResponse.encode_config documented shape.
Codec family map (literal -> family): {libx265, hevc_nvenc, hevc_qsv, hevc_amf -> hevc}; {libaom-av1, av1_nvenc, av1_qsv -> av1}; {libx264, h264_nvenc, h264_qsv -> h264}.
Acceptance: a claim for a movies file carries `target_codec_family=hevc` (+ quality tier, container, routing) derived from the coordinator movies library, regardless of which literal encoder the coordinator is set to.

Status 2026-06-15: agent implementation complete in change packet MP-CHANGE-2026-0614-018. `snapshot_encode_config` now attaches a versioned `__coordinator_policy` block resolved from coordinator library profiles, with hardware-neutral codec family, quality tier, output container, routing thresholds, size guards, audio policy, and subtitle policy. Targeted unit coverage proves library-resolved hardware-neutral claims; representative real-media validation remains required before enabling this broadly.

### E2 (#14) - Worker applies coordinator policy + maps family -> local encoder
Depends-on: E1, E3 | Effort: M-L | Risk: HIGHEST | §7: YES (FFmpeg command generation + routing)
Problem: `network_lifecycle_provider.py:574` ignores `job.encode_config`; the worker uses its own full config.
Target: build an EFFECTIVE per-job config = coordinator policy overlaid on a minimal worker hardware profile. Resolve `target_codec_family` -> local encoder via E3 map, translate `quality_tier` -> encoder param via E4, then run `start_pipeline` with that effective config (write a per-job effective config file or pass overrides) instead of the worker full own config.
Files: `network_lifecycle_provider._start_network_claimed_job` (consume `job.encode_config`), new effective-config builder, `service.start_pipeline` override path.
Precedence: coordinator policy wins for ALL non-hardware settings; worker supplies ONLY encoder impl + encoder-specific preset + concurrency/resource limits.
Acceptance: with coordinator movies policy `target_codec_family=hevc, quality_tier=T, container=mkv`, the NVIDIA worker encodes with `hevc_nvenc` at the translated quality and mkv; a CPU-only worker fulfills the SAME policy with `libx265`. Changing the policy on the coordinator changes both workers' output without touching either worker config.

Status 2026-06-15: agent implementation complete in change packet MP-CHANGE-2026-0614-018. Worker launch now materializes a per-job effective PSD1 only when `WorkerHonorCoordinatorPolicy` is enabled; otherwise it keeps the original per-worker config as the mixed-version fallback. The effective config overlays coordinator policy for non-hardware media settings and leaves worker hardware execution local. Representative real-media validation remains required because this touches encode behavior.

### E3 (#15) - Worker hardware-encoder capability map (the only per-worker encode setting)
Depends-on: none | Effort: M | Risk: med | §7: settings schema
Target: a worker config block (+ optional auto-detect) declaring per-family local encoders, e.g. `WorkerEncoderMap = {"hevc":"hevc_nvenc","av1":"av1_nvenc","h264":"h264_nvenc"}`; CPU fallback `{"hevc":"libx265",...}`. Optional detection via `ffmpeg -encoders` + `nvidia-smi`. Coordinator (Intel) would map hevc->hevc_qsv/libx265 but never encodes (`CoordinatorAlsoEncodeLocally=$false`).
Acceptance: worker resolves each family to a supported local encoder; unknown/unsupported family falls back to CPU with a logged warning.

Status 2026-06-15: agent implementation complete in change packet MP-CHANGE-2026-0614-018. Added `WorkerEncoderMap` as the worker-local hardware map with CPU fallback for unsupported, missing, or unparsable entries; runtime drift evidence fingerprints the map without exposing raw encoder text.

### E4 (#16) - Quality-tier translation across encoders
Depends-on: E1 | Effort: M | Risk: med-high | §7: YES (encode quality)
Problem: CRF (libx265) and CQ (nvenc) scales are not interchangeable; a raw number is not portable across encoders.
Target: coordinator expresses quality as a TIER (or per-family target); worker translates tier -> encoder-specific param via a documented table, with optional per-worker fine-tune.
Acceptance: the same coordinator quality tier yields visually comparable output on nvenc vs libx265; mapping table documented and unit-tested.

Quality tier translation table:
| Coordinator tier | CPU encoder value (CRF-style) | Hardware encoder value (CQ-style) |
|------------------|-------------------------------|-----------------------------------|
| very_high        | 18                            | 17                                |
| high             | 20                            | 19                                |
| standard         | 22                            | 21                                |
| compact          | 26                            | 25                                |

Status 2026-06-15: agent implementation complete in change packet MP-CHANGE-2026-0614-018. The worker translates coordinator quality tiers through the table above and unit tests cover both hardware and CPU fallback values. Visual comparability still requires representative real-media validation.

### E5 (#17) - UI authority cues + drift
Depends-on: E1, E2, E3 | Effort: S-M | Risk: low | §7: no
Target: coordinator Settings marks per-library processing policy as "cluster-authoritative (applies to all workers)"; worker Settings shows only the hardware encoder map as locally-owned and that other settings come from the coordinator; extend the A1 drift banner to flag when a worker would diverge from coordinator policy.

Status 2026-06-15: agent implementation complete in change packet MP-CHANGE-2026-0614-018. Network/Home drift evidence now includes a policy-divergence payload; the WebView Network page surfaces coordinator policy authority, worker-local execution ownership, the worker hardware-map control, and the guarded `WorkerHonorCoordinatorPolicy` control. Default-off policy remains a review cue until operator validation enables it intentionally.

Rollout / safety: gate behind `WorkerHonorCoordinatorPolicy` (default OFF). With the flag off, current behavior (worker uses its own config) persists, so this ships safely and is reversible. This is the LARGEST §7 change in the plan (FFmpeg command generation + settings schema + routing) - additive, version-bumped, real-media validated per AGENTS §5/§8, with a mixed-version fallback to per-worker config.

Dependencies: E1 -> (C1,C2). E2 -> (E1,E3). E4 -> E1. E5 -> (E1,E2,E3). E3 independent.
