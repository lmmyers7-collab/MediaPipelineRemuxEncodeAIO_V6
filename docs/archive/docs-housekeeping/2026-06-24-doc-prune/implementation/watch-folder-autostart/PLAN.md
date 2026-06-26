# Watch-folder / event-driven auto-start — Implementation plan for Codex

Status: PLAN (not implemented). Written 2026-06-11 by Claude Code at the operator's request.
Implementing agent: Codex. Authority order: AGENTS.md > docs/SESSION.md > this plan.
Citation baseline: branch `refactor/mediapipeline-entrypoint-slice`, commit `eacea171`,
2026-06-11. Line numbers WILL drift — re-verify every `path:line` with Grep before editing.
Do not start implementation without the operator-approved docs/SESSION.md scope block in §14.

---

## 0. One-paragraph goal

When a new media file lands under a watched source root, the local-API backend detects it
within seconds, and — depending on configuration — either (a) records it as pending work and
surfaces it in the UI ("enqueue_only"), or (b) requests a pipeline launch through the exact
same gated command path the Launch button uses ("enqueue_and_launch"). Off by default.
Zero new media policy: the feature only *triggers* existing flows; it never touches media,
queue state, publish state, or FFmpeg behavior.

## 1. Corrections to the original brief (read first — the brief has stale paths)

The operator's draft brief was written against an older layout. The repository has since
moved everything from `DesktopApp/` and `app/` into `src/mediapipeline/`. Corrections:

| Brief said | Reality (verified 2026-06-11) |
| --- | --- |
| `app/processes/lifecycle.py` | `src/mediapipeline/core/processes/lifecycle.py` (`ProcessLifecycleServiceMixin`). But the correct lifecycle template is `ScheduleStopWatcherManager` — see §4. |
| "facade.py → process facade" | `src/mediapipeline/desktop/application/facade.py` (`MediaPipelineApplicationFacade`) composes `PipelineLaunchFacadeMixin` from `src/mediapipeline/core/processes/pipeline_facade.py`; the single safe entrypoint is `start_pipeline_process(resolved, request)` at `pipeline_facade.py:67`. |
| "enqueue into the existing queue" | **There is no persistent enqueue API.** The queue plan is derived by scanning source roots at launch (`src/mediapipeline/core/queue/source_inventory.py` — `build_queue_source_inventory()`, `queue_inventory_source_roots()`; engine side `ops/pipeline/engine/queue/queue_plan.ps1`). A file sitting in a source root IS enqueued for the next run. Therefore `enqueue_only` = detect + surface in UI; `enqueue_and_launch` = detect + request a launch. Nothing is ever "inserted" anywhere. |
| "use watchdog or FileSystemWatcher" | **Neither.** `watchdog` is not a dependency (verified: zero hits outside two docs), the Python runtime is a bundled CPython at `apps/desktop/runtime/Python/`, and the real source roots are SMB UNC paths (`\\LAYNE-SERVER\...`) where change notifications are unreliable. Decision (locked): hand-rolled stdlib polling scanner. No new dependency of any kind. |
| "respect worker_mutex.ps1" | The Python launch path already serializes launches (`_acquire_process_launch_lock` + `_active_work_block_message`, used at `pipeline_facade.py:88-94`); `ops/pipeline/engine/queue/worker_mutex.ps1` remains the engine-side last line of defense. The watcher gets all of this for free by calling `start_pipeline_process` and MUST NOT reimplement or touch any of it. |

A useful idempotency property that simplifies everything: because the queue is scan-derived
and duplicate detection lives in the engine, **triggering a launch when there is nothing new
to do is harmless** (the run scans, finds nothing actionable, exits). The watcher therefore
never needs to know whether a specific file was processed; it only needs "a launch happened
after I detected work."

## 2. Locked decisions (do not re-litigate; deviations need operator approval)

1. Polling scanner, stdlib only (`os.scandir`), injectable clock. No watchdog, no .NET
   FileSystemWatcher, no new pip package, no Rust/Tauri change.
2. Default `WatchAction = enqueue_only`. Auto-launch is opt-in.
3. `EnableWatchFolders` defaults to **false** in every registry, schema, template, and
   profile. Disabled means: no thread started, zero filesystem reads.
4. Auto-launch uses pipeline mode `"once"` (valid modes are
   `{"continuous","once","validate","drain_pending_pushes"}` —
   `src/mediapipeline/core/processes/pipeline_policy.py:15`).
