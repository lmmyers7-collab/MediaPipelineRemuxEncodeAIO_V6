# Network Mode Read-Only Documentation

Date: 2026-06-02

Documents what the WebView Network page can and cannot do, how network mode is configured, what the read-only coordinator/worker state represents, and what operations remain backend-only/manual until lifecycle routes are deliberately promoted.

---

## Network Mode Overview

MediaPipelineRemuxEncodeAIO supports three network roles configured via the `NetworkRole` config key:

| Role | Meaning |
|---|---|
| `standalone` | Default. Single machine processes all files locally. No coordinator or workers. |
| `coordinator` | This machine manages job distribution, maintains the queue, and optionally processes jobs locally. |
| `worker` | This machine polls the coordinator for jobs and processes them. No local queue management. |

Network role is configured through backend Settings (`NetworkRole` key). The WebView Network page can stage and submit non-secret Worker Mode Settings through the backend Settings Preview/Save routes, but applying a changed role to running distributed work still requires the normal backend config-save flow and a pipeline restart.

---

## What the WebView Network Page Does

The Network worker/lifecycle view is read-only. It renders coordinator/worker runtime state from `GET /api/network/workers` and displays design-only lifecycle gates from `/api/contract`. Those gates describe what a future backend-owned lifecycle implementation must prove; they are not command routes and do not authorize WebView lifecycle buttons.

The same tab also contains Worker Mode Settings controls for non-secret network configuration. Those controls only stage local settings JSON and call the existing backend Settings Preview/Save routes. They do not start or stop coordinator/worker runtime, release or reclaim jobs, send done reports, mutate queue state, publish, rename, or touch media files.

### Evidence and Config Operations (available)

| Action | Route | Notes |
|---|---|---|
| View coordinator readiness summary | `GET /api/network/workers` | Shows whether a coordinator is reachable and any configuration issues |
| View registered worker rows | `GET /api/network/workers` | One row per worker registered with the coordinator |
| Review future lifecycle gates | `GET /api/contract` | Design-only contracts for coordinator start, coordinator stop, and worker polling lifecycle; mutation disabled |
| Select a worker row for detail | Local UI | Renders worker name, address, status, last heartbeat, active job if any |
| Apply local worker display filter | Local UI | Filters visible worker rows; does not affect coordinator state or backend |
| See filter warning when active/problem workers are hidden | Local UI | Mutation guardrail: filter-scope warning appears when a problem row is hidden by an active filter |
| Stage non-secret worker mode settings | Local UI | Writes only the shared Settings patch JSON in the browser |
| Preview or save non-secret worker mode settings | Backend Settings routes | Uses the same backend Preview/Save validation and config backup flow as Settings; not a Network lifecycle route |

### Browser Smoke Coverage

`Test-WebViewBrowserNetworkSmoke.ps1` exercises:
- Read-only network posture rendering
- Persisted worker rows display
- Worker detail panel rendering
- Local filter warnings when active/problem rows are hidden

---

## What the WebView Network Page Does Not Do

| Action | Why not |
|---|---|
| Start or stop the coordinator | The coordinator is a backend process — WebView cannot launch or stop it |
| Register or unregister a worker | Worker registration is handled by the worker process itself on startup |
| Apply a changed `NetworkRole` to active runtime | Config save alone does not restart or migrate active coordinator/worker work |
| Bypass backend Settings Preview/Save for `WorkerCoordinatorUrl` or `CoordinatorPort` | Config persistence remains backend-owned |
| View, stage, or rotate `CoordinatorAuthToken` / `WorkerAuthToken` | Auth secret values are intentionally excluded from the WebView builder and Network evidence surface |
| Reassign jobs between workers | Job assignment is coordinator-owned |
| Force a worker to disconnect or reconnect | Backend-only operation |
| Execute lifecycle dry-runs or commands | Not implemented; future routes must satisfy `NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` first |
| See live CPU/GPU metrics per worker | Telemetry is per-machine only; remote worker metrics are not aggregated |

---

## What Remains Backend-Only

| Operation | Where to perform |
|---|---|
| Launch the coordinator | `scripts\dev\start-api-and-browser.bat` or `scripts\dev\start-local-api.bat` on the coordinator machine, with `NetworkRole=coordinator` in config |
| Launch a worker | Same start command on the worker machine, with `NetworkRole=worker` and `WorkerCoordinatorUrl` set |
| Set coordinator/worker auth token | Direct PSD1 edit or a future backend-owned secret workflow |
| Diagnose cluster log | Diagnostics page → `cluster_log` target (tail) or open |
| Inspect active job assignment | Diagnostics → `active_jobs` target |
| Rotate network auth secrets | Direct config edit or a future backend-owned secret workflow that does not expose token values to WebView |

