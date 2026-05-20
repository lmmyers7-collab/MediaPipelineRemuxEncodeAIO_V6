# Network Read-Only Parity Audit

Purpose: document what the WebView Network page covers, what it does not cover compared to the CustomTkinter app, and what gaps matter most for operators running in coordinator or worker mode.

This is an audit document. It does not implement lifecycle controls, live-board APIs, or token management. Standalone mode is the supported default; coordinator/worker is experimental.

---

## What The WebView Network Page Covers (Read-Only)

All WebView network coverage is read-only. No lifecycle controls, no coordinator start/stop, no force-reclaim, no auth token access.

### Role And Settings Display

| Coverage | Source |
|---|---|
| Active network role (`standalone` / `coordinator` / `worker`) | `GET /api/network/workers` → `NetworkWorkersDto.role` |
| Coordinator target display (`<bind_address>:<port>` or worker's coordinator URL) | Derived from config keys in settings workspace |
| Worker poll interval | From config |
| Settings table for all non-auth network keys | Settings builder / `GET /api/settings/workspace` |

Settings keys visible in the Network page and Settings builder:

| Key | Shown in Network | Shown in Settings builder |
|---|---|---|
| `NetworkRole` | Yes | Yes |
| `CoordinatorPort` | Yes | Yes |
| `CoordinatorBindAddress` | Yes | Yes |
| `CoordinatorAlsoEncodeLocally` | Yes | Yes |
| `CoordinatorHeartbeatTimeoutMins` | Yes | Yes |
| `WorkerCoordinatorUrl` | Yes | Yes |
| `WorkerName` | Yes | Yes |
| `WorkerPollIntervalSecs` | Yes | Yes |
| `WorkerSourcePathMap` | Yes (display only) | Yes (raw JSON string) |
| `WorkerConfigOverrides` | Yes (display only) | Yes (raw JSON string) |
| `CoordinatorAuthToken` | **No** (hidden) | **No** (intentionally excluded) |
| `WorkerAuthToken` | **No** (hidden) | **No** (intentionally excluded) |

`WorkerSourcePathMap` and `WorkerConfigOverrides` are JSON string fields. The WebView displays them as-is from config without a structured editor. Operators must use raw JSON patch or direct config file edit for these.

### Worker Board (Persisted State)

The worker board reads from the backend's persisted coordinator/worker state files (`coordinator_inflight.json`, `worker_state.json`) via `GET /api/network/workers`. It does not query the coordinator's live HTTP API.

Per-worker fields visible in the board:

| Field | Notes |
|---|---|
| Worker name / ID | From persisted registry |
| Status (active / idle / problem / unknown) | Derived from registry state |
| Current file | From in-flight record |
| Progress % | From in-flight record |
| Heartbeat age | Derived from last heartbeat timestamp |
| Files completed (session) | From worker stats |
| GB encoded (session) | From worker stats |
| Average / current encode speed | From worker stats |
| Current stage | From in-flight record |
| Extra persisted fields | Shown in per-worker detail panel |

Filtering: status filter (active / idle / problem / unknown) and text search on name/file.

Warnings returned by `GET /api/network/workers` when the backend detects:
- Stale in-flight records (heartbeat timeout exceeded)
- Worker has a pending done report not yet processed
- Empty worker board while in coordinator role
- Worker state file present with an interrupted job (crash-recovery state)

### Readiness Evidence Checklist

The Network page shows a 7-checkpoint readiness checklist:

1. Role and lifecycle boundary — confirms role is understood and no lifecycle controls exist in WebView
2. API contract — confirms `/api/network/workers` is in the route contract
3. Persisted worker state — whether coordinator in-flight registry has rows
4. Local recovery state — whether a worker state file with an interrupted job exists
5. Diagnostics targets — `cluster_log` and `state` are openable from WebView
6. Mutation guards — confirms all lifecycle controls remain Tk-owned
7. Settings posture — whether required network keys have values

---

## What The WebView Does NOT Cover

### 1. Coordinator Lifecycle (Start/Stop)

**Tk covers**: Starting and stopping the coordinator HTTP server, changing port/bind address and restarting, viewing the live coordinator status indicator in the status bar.

**WebView gap**: The WebView cannot start, stop, or restart the coordinator. These controls remain in the CustomTkinter network panel (`NetworkController.start_coordinator_api()`, `stop_coordinator_api()`). There is no command route for coordinator lifecycle in `contract_command.py`.

**Risk**: Operators who need to toggle coordinator mode must use the Tk app. If WebView is the only shell open, coordinator lifecycle changes require restarting with the Tk app.

### 2. Live Worker Board

**Tk covers**: The coordinator's in-flight job registry is queried in real-time from the running coordinator HTTP server, so the Tk worker board reflects live claim/heartbeat/done activity.

**WebView gap**: `GET /api/network/workers` reads from persisted state files (`coordinator_inflight.json`), not from the live coordinator HTTP API. The board updates on WebView page refresh, not on coordinator events. In fast-moving encode sessions, the WebView may show stale in-flight records.

**Risk**: An operator monitoring encode progress across multiple workers using only the WebView will see refresh-lag in job status. The persisted-state view is accurate for diagnostic review but should not be treated as real-time.

**Note from parity matrix**: Adding a true live worker-board payload requires the coordinator lifecycle to move behind backend commands first. This must not be added until lifecycle ownership is fully backend-owned.

### 3. Coordinator Health Verification

**Tk covers**: The coordinator status indicator shows whether the coordinator HTTP server is actively accepting connections.

**WebView gap**: The WebView can read the role and persisted worker state but cannot verify that the coordinator HTTP server is actually running and accepting claim/heartbeat/done requests. An operator who sees a populated worker board in the WebView cannot confirm from the WebView alone that the coordinator is alive.

**Risk**: A crashed or stopped coordinator will not be immediately visible in the WebView until stale heartbeat warnings appear in the persisted state and are picked up on the next refresh.

### 4. Auth Token Management

**Tk covers**: Auto-generation of `CoordinatorAuthToken` on first coordinator start (if the field is empty). Display of the token value within the Tk app for operator copy/paste to workers.

**WebView gap**: `CoordinatorAuthToken` and `WorkerAuthToken` are intentionally hidden from the WebView. Operators cannot read, rotate, or display tokens through the WebView. Auth token changes require direct config file editing or a raw JSON patch through the backend settings routes, with the token never appearing in the WebView response.

**Risk**: This is by design (see `SETTINGS_BUILDER_COVERAGE_MATRIX.md`). Auth tokens must not appear in browser storage, dev tools, or JS heap snapshots. The gap is intentional and the correct behavior.

### 5. mDNS Coordinator Discovery

**Tk covers**: Optional mDNS advertisement (when `zeroconf` is installed) allows workers to discover the coordinator without a manually configured URL. The coordinator broadcasts its address.

**WebView gap**: mDNS discovery is not surfaced in the WebView. Operators configuring `WorkerCoordinatorUrl` must enter the coordinator address manually.

**Risk**: Low for current usage — mDNS is optional and requires `zeroconf`. Manual URL entry is the primary path.

### 6. Force-Reclaim And Worker Control

**Tk covers**: The coordinator can reclaim a stale job by letting the heartbeat timeout expire and waiting for the reaper thread to act. There is no explicit "force reclaim" UI, but stopping and restarting the coordinator effectively reclaims all in-flight jobs.

**WebView gap**: No mechanism to force-reclaim, eject, or reset a worker from the WebView. All such operations require Tk.

**Risk**: Low in practice — the backend's stale-reaper thread handles reclaim automatically. Only relevant if a specific worker must be evicted during a long job.

### 7. WorkerSourcePathMap And WorkerConfigOverrides Editing

**Tk covers**: These keys are set through the Tk network/settings panel. The Tk app does not provide a structured editor either — both are raw JSON string fields.

**WebView gap**: Displayed as raw JSON strings. No structured builder. Operators editing these must use raw JSON patch or direct config edit.

**Risk**: Moderate — these fields are infrequently changed but silently wrong values can break worker path resolution or apply unintended encode settings per-worker.

---

## Gap Priority Summary

| Gap | Operator Impact | Current Workaround | Notes |
|---|---|---|---|
| Coordinator start/stop | High if coordinator mode is used | Must use Tk app | No command route exists; intentionally deferred |
| Live worker board | Medium — stale refresh lag | Manual page refresh; use `cluster_log` tail for live activity | Requires lifecycle ownership to move first |
| Coordinator health check | Medium — silent crash not visible | Tail `cluster_log` via Diagnostics for HTTP server status | Periodic health poll would require a new read route |
| Auth token management | Intentionally absent | Direct config edit; never via WebView | By design — security constraint |
| mDNS discovery | Low | Manual URL entry | Optional feature; not a daily-driver gap |
| Force-reclaim / worker eject | Low | Heartbeat timeout auto-reclaim | No explicit UI in Tk either |
| WorkerSourcePathMap / WorkerConfigOverrides editing | Low-moderate | Raw JSON patch via Settings | Infrequently changed |

---

## What IS Safe To Do In WebView For Network Monitoring

- Read active role and coordinator target address
- Inspect persisted worker board rows with filtering and per-worker detail
- View readiness evidence checklist
- Open `cluster_log` (via Diagnostics) to tail live coordinator/worker log activity
- Open `state` folder (via Diagnostics) to browse coordinator state files directly
- Review network-related Settings workspace keys (non-auth)
- Use Diagnostics → Recent Events to see network command history

---

## See Also

- Network settings builder: `SETTINGS_BUILDER_COVERAGE_MATRIX.md` (Network group, auth token exclusions)
- Route contract: `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` (`GET /api/network/workers`)
- Diagnostics targets: `DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` (`cluster_log`, `state`, `workspace`)
- Parity matrix: `TAURI_WEBVIEW_PARITY_MATRIX.md` (Network row)
- Network mode checklist: `archive/completed-checklists/NETWORK_MODE_CHECKLIST.md` (implementation archive)