5. Network role gating (`NetworkRole` key, choices `standalone|coordinator|worker`, defined
   in `src/mediapipeline/core/config/metadata_parts/network_fields.py`):
   `worker` → watcher fully disabled (reason surfaced); `coordinator` → scanning allowed but
   action forced to `enqueue_only`; `standalone` → configured action.
6. All launches go through `MediaPipelineApplicationFacade` →
   `PipelineLaunchFacadeMixin.start_pipeline_process`. Never call
   `service.start_pipeline`/`spawn` directly, never build MediaPipeline.ps1 args.
7. v1 uses the global `ValidExtensions` list only (per-profile extension overrides are a
   documented follow-up, not in scope).
8. Watcher state is surfaced on the **Schedule page**
   (`apps/desktop/webview/static/assets/scheduleView.js`), read-only, plus one new read-only
   API route. No new mutation routes in v1 (config changes go through the existing Settings
   flow).
9. Poll interval is an internal module constant (`WATCH_POLL_INTERVAL_SECONDS = 10`), not a
   config key. The five config keys are exactly the five in §5.
10. The watcher is **not** "active work": it must never block close-readiness or shutdown.

## 3. Verified architecture map (all paths confirmed to exist)

Trigger sources today (the watcher becomes the fourth; it must coexist with all three):
- Manual Launch: WebView Launch page → command route → facade →
  `start_pipeline_process` (`src/mediapipeline/core/processes/pipeline_facade.py:67`) →
  `service.start_pipeline` (`src/mediapipeline/core/processes/lifecycle.py:79`) →
  `start_pipeline_for_service` (`src/mediapipeline/core/processes/launch_runner.py:30`) →
  spawns `ops/pipeline/entrypoints/MediaPipeline.ps1`.
- Schedule: schedule gate `resolve_pipeline_start_schedule_gate()` /
  `normalize_schedule_override()` in `src/mediapipeline/core/processes/schedule_policy.py`;
  `schedule_override == "ignore"` bypasses the gate (`pipeline_facade.py:51`).
- Network mode: `src/mediapipeline/desktop/network/` (coordinator/worker);
  role from config key `NetworkRole`.

Gating inside `start_pipeline_process` (all inherited for free, in order):
config-identity block → mode validation → sleep/extra-args validation → schedule gate →
`_acquire_process_launch_lock` → `_active_work_block_message` → runtime prep → spawn →
arm schedule-stop watcher. A second launch while work is active returns a refusal
`CommandResult`, it does not raise.

Lifecycle template (copy this pattern exactly):
- `ScheduleStopWatcherManager` in
  `src/mediapipeline/desktop/application/schedule_stop_watcher.py` — a thread-based
  background manager owned by the facade.
- Instantiated at `src/mediapipeline/desktop/application/facade.py:114`
  (`self._schedule_stop_watcher = ScheduleStopWatcherManager()`).
- Stopped from `LocalApiServer.stop()` at `src/mediapipeline/desktop/api/server.py:102-117`
  (it looks up `facade._cancel_pipeline_schedule_stop_watcher` and calls it before HTTP
  shutdown; threads joined with a 2.0 s timeout).
- Backend entry: `src/mediapipeline/desktop/local_api_main.py` builds the backend, creates
  `LocalApiServer(...)` (~line 255), `server.start()` (~line 351); startup progress steps
  come from `src/mediapipeline/desktop/backend_bootstrap.py` (`startup_step()`).

Read-route pattern (copy for the status route):
- Route table: `src/mediapipeline/desktop/api/routes_read.py` (e.g. line 16:
  `"/api/backend/close-readiness": RouteHandlerSpec("_close_readiness_payload")`).
- Payload builder: `src/mediapipeline/desktop/api/read_payloads_status.py:69`
  (`_close_readiness_payload`, delegates to the facade, has an unavailable-fallback in
  `read_payloads_policy.py`).
- Contract entry: `src/mediapipeline/desktop/api/contract_read.py` (close-readiness entry at
  ~line 94 with `response_schema": "desktop_close_readiness.v1"`).
- Governance docs that tests enforce: `docs/inventories/API_ROUTE_INVENTORY.md`,
  `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md` (see `test_api_route_inventory`).

Existing config keys the watcher reuses (do NOT redefine them):
- `FileStabilityWait` — "Seconds to wait after a source file stops growing before
  processing it" (`docs/architecture/CONFIG_KEY_GLOSSARY.md:39`); enforced engine-side in
  `ops/pipeline/engine/probe/media_probe.ps1` / `ops/pipeline/engine/process/pipeline_processing.ps1`.
  The engine re-checks stability at processing time, so even if the watcher fires early the
  engine still protects the file. The watcher's debounce is a triggering courtesy, not the
  safety mechanism.