Future WebView lifecycle buttons require `Docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`: backend dry-run routes, duplicate-command guards, close-readiness integration, process cleanup/rollback, command journaling, state preservation, browser no-mutation coverage, and inventory/doc-touch updates.

---

## Config Keys for Network Mode

| Key | Builder page | Risk | Notes |
|---|---|---|---|
| `NetworkRole` | Network | **High** | `standalone`/`coordinator`/`worker`; changing requires restart |
| `CoordinatorPort` | Network | Medium | HTTP listen port (default 7830); must be open in firewall |
| `CoordinatorBindAddress` | Network | Medium | `0.0.0.0` or `127.0.0.1`; `0.0.0.0` exposes coordinator to LAN |
| `CoordinatorAlsoEncodeLocally` | Network | Medium | Whether coordinator also processes jobs |
| `CoordinatorHeartbeatTimeoutMins` | Network | Medium | Stale worker job timeout (default 5 min) |
| `CoordinatorAuthToken` | Not surfaced | **High** | Auth secret; intentionally excluded from WebView builder and Network evidence |
| `WorkerCoordinatorUrl` | Network | Medium | `http://host:port`; must match coordinator address |
| `WorkerName` | Network | Low | Worker display name |
| `WorkerAuthToken` | Not surfaced | **High** | Must match coordinator token; excluded from WebView builder and Network evidence |
| `WorkerPollIntervalSecs` | Network | Low | How often the worker checks for new jobs (default 10s) |
| `WorkerSourcePathMap` | Network | Medium | JSON object remapping source paths for workers on different drive letters/mounts |
| `WorkerConfigOverrides` | Network | Medium | Per-worker JSON config overrides applied by coordinator |

Auth token values must be set by direct PSD1 edit or a future backend-owned secret workflow. The Network page must not render token values, token setting rows, or token staging controls.

---

## Worker State Fields

Each worker row in `GET /api/network/workers` includes:

| Field | Meaning |
|---|---|
| `worker_name` | Display name configured in `WorkerName` |
| `worker_address` | Worker host/port as seen by the coordinator |
| `status` | `active`, `idle`, `problem`, `offline`, or `unknown` |
| `last_heartbeat` | ISO timestamp of most recent heartbeat |
| `active_job` | Current job assignment (source path / job_id), if any |
| `registered_at` | ISO timestamp of initial registration |
| `version` | Worker's product version |

Worker status meanings:

| Status | Meaning |
|---|---|
| `active` | Worker is processing a job |
| `idle` | Worker is reachable and waiting for jobs |
| `problem` | Worker reported an error or is failing health checks |
| `offline` | No heartbeat received within the coordinator timeout |
| `unknown` | Coordinator has not yet received a heartbeat |

---

## Read-Only Guarantee

`GET /api/network/workers` has effect `none`. Selecting a worker row, applying a local filter, or clicking a worker/lifecycle detail control makes no backend call.

The Network page's Worker Mode Settings buttons are the exception to the page's otherwise read-only behavior: they call backend Settings Preview/Save routes for non-secret config changes only. They are not `/api/network/*` mutation routes and do not own coordinator/worker lifecycle.

The only mutations that can affect network state are:
1. Changing non-secret network-related config keys via backend Settings save-patch.
2. Editing network auth secrets outside the WebView.
3. Launching the pipeline process on a coordinator or worker machine.

The Network worker/lifecycle evidence panels do not perform any of those mutations.

---

## Diagnostics Targets for Network Issues

| Symptom | Recommended targets |
|---|---|
| Worker shows `offline` | `cluster_log` tail → look for heartbeat timeout messages |
| Worker shows `problem` | `cluster_log` tail + `active_jobs` open on the worker machine |
| Job assigned but not completing | `last_stderr_log` on the worker machine + `active_jobs` on coordinator |
| Coordinator not reachable | Check `NetworkRole`, `CoordinatorPort`, `CoordinatorBindAddress` in Settings; check firewall |

---

## See Also

- Settings key ownership map: `Docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`
- Network UX improvements doc: `Docs/ui/NETWORK_UX_IMPROVEMENTS.md`
- Browser network smoke: `Test-WebViewBrowserNetworkSmoke.ps1`
- API route inventory: `Docs/inventories/API_ROUTE_INVENTORY.md`
