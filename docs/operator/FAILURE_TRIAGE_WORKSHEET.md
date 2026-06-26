# Failure Triage Worksheet

Copy this worksheet when diagnosing a failed, suspicious, or unexpected pipeline run. Fill in each section from current evidence before taking any corrective action.

**Do not delete source files, scratch files, output files, or clear state until you have completed the Evidence sections below.** Deleting state removes the evidence you need to understand what happened.

---

## Triage Run Identity

| Field | Value |
|---|---|
| Date / Time | |
| Operator | |
| Machine | |
| App version (UI / API snapshot) | |

---

## What Happened

Describe the problem in plain language:

```
(e.g., "Pipeline stopped mid-encode and left a partial file in scratch",
"A file that should be remuxed was encoded instead",
"Drain failed with a missing payload error",
"The app closed unexpectedly during active work")
```

---

## Current App State

| Field | Value | Where to find |
|---|---|---|
| Desktop app open? | Yes / No | — |
| Tauri/WebView open? | Yes / No | — |
| Pipeline running? | Yes / No | WebView Home / ActiveJobs |
| Close readiness | Safe / Unsafe / Unknown | `GET /api/backend/close-readiness` or WebView Home |
| Recent command history entries | | WebView Command History or `GET /api/commands` |
| ActiveJobs records present? | Yes / No | `State\ActiveJobs\` or WebView Diagnostics |
| ActiveJobs PID still running? | Yes / No | Task Manager or `Get-Process` |

---

## Source / Output / Scratch Paths

| Field | Value |
|---|---|
| Source file(s) in question | |
| Expected output path | |
| Scratch / temp path (if known) | |
| Files present in scratch right now | Yes / No / Unknown |
| Output file present (full or partial)? | Yes / No / Partial |

---

## Queue Evidence

Capture this before refreshing or launching anything.

| Field | Value | Source |
|---|---|---|
| File in current queue? | Yes / No / Excluded | WebView Queue or `GET /api/queue` |
| Route shown | Remux / Encode / Unknown | Queue row |
| Route reason | | Queue row detail |
| Blocked? | Yes / No | Queue row |
| Excluded? | Yes / No | Queue row detail |
| Snapshot age | | Queue page or `State\Progress\queue_plan_snapshot.json` modified time |
| Runtime outcome history for this source | | Queue selected-row detail |

---

## Completed Manifest Evidence

| Field | Value | Source |
|---|---|---|
| File in completed manifest? | Yes / No | WebView Completed or `GET /api/completed` |
| Output path in manifest exists on disk? | Yes / No | Completed row detail |
| Sidecar present? | Yes / No | Completed row detail |
| Route reason in manifest | | Completed row detail |
| Completed manifest file age | | `State\Completed\completed_jobs.jsonl` modified time |
| Size in manifest vs actual file size | | Completed row / disk |

---

## Pending Publish Evidence

Fill in only if DeferredPublish is enabled or if a drain event is suspected.

| Field | Value | Source |
|---|---|---|
| File in pending publish? | Yes / No | WebView Pending Publish or `GET /api/pending-publish` |
| Row state | Ready / Do Not Drain / Missing Payload / Orphan / Invalid Manifest | Pending Publish row |
| Recovery dry-run run? | Yes / No | WebView Pending Publish → Recovery Plan |
| Recovery dry-run result | | Recovery plan output |
| Last drain summary | | `State\PendingServerPush\pending_drain_summary.json` |
| Drain command in command history? | Yes / No | WebView Command History |
| Drain result | | Command history |

---

## Diagnostics Tail / Logs Evidence

Use backend-allowlisted diagnostics targets only. Do not open arbitrary paths directly.

| Target | Key findings | Opened via |
|---|---|---|
| `last_stderr_log` | | `POST /api/diagnostics/open` or WebView Diagnostics Tail |
| `last_stdout_log` | | Same |
| `run_logs` | | Same |
| `active_jobs` | | Same |
| `queue_snapshot` | | Same |
| `latest_failure_json` | | Same |
| `latest_failure_report` | | Same |
| `state` | | Same |

FFmpeg error lines from last_stderr_log:

```
(paste relevant lines here)
```

---

## Command History Evidence

Recent commands visible in `GET /api/commands` or WebView Command History:

| Time | Command | Status | Issue level | Notes |
|---|---|---|---|---|
| | | | | |
| | | | | |

---

## Failure Marker Evidence

| Field | Value | Source |
|---|---|---|
| Failure marker present for this source? | Yes / No | `State\Failures\Markers\` or WebView Queue exclusion |
| Failure report present? | Yes / No | `State\Failures\Reports\` or WebView Diagnostics |
| Latest failure JSON summary | | `latest_failure_json` or Diagnostics tail |

---

## Safe Next Actions (Choose One)

Select the appropriate next action based on evidence above. Do not skip to action before filling in evidence sections.

| Scenario | Next action |
|---|---|
| Source is in queue but excluded (failure marker present) | Review failure report; when understood, use Reports > Clear Retry Blockers to preview and confirm marker cleanup |
| Output is partial in scratch | Do not delete manually; restart pipeline to resume (it will overwrite scratch) |
| Output is in completed manifest but wrong route | Document the route evidence; decide whether to rerun via CSV rerun |
| Pending Publish row is Do Not Drain | Use recovery dry-run to understand blockers; do not drain until resolved |
| ActiveJobs record present but process not running | Clean via app Kill + Quit; do not delete ActiveJobs manually |
| Suspected partial config save | Restore from backup (`MediaPipeline_config_chatgpt.backup_*.psd1`) and reload |
| Unknown state | Do not change anything; open `State\` and `Diagnostics` targets for more evidence |

---

## Actions Not Taken Yet

List actions you have confirmed are NOT safe to take yet:

| Action | Why deferred |
|---|---|
| | |
| | |

---

## Resolution

| Field | Value |
|---|---|
| Root cause identified | Yes / No / Partial |
| Root cause | |
| Resolution action taken | |
| Evidence captured before action | Yes / No |
| State returned to known-good | Yes / No |
| Follow-up needed | |

---

## See Also

- Runtime artifact inventory: `docs/inventories/RUNTIME_ARTIFACT_INVENTORY.md`
- Diagnostics target runbook: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- Real-media validation evidence template: `docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`
- Failure marker clear behavior: `docs/CURRENT_PROJECT_STATE.md`
- No-touch boundaries: `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