- `ValidExtensions` — extension allowlist (`CONFIG_KEY_GLOSSARY.md:42`).
- `LibraryProfiles` — list of profile dicts (`src/mediapipeline/contracts/config.py:655`);
  helper module `src/mediapipeline/core/config/library_profiles.py`; the queue already
  derives scan roots from it via `queue_inventory_source_roots()` in
  `src/mediapipeline/core/queue/source_inventory.py`. Reuse that helper (or the underlying
  library_profiles function it calls — read both files first) for the default watch roots.

## 4. New module layout

```
src/mediapipeline/desktop/watch/
    __init__.py        # exports WatchFolderManager, watch_folder_state_mapping
    scanner.py         # pure logic: snapshots, diff, stability, dedupe. NO threads, NO config, NO facade imports.
    manager.py         # WatchFolderManager thread + cycle logic + state. Imports scanner only.
```

Layout rule (AGENTS.md §2): desktop-only adapters belong under
`src/mediapipeline/desktop/`; do not create files under any legacy path, do not create
`facade_*.py`/`service_*.py` named files.

### 4.1 `scanner.py` — pure, fully unit-testable contract

- `scan_root(root: str, extensions: frozenset[str]) -> dict[str, tuple[int, int]]`
  Recursive `os.scandir` walk (`follow_symlinks=False`), returns
  `{absolute_path: (size_bytes, mtime_ns)}` for files whose suffix (casefolded, with and
  without leading dot normalized) is in `extensions`. Per-directory `OSError` /
  `PermissionError` is caught and recorded (return a `(snapshot, errors)` pair or raise a
  dedicated `RootScanError` carrying partial results — pick one, test it). A completely
  unreachable root must produce a degraded result, never an unhandled exception.
- `class StabilityTracker` — injectable monotonic clock. `observe(path, stat, now)` records
  observations; a path becomes *stable* when the same `(size, mtime_ns)` has been observed
  at least twice with the observations spanning `>= debounce_seconds`. Growing/changing
  files reset their span. `pop_stable(now) -> list[str]` returns newly stable paths once.
- `class FiredRegistry` — dedupe so one file fires once. Keyed by
  `(path_casefolded, size, mtime_ns)`; bounded (max 10_000 entries, oldest evicted); entries
  expire after 24 h so a genuinely re-copied file (new mtime) can fire again. Windows paths:
  compare casefolded.
- No `time.sleep`, no `datetime.now()` calls inside logic — clocks are parameters.

### 4.2 `manager.py` — `WatchFolderManager` contract

Model the public surface on `ScheduleStopWatcherManager` (read
`schedule_stop_watcher.py` fully before writing this file — mirror its state-mapping and
locking idioms, including how messages/reasons are surfaced).

- Constructed with no arguments in the facade `__init__` (next to line 114).
- `start(context: WatchContext) -> None` — idempotent; spawns one daemon thread named
  `MediaPipelineWatchFolders`.
- `stop(reason: str) -> None` — sets a `threading.Event`, joins with timeout 2.0 s,
  idempotent, never raises.
- `run_single_cycle(now: float | None = None) -> None` — the entire per-tick behavior, so
  tests never need the thread. The thread loop is just
  `while not stop_event.wait(WATCH_POLL_INTERVAL_SECONDS): run_single_cycle()`, wrapped so
  any exception is recorded in state (`last_error`) and the loop continues.
- `state_mapping() -> dict` — JSON-safe snapshot for the API (see §7 for required fields).
  Guard all shared state with one `threading.Lock`; `state_mapping` must not block on I/O.

`WatchContext` (small dataclass defined in `manager.py`) carries facade-supplied callables —
this keeps the manager testable with fakes and avoids the manager importing facade modules:
- `load_settings() -> Mapping[str, Any]` — current effective config values (the facade
  already has resolved config access; reuse whatever accessor
  `start_pipeline_process`/settings reads use — find it by reading
  `facade.py` and `read_payloads_status.py`, do not invent a new config loader).
- `default_watch_roots() -> list[str]` — enabled LibraryProfiles source roots (reuse the
  queue helper, §3 last bullet).
- `start_pipeline(request: dict) -> CommandResult` — bound by the facade to a thin wrapper
  that resolves paths the same way the command route does and calls
  `self.start_pipeline_process(resolved, request)`.
- `log(message: str) -> None` — reuse the same logging style schedule_stop_watcher uses.

