# Network Mode Lifecycle Documentation

Date: 2026-06-13

Documents what the WebView Network page can and cannot do, how network mode is configured, what coordinator/worker state represents, and which lifecycle operations are now backend-owned Local API commands.

The filename is retained for compatibility with older links. The page is no longer a read-only-only contract.

---

## Network Mode Overview

The persisted config key remains `NetworkRole=standalone|coordinator|worker`.

The UI shows four visible modes:

| UI mode | Persisted config |
|---|---|
| Standalone | `NetworkRole=standalone` |
| Coordinator only | `NetworkRole=coordinator`, `CoordinatorAlsoEncodeLocally=false` |
| Worker only | `NetworkRole=worker` |
| Coordinator + local worker | `NetworkRole=coordinator`, `CoordinatorAlsoEncodeLocally=true` |

Normal Launch is blocked when `NetworkRole` is `coordinator` or `worker`. Distributed work starts from the Network page lifecycle controls.

---

## What The WebView Network Page Does

The Network page renders persisted worker/coordinator state from `GET /api/network/workers`, shows role-aware settings, and exposes backend-owned lifecycle controls for coordinator/worker start and stop.

Lifecycle controls call only these Local API routes:

| Action | Route | Effect |
|---|---|---|
| Coordinator start dry-run | `POST /api/network/coordinator/start-dry-run` | `none` |
| Coordinator stop dry-run | `POST /api/network/coordinator/stop-dry-run` | `none` |
| Worker start dry-run | `POST /api/network/worker/start-dry-run` | `none` |
| Worker stop dry-run | `POST /api/network/worker/stop-dry-run` | `none` |
| Start coordinator | `POST /api/network/coordinator/start` | `backend-lifecycle` |
| Stop coordinator | `POST /api/network/coordinator/stop` | `backend-lifecycle` |
| Start worker | `POST /api/network/worker/start` | `backend-lifecycle` |
| Stop worker | `POST /api/network/worker/stop` | `backend-lifecycle` |

Dry-runs return preconditions, active work, pending done reports, state-file posture, redacted config evidence, and `would_not_touch` evidence. Confirmed routes require `confirm_start` or `confirm_stop` and remain provider-guarded until the real coordinator/worker lifecycle provider is available.

The same tab also contains non-secret Network settings controls. Those controls stage local settings JSON and call the existing backend Settings Preview/Save routes. They do not start or stop runtime loops.

---

## What The WebView Network Page Does Not Do

| Action | Boundary |
|---|---|
| Normal pipeline launch in network mode | Blocked by backend `/api/pipeline/start` and launch preflight |
| Scan the queue from a worker | Forbidden; workers accept coordinator claims only |
| Construct source/output/scratch filesystem paths | Backend owns path maps, validation, and source/scratch/output policy |
| Reassign, reclaim, release, abort, quarantine, drain, publish, or rename | Disabled until separate backend routes and tests exist |
| View, stage, or rotate `CoordinatorAuthToken` / `WorkerAuthToken` | Auth secrets remain hidden and backend-owned |
| Delete or rename source files | Forbidden by project source mutation policy |

---

## Current Provider Guard

The Local API lifecycle routes exist now. Confirmed routes are not fake launchers. If the real lifecycle provider hook is unavailable, they return a blocked command result and do not fall through to normal Launch, local queue scanning, media processing, claim release, or file mutation.

This is intentional fail-closed behavior while the dispatcher provider integration is completed.

---

## Config Keys For Network Mode

| Key | Builder visibility | Notes |
|---|---|---|
| `NetworkRole` | All modes | Persisted compatibility role |
| `CoordinatorPort` | Coordinator modes | HTTP listen port, default 7830 |
| `CoordinatorBindAddress` | Coordinator modes | `0.0.0.0` for LAN workers or `127.0.0.1` for local-only tests |
| `CoordinatorAlsoEncodeLocally` | Backing value for Coordinator + local worker | Hidden as a raw checkbox when the fourth UI mode is selected |
| `CoordinatorHeartbeatTimeoutMins` | Coordinator modes | Stale heartbeat timeout |
| `WorkerCoordinatorUrl` | Worker mode | Coordinator endpoint |
| `WorkerName` | Worker mode | Worker display name |
| `WorkerPollIntervalSecs` | Worker mode | Worker claim poll interval |
| `WorkerSourcePathMap` | Worker mode | JSON path-map from coordinator source paths to worker-visible paths |
| `WorkerConfigOverrides` | Deprecated/hidden for quality policy | Must not override quality-affecting CRF/bitrate/audio/subtitle/output naming policy |
| `CoordinatorAuthToken`, `WorkerAuthToken` | Not surfaced | Secret values intentionally excluded from WebView |

---

## Browser Smoke Coverage

`Test-WebViewBrowserNetworkSmoke.ps1` exercises:

- Network lifecycle control visibility from the backend route contract.
- Runtime readiness and lifecycle handoff rendering.
- State-file evidence and persisted worker rows.
- Worker detail panel rendering.
- Local filter warnings when active/problem rows are hidden.
- No confirmed coordinator/worker start or stop is executed during the smoke.

---

## See Also

- Network lifecycle command contract: `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- API route inventory: `docs/inventories/API_ROUTE_INVENTORY.md`
- Command ownership matrix: `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- Settings key ownership map: `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`
