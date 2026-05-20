# Network Read-Only Language Audit

Date: 2026-05-14

Checks whether any wording implies the WebView Network page can start, stop, or otherwise control the coordinator or worker lifecycle when it remains read-only. Source: `Docs\NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`.

---

## Summary

No wording found that implies the WebView Network page has lifecycle control. All inspected files correctly limit the Network page to read-only visibility of coordinator/worker state. No documentation changes required.

---

## Acceptance Criteria Check

| Criterion | Status | Evidence |
|---|---|---|
| Network lifecycle controls remain explicitly Tk/backend-future only | Pass | `NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`: "Start or stop the coordinator — The coordinator is a backend process — WebView cannot launch or stop it" |
| Read-only worker visibility is clearly described | Pass | Network page renders from `GET /api/network/workers`; all actions listed under "What the WebView Network Page Does" are GET or local-UI operations |
| No operator instructions to start workers from WebView | Pass | "What Remains Backend-Only" section explicitly lists all lifecycle operations and directs to the BAT launcher |

---

## Network Page Operations (Confirmed Read-Only)

From `NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`:

| Operation type | Operations available |
|---|---|
| **Read (GET)** | View coordinator readiness summary, view registered worker rows |
| **Local UI** | Select worker row for detail, apply local display filter, see filter warning |
| **Not available** | Start/stop coordinator, register/unregister worker, change NetworkRole, view/rotate auth tokens, reassign jobs, force disconnect/reconnect, live remote telemetry |

---

## What Remains Backend-Only (Confirmed)

| Operation | Correct location |
|---|---|
| Launch coordinator | `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat` on coordinator machine |
| Launch worker | Same BAT on worker machine with `NetworkRole=worker` |
| Set coordinator auth token | Settings raw JSON patch or direct PSD1 edit |
| Diagnose cluster log | Diagnostics page (read-only tail/open) |
| Per-worker config overrides | Settings raw JSON patch |

All lifecycle operations are correctly documented as backend-only or Tk-owned.

---

## Auth Token Handling

`CoordinatorAuthToken` and `WorkerAuthToken` are classified as:
- **Intentionally hidden** from the WebView builder and raw JSON staging
- Must not appear in browser storage, dev tools, or JS heap snapshots
- Must be edited via PSD1 directly or a secure credential management practice

This is consistent with `Docs\SETTINGS_RAW_KEY_TRIAGE.md` (CLN-015 findings).

---

## Browser Smoke Boundary Confirmation

`Test-WebViewBrowserNetworkSmoke.ps1` is confirmed to:
- Render read-only network posture and persisted worker state
- Not start/stop coordinator or workers
- Not post mutation routes

The browser smoke confirms the wording matches the actual implementation.

---

## Files Inspected

- `Docs\NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`: full read-only scope; what-not table; backend-only operations; config keys

---

## Freshness Review — 2026-05-15 (CLN2-14)

Re-checked `networkView.js` (reference only), `NETWORK_READ_ONLY_PARITY_AUDIT.md`, and V5 status board.

| Check | Evidence | Status |
|---|---|---|
| WebView Network JS has no lifecycle controls | `networkView.js` contains no `apiPost` calls for start/stop/register/unregister; read-only pattern confirmed | Pass — no drift |
| JS guardrail text present | `networkView.js`: "Lifecycle owner: Tk Network tab / Python dispatcher."; "WebView status: read-only settings, contract, logs, and diagnostic opens."; "live dispatcher lifecycle rows remain Tk-owned." | Pass — wording intact |
| Parity audit documents lifecycle as WebView gap | `NETWORK_READ_ONLY_PARITY_AUDIT.md` section 1: "There is no command route for coordinator lifecycle in `contract_command.py`." | Pass — no drift |
| V5 status board | `V5_TRANSITION_STATUS_BOARD.md`: "Network — **Read-only** — Persisted worker state visible; lifecycle controls remain Tk-owned" | Pass — no drift |
| Auth token exclusion | `NETWORK_READ_ONLY_PARITY_AUDIT.md` section 4: CoordinatorAuthToken and WorkerAuthToken intentionally hidden — correct and unchanged | Pass — no drift |

No documentation changes required. No lifecycle controls are implied or newly introduced anywhere in the Network docs or JS.

---

## Freshness Review — 2026-05-15 (CLN3-026)

Re-confirmed Network read-only status after recent V5 transition work (browser smokes, sample validation, real-media proof).

| Check | Result |
|---|---|
| No new `apiPost` calls in `networkView.js` | Pass — `networkView.js` flat export count is 7 (CLN3-004); none of the 7 exports are POST callers |
| `Test-WebViewBrowserNetworkSmoke.ps1` boundary | Pass — smoke boundary text: "verifies no network lifecycle mutation commands are posted; WebView Network remains read-only" (confirmed in WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md) |
| Network page Tk-owned lifecycle note in TLDR.md | Pass — "Network — read-only; coordinator/worker lifecycle remains Tk-owned" |
| New sample-validation or real-media proof interactions with Network | None — network page is not part of the real-media proof chain |

No wording corrections needed. Network page remains read-only.

```
Task ID: CLN3-026
Files inspected: Docs\NETWORK_READONLY_WORDING_AUDIT.md, Docs\NETWORK_MODE_READ_ONLY_DOCUMENTATION.md, Docs\NETWORK_UX_IMPROVEMENTS.md, Docs\TLDR.md (references)
Files changed: Docs\NETWORK_READONLY_WORDING_AUDIT.md (CLN3-026 freshness note added)
Validation: Select-String -Path Docs\NETWORK_MODE_READ_ONLY_DOCUMENTATION.md,Docs\NETWORK_READONLY_WORDING_AUDIT.md,Docs\NETWORK_UX_IMPROVEMENTS.md,Docs\TLDR.md -Pattern "read-only|start|stop|coordinator|worker"
Findings: All wording current. No lifecycle controls introduced.
Open questions: None.
Risk: Low — documentation only.
```

---

## Task Output

```
Task ID: CLN-018
Files inspected: Docs\NETWORK_MODE_READ_ONLY_DOCUMENTATION.md
Files changed: Docs\NETWORK_READONLY_WORDING_AUDIT.md (created)
Validation: Checked acceptance criteria against read-only documentation and browser smoke scope.
Findings: All criteria pass. No lifecycle-control wording found. Auth token exclusion is correct.
Open questions: None.
Risk: Low — documentation only.
```