Per-cycle algorithm (write it exactly like this):
1. Reload settings via `load_settings()`. On failure: keep last good settings, set degraded
   reason, continue. (Optional optimization: cache on config-file mtime.)
2. If `EnableWatchFolders` is falsy or `NetworkRole == "worker"` → ensure idle state
   (record reason), clear nothing else, return. (Toggling the setting must take effect
   without a backend restart — this is why settings reload per cycle.)
3. Effective roots = `WatchFolderRoots` if non-empty else `default_watch_roots()`.
   Normalize, drop duplicates, record per-root reachability in state.
4. Effective extensions = `ValidExtensions` from settings.
   Effective debounce = `WatchDebounceSeconds` if set else `FileStabilityWait` value,
   clamped to `>= 5`.
5. Scan each root; feed snapshots into `StabilityTracker`. Files present in the very first
   snapshot after (re)start or after a roots/extension change are treated as *baseline* and
   never fire (only files that appear or change after baseline can fire). This prevents a
   restart from "detecting" an entire existing library.
6. For each newly stable path not in `FiredRegistry`: register it, append to the rolling
   `recent_detections` list (cap 50), set `pending_work = True`.
7. Action dispatch when `pending_work` is true:
   - Effective action = `enqueue_only` if `NetworkRole == "coordinator"` else `WatchAction`.
   - `enqueue_only` → nothing further (state shows pending count; next manual/scheduled run
     picks the files up because the queue is scan-derived).
   - `enqueue_and_launch` → at most one launch attempt per cycle: build the request
     ```python
     request = {"mode": "once", "show_config": False, "show_console": False, "extra_args": ""}
     # sleep_seconds: pass the same default the policy accepts — read
     # parse_pipeline_sleep_seconds in pipeline_policy.py and mirror the WebView default
     # from launchView.js; do NOT guess a literal here.
     if not WatchRespectScheduleWindow: request["schedule_override"] = "ignore"
     ```
     Call `context.start_pipeline(request)`. On success result → `pending_work = False`,
     record `last_launch` (timestamp, pid/message from the CommandResult). On refusal
     (active work, schedule gate closed, config blocked) → keep `pending_work = True`,
     record the refusal reason, retry next cycle. Refusals are EXPECTED outcomes, not
     errors: with `WatchRespectScheduleWindow = True` and the window closed, the retry loop
     IS the "launch when the window opens" behavior.
8. Update `last_cycle_completed_utc` in state.

Concurrency rules (the entire point of this feature being safe):
- The manager never spawns processes, never touches
  `ops/pipeline/engine/queue/worker_mutex.ps1`, control flags, active-job records, runtime
  artifacts, or the schedule-stop watcher. Those belong to the launch path it calls.
- One manager instance, one thread, one in-flight launch attempt (the cycle is
  single-threaded by construction).
- A manual Launch or schedule launch racing the watcher is resolved by the existing launch
  lock + active-work block inside `start_pipeline_process`; the watcher just receives a
  refusal and retries later. Verify with the race test in §10.

## 5. Config keys (new, exactly five) — AGENTS.md §7 settings-schema territory

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `EnableWatchFolders` | bool | `$false` / `False` | Master switch. Off = no thread, no I/O. |
| `WatchFolderRoots` | list[str] | `@()` / `[]` | Explicit roots. Empty = derive from enabled LibraryProfiles source roots. |
| `WatchDebounceSeconds` | int | `30` (min 5) | Watcher-side stability span before a file fires. Falls back to `FileStabilityWait` when unset/zero. |
| `WatchAction` | enum string | `enqueue_only` | `enqueue_only` \| `enqueue_and_launch`. |
| `WatchRespectScheduleWindow` | bool | `$true` / `True` | True: launches go through the schedule gate (deferred-until-window-open). False: pass `schedule_override="ignore"`. |

Registration is mirrored across both the Python and PowerShell config systems and is
enforced by tests. **Method: pick the tracer key `CoordinatorPort` (a recently added,
desktop-consumed key), run `rg -l "CoordinatorPort"` at the repo root, and add the five new
keys in a parallel way at every hit that is a registry/schema/metadata/doc (skip
network-specific logic files).** As of 2026-06-11 that footprint is:

1. `src/mediapipeline/contracts/config.py` — pydantic fields with defaults/constraints
   (enum via `Literal`, list via `default_factory`), placed in a sensible section, plus the
   ordered-key lists near lines 78/227 (there are TWO ordered lists — add to both, the
   existing tests will catch a miss).
2. Regenerate `src/mediapipeline/contracts/schemas/config.v1.schema.json`:
   `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.generate_config_schema`
   (never hand-edit; the tool has `--check` for verification).
3. `src/mediapipeline/core/kernel/config_keys.py` (KEY_* constants),
   `src/mediapipeline/core/kernel/config_key_order.py`,
   `src/mediapipeline/core/kernel/config_key_groups.py` (new "Watch Folders" group or the
   group the operator's settings layout suggests),
   `src/mediapipeline/core/kernel/config_key_aliases.py` only if aliasing is required (it is
   not — no legacy spelling exists).
4. Settings-page metadata: new
   `src/mediapipeline/core/config/metadata_parts/watch_fields.py` following
   `network_fields.py` exactly (page/section/key/label/kind/choices/default/help), wired
   wherever `NETWORK_CONFIG_FIELD_DEFINITIONS` is aggregated
   (`src/mediapipeline/core/config/metadata.py` and `metadata_parts/__init__` — follow the
   imports). Suggested page: "Schedule" (keeps trigger config beside schedule config) —
   confirm with the operator if ambiguous; do not invent a new page without approval.
5. Engine registry: `ops/pipeline/engine/config/config_keys.ps1`,
   `ops/pipeline/engine/config/default_values.ps1`,
   `ops/pipeline/engine/config/schema_keys.ps1`. The engine does not consume these keys, but
   the registry checks assert registry/schema/order parity, and the entrypoint config loader
   must accept them as known keys.
6. `ops/pipeline/config/schemas/media_pipeline_config.schema.json` — properties + any
   enum, mirroring the engine registry.
7. `ops/pipeline/config/MediaPipeline_config_template.psd1` and
   `ops/pipeline/config/profiles/Default.psd1` — commented defaults, disabled.
8. WebView: `apps/desktop/webview/static/assets/settingsMetadata.js` display/order bindings
   (backend field_definitions own labels/defaults/validation — see the comment at the top of
   that file) and the matching settings view builder
   (`settingsView.builders.*.js` — follow how the Network section was added).
9. Docs: `docs/architecture/CONFIG_KEY_GLOSSARY.md` (five rows),
   `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`,
   `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`.

Gate for this whole section:
`pwsh -File ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1` (asserts engine
registry vs key order vs schema parity and will name exactly what you missed) and
`pwsh -File ops\pipeline\tests\Unit\Invoke-ContractSchemaChecks.ps1`, plus the Python
settings/config unit tests (`tests/python/desktop/test_service_config_validation.py` and
neighbors). Run them before moving past Phase 1.

## 6. Lifecycle wiring

1. Facade: in `MediaPipelineApplicationFacade.__init__`
   (`src/mediapipeline/desktop/application/facade.py`, next to the schedule-stop watcher at
   line 114): `self._watch_folder_manager = WatchFolderManager()`. Add two thin facade
   methods mirroring the existing watcher hooks:
   `_start_watch_folder_manager()` (builds `WatchContext` with the bound callables) and
   `_stop_watch_folder_manager(reason: str)` (delegates to `manager.stop`, safe when never
   started). Add `get_watch_folder_state() -> dict` returning
   `self._watch_folder_manager.state_mapping()`.
2. Backend startup: in `src/mediapipeline/desktop/local_api_main.py`, after the backend is
   built and config is resolved (near `server.start()`, ~line 351 — read the surrounding
   startup-step sequence first), call `facade._start_watch_folder_manager()` and emit a
   startup step `watch_folders` via the existing `startup_step()` helper
   (`src/mediapipeline/desktop/backend_bootstrap.py`) with outcome text one of:
   `disabled`, `started (N roots)`, `degraded: <reason>`. Starting the manager when
   `EnableWatchFolders` is false is fine and preferred — the manager idles cheaply and picks
   up a later settings toggle (decision in §4.2 step 2); but it must not scan while
   disabled.
3. Shutdown: in `LocalApiServer.stop()` (`src/mediapipeline/desktop/api/server.py:102`),
   immediately after the existing `_cancel_pipeline_schedule_stop_watcher` call, look up
   `facade._stop_watch_folder_manager` with the same `getattr`-and-callable pattern and call
   it with reason `"local API server stopping"`. Keep the same defensive style (never raise
   from stop()).
4. Close-readiness: NO changes to close-readiness logic. The watcher is not active work.
   Add a regression test asserting the close-readiness payload is unchanged/safe while the
   watcher is running (§10).
5. Tauri: no Rust changes. The Tauri shell already drives backend shutdown through the
   local-API lifecycle; the server.stop() hook covers it. Do not touch
   `apps/desktop/tauri/`.

## 7. Status API route + Schedule page card

Route (read-only, no mutation): `GET /api/watch-folders/status`.
- `src/mediapipeline/desktop/api/routes_read.py`: add
  `"/api/watch-folders/status": RouteHandlerSpec("_watch_folders_status_payload")`.
- `src/mediapipeline/desktop/api/read_payloads_status.py`: add
  `_watch_folders_status_payload()` following `_close_readiness_payload` (`:69`) including
  the facade-unavailable fallback pattern from `read_payloads_policy.py`.
- `src/mediapipeline/desktop/api/contract_read.py`: add the contract entry,
  `response_schema: "desktop_watch_folders.v1"`, purpose text, read-only classification.
- Payload (all fields required, JSON-safe):
  `schema_version`, `enabled` (bool), `running` (bool), `effective_action`,
  `network_role`, `roots` (list of `{path, reachable, last_error}`),
  `derived_roots_from_library_profiles` (bool), `debounce_seconds`,
  `pending_work` (bool), `recent_detections` (list of `{path, detected_utc}`, cap 50),
  `last_launch` (`{requested_utc, outcome, message}` or null),
  `last_refusal` (`{utc, reason}` or null), `last_cycle_completed_utc`, `last_error`.
- Governance (tests enforce these): add the route to
  `docs/inventories/API_ROUTE_INVENTORY.md` and
  `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md` classified read/non-mutating.

UI: read-only card on the Schedule page.
- `apps/desktop/webview/static/assets/scheduleView.js` renders the payload (enabled/roots/
  pending count/last launch/degraded reasons). Follow the page's existing card markup and
  refresh wiring; add the fetch to the page's existing refresh path via
  `apps/desktop/webview/static/assets/apiClient.js` conventions. Check
  `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md` / `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` —
  there are static-JS inventory tests that fail on undeclared DOM ids/global exports; update
  the inventories for any new ids/exports.

## 8. Phased execution (each phase ends green before the next starts)

Phase 0 — scope + ledger (no code):
- Operator pastes/approves the docs/SESSION.md block (§14). Create the change packet under
  `ops/release/changes/unreleased/` (next free `MP-CHANGE-<date>-NNN`; many IDs are taken —
  glob first). Keep `files_touched` current as you work
  (`mediapipeline.tools.change_control.record_change_touch`). New branch off the operator's
  chosen base; do not commit without instruction.

Phase 1 — config keys (§5 in full). Exit: registry + contract-schema checks green, Python
config tests green, settings page renders the new fields (smoke or unit assertion), all
defaults off/empty.

Phase 2 — `scanner.py` + its unit tests (§10 group A). Pure logic only; no manager, no
facade edits. Exit: scanner tests green under bundled Python.

Phase 3 — `manager.py` + facade/lifecycle wiring (§6) + startup step. Exit: group B + C
tests green; backend starts with the feature disabled showing `watch_folders: disabled`;
`LocalApiServer.stop()` joins the thread cleanly (test).

Phase 4 — action dispatch (§4.2 step 7) with a fake `start_pipeline` in tests; the real
binding in the facade. Exit: group D tests green, including the
refusal-retry and race tests.

Phase 5 — API route + contract + inventories + Schedule page card (§7). Exit: route tests
+ route-inventory test + webview static tests green.

Phase 6 — full validation sweep + handoff:
- Full desktop suite: `.\apps\desktop\runtime\Python\python.exe -m pytest tests\python\desktop -q`
- `pwsh -File ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1`
- `pwsh -File ops\pipeline\tests\Unit\Invoke-ContractSchemaChecks.ps1`
- End-to-end engine smoke unchanged: `pwsh -File ops\pipeline\tests\Invoke-EndToEndSmokeChecks.ps1`
- Affected smokes: `ops\scripts\smoke\Test-LocalApiLifecycleContractSmoke.ps1` and the
  WebView smokes covering Schedule/Settings surfaces (see
  `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md` for exact names).
- Summaries: `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths <every added/changed source file>`
- Guardrail pair: `python -m mediapipeline.tools.dev.ai_guardrail` preflight/postflight (via
  run-python-tool).
- Change packet: `mediapipeline.tools.change_control.validate_changes --require-worktree-coverage`.
- `CHANGELOG.md` entry. Handoff appended to docs/SESSION.md per CLAUDE.md §8.

## 9. Hard prohibitions (any one of these is a do-over)

1. No new dependency (no watchdog, no pip install, no vendored package, no .NET interop).
2. Never spawn or signal MediaPipeline.ps1 / pwsh directly; never construct launch
   arguments; never write control flags, active-job records, or runtime artifacts.
3. Never bypass or weaken `start_pipeline_process` gating; never edit
   `worker_mutex.ps1`, `schedule_policy.py` gate logic, `guard_policy.py`,
   `pipeline_policy.py` semantics, or the schedule-stop watcher.
4. The watcher performs **zero writes inside watched roots** and zero writes to media
   anywhere. It reads directory entries and stat data only. It must function correctly on
   read-only shares.
5. `EnableWatchFolders` defaults to false in every artifact listed in §5. The feature being
   accidentally on after a fresh install/upgrade is a critical bug.
6. The watcher must never block or delay backend shutdown (daemon thread, event-driven
   stop, bounded join) and must never appear as unsafe work in close-readiness.
7. No edits outside the files named in this plan + the SESSION.md scope block without
   operator approval. Especially: no edits under `ops/pipeline/engine/` beyond the three
   config registry files, no Tauri/Rust edits, no opportunistic refactors.
8. Real media: never point tests or local experiments at `\\LAYNE-SERVER\...` or any real
   library root. Tests use temp dirs and fixture-sized fake files only.
9. Per AGENTS.md §7 this work touches settings schema and schedule-start adjacency: do not
   self-declare completion; the operator validation list in §12 is mandatory.

## 10. Test plan (bundled interpreter only: `apps\desktop\runtime\Python\python.exe`)

New files in `tests/python/desktop/` (match the existing naming/style there):
`test_watch_folder_scanner.py`, `test_watch_folder_manager.py`,
`test_watch_folder_routes.py`.

Group A — scanner (pure, temp dirs, fake clock):
1. Recursive discovery; extension filter is case-insensitive and dot-normalized.
2. A growing file (size changes between observations) never becomes stable.
3. Stability requires an unchanged (size, mtime) span >= debounce; fires exactly once.
4. FiredRegistry: same (path,size,mtime) never refires; new mtime refires; bound/TTL
   eviction works.
5. Unreadable root → degraded result, no exception; other roots unaffected.
6. Baseline semantics: files present at first scan never fire; a file added after baseline
   fires.

Group B — manager cycle (fakes, `run_single_cycle`, no threads, no sleeps):
1. Disabled → no scan callable invoked, state reason recorded.
2. `NetworkRole=worker` → disabled with reason; `coordinator` → effective action forced
   `enqueue_only`; `standalone` → configured action.
3. Settings toggle mid-test (flip the fake `load_settings` return) takes effect next cycle
   without restart.
4. Empty `WatchFolderRoots` → `default_watch_roots()` used and reflected in state.
5. Scan exception → `last_error` recorded, next cycle runs normally.

Group C — lifecycle:
1. `start()` idempotent; `stop()` idempotent, joins within timeout, callable before start.
2. `LocalApiServer.stop()` invokes the facade stop hook (mirror however the schedule-stop
   watcher's server-stop behavior is tested — find that test first; if none exists, add the
   assertion via a fake facade).
3. Close-readiness payload identical/safe with the manager running (compare against a
   baseline payload).
4. Startup step `watch_folders` emitted with correct outcome for enabled/disabled.

Group D — action dispatch (fake `start_pipeline` recording calls):
1. `enqueue_only`: stable file → pending_work true, recent_detections grows, zero
   `start_pipeline` calls.
2. `enqueue_and_launch`: stable file → exactly ONE `start_pipeline` call; request has
   `mode="once"`, no `schedule_override` when `WatchRespectScheduleWindow=True`,
   `schedule_override="ignore"` when False.
3. Refusal then success: first call returns a refusal CommandResult → pending stays, second
   cycle calls again, success clears pending; total calls == 2; no duplicate launch after
   success even though the fired files are unchanged.
4. Batch collapse: three files stabilize in one cycle → still exactly one launch attempt.
5. Race simulation: fake `start_pipeline` that refuses with the active-work message (copy
   the real message shape from `pipeline_start_active_work_result` in
   `pipeline_policy.py`) → watcher records the refusal verbatim and does not error.

Group E — route/UI:
1. Route registered, payload contains every §7 field, schema_version correct.
2. Route-inventory governance test passes (it will fail by itself if the docs weren't
   updated — treat that as the assertion).
3. WebView static tests for the Schedule page additions (DOM id / global export
   inventories).

Optional integration (agent-side, only if cheap): manager with real thread, poll interval
overridden to 0.05 s, temp root, fake facade → exactly one launch for one dropped file;
clean stop. Mark with a generous timeout; no flaky timing assertions (assert on events, not
elapsed wall-clock).

## 11. Validation ladder mapping (AGENTS.md §5)

Rung: "Settings, queue, rename, pending publish, diagnostics → targeted unit tests plus
affected smokes" for the config/route/UI surface, plus the local-API rung
(`Test-LocalApi*`) because routes/lifecycle changed. No FFmpeg/subtitle/audio/publish rung
is triggered — the feature must not touch those paths (if you find yourself needing to, stop
and report). The end-to-end engine smoke must remain green untouched, proving the engine is
unaffected.

## 12. Operator validation (mandatory before "done"; agent must not self-certify)

1. Start the backend (`.\ops\scripts\dev\start-local-api.bat`) with the feature disabled →
   startup step shows `watch_folders: disabled`; Schedule page card shows disabled.
2. Enable `EnableWatchFolders` with `WatchFolderRoots = @("C:\Temp\watch-test")` (a TEST
   folder, never a real library root), `WatchAction = enqueue_and_launch`,
   `WatchRespectScheduleWindow = $false`. Drop ONE small fixture media file in. Expect:
   detection within ~poll+debounce, exactly one pipeline `once` launch, no second launch,
   file processed normally end to end.
3. While a continuous run is active, drop another fixture → watcher records refusal
   (active work), no second process appears; after the run completes the watcher launches
   once.
4. Close the app during an idle watch → clean shutdown, no lingering
   `MediaPipelineWatchFolders` thread/process, close-readiness unaffected.
5. Smokes from §8 Phase 6 + guardrail preflight/postflight pair.

## 13. Known follow-ups (explicitly out of scope for v1)

- Per-LibraryProfile extension/debounce overrides for the watcher.
- A "watch SMB roots" hardening pass (long-poll cadence per root type, jittered scans).
- Mutation route to pause/resume the watcher from the UI.
- Coordinator-role auto-dispatch semantics (today: forced enqueue_only).

## 14. Ready-to-paste docs/SESSION.md scope block

```markdown
## Watch-folder auto-start 2026-MM-DD (operator-approved in chat; plan: docs/implementation/watch-folder-autostart/PLAN.md)

Implements watch-folder detection + optional gated auto-launch per the plan. AGENTS.md §7
contact: settings schema (5 new keys) and schedule-start adjacency — NOT self-certified;
operator validation list in plan §12 required.

In-scope files:
- NEW src/mediapipeline/desktop/watch/{__init__,scanner,manager}.py
- EDIT src/mediapipeline/desktop/application/facade.py (manager init + start/stop/state hooks)
- EDIT src/mediapipeline/desktop/api/server.py (stop hook)
- EDIT src/mediapipeline/desktop/local_api_main.py (startup step + manager start)
- EDIT src/mediapipeline/desktop/api/{routes_read,read_payloads_status,contract_read}.py (status route)
- Config-key registration set from plan §5 (contracts/config.py + generated config.v1.schema.json,
  core/kernel/config_key_{s,_order,_groups}.py, core/config/metadata_parts/watch_fields.py + aggregator,
  ops/pipeline/engine/config/{config_keys,default_values,schema_keys}.ps1,
  ops/pipeline/config/schemas/media_pipeline_config.schema.json,
  ops/pipeline/config/MediaPipeline_config_template.psd1, ops/pipeline/config/profiles/Default.psd1,
  apps/desktop/webview/static/assets/settingsMetadata.js + settings builder,
  docs/architecture/CONFIG_KEY_GLOSSARY.md, docs/inventories/SETTINGS_* and API route inventories)
- EDIT apps/desktop/webview/static/assets/scheduleView.js (+ apiClient wiring, DOM/export inventories)
- NEW tests/python/desktop/test_watch_folder_{scanner,manager,routes}.py
- docs/generated/summaries/ mirrors; CHANGELOG.md; change packet under ops/release/changes/unreleased/

Out of scope: everything in plan §9; all other AGENTS.md §7 areas; engine behavior.
Validation rung: plan §11. Exit criteria: plan phases 0-6 green + handoff written.
```

## 15. Final report Codex must produce

Files changed with one-line summaries; every validation command with its exact result;
change-packet ID + strict coverage result; explicit list of which §12 operator items remain;
any drift found between this plan's citations and the live tree (report, don't silently
adapt, if the drift is structural).
