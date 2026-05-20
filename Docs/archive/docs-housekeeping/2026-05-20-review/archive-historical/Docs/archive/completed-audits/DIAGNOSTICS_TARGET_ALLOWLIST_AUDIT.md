# Diagnostics Target Allowlist Audit

Date: 2026-05-14

Inventories every backend-allowlisted target key for `/api/diagnostics/open` and `/api/diagnostics/tail`. States the resolved artifact, whether open and/or tail are available, which WebView pages surface the target, and the read-only safety guarantee. Source: `Docs/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` and `contract_command.py`.

---

## Safety Contract

The WebView cannot pass arbitrary filesystem paths to any diagnostics route. Every request is validated against the allowlist before the backend resolves or reads any path. The frontend passes only a target key string.

- **`/api/diagnostics/open`** — opens the resolved path in Windows Explorer. Appends a command-journal result. Does not move, edit, delete, or write any file.
- **`/api/diagnostics/tail`** — returns a bounded text excerpt (1 KB–256 KB, default 64 KB). Does not write, append, or truncate the file.

Neither route processes media, launches pipeline work, changes settings, publishes parked outputs, renames files, or mutates queue state.

---

## File Targets — Open and Tail Available (11 targets)

These targets resolve to physical files. Both `/api/diagnostics/open` (Explorer) and `/api/diagnostics/tail` (bounded read) are available.

| Target key | Resolves to | Primary diagnostic use | WebView pages that surface it |
|---|---|---|---|
| `last_stderr_log` | Latest pipeline/audit run stderr log | First stop for FFmpeg errors, encoder failures, subtitle/audio issues | Diagnostics, Queue, Completed, Pending Publish, Launch, Home |
| `last_stdout_log` | Latest pipeline/audit run stdout log | Pipeline start/stop sequencing, heartbeat, signal handling | Diagnostics, Launch |
| `queue_snapshot` | Queue snapshot JSON file | Raw queue plan, route decisions, exclusion reasons | Diagnostics, Queue, Home |
| `completed_manifest` | `completed_jobs.jsonl` manifest | Output paths, sidecar state, route/size/audio/subtitle fields | Diagnostics, Completed, Home |
| `latest_failure_json` | Latest failure JSON artifact | Raw failure record: error code, stage, source path | Diagnostics, Reports, Pending Publish |
| `latest_failure_report` | Latest failure report file | Human-readable failure summary | Diagnostics, Reports |
| `cluster_log` | `{app_root}/cluster.log` | Multi-worker coordinator/worker session log | Diagnostics, Network |
| `config` | Active config PSD1 file | Current media-policy settings as seen by the pipeline | Diagnostics, Settings |
| `latest_audit_csv` | Most recent audit output CSV | Library audit rows, issue codes, source paths | Diagnostics, Reports |
| `latest_priority_csv` | Most recent priority CSV | Priority source paths for CSV rerun | Diagnostics, Reports |
| `sample_validation_log` | `{state_root}/Validation/sample_validation_log.jsonl` | Operator-appended sample validation evidence records | Diagnostics, Home |

---

## Folder Targets — Open Only (9 targets)

These targets resolve to directories. Only `/api/diagnostics/open` (Explorer open) is available. Tail is not applicable to folders.

| Target key | Resolves to | Primary diagnostic use | WebView pages that surface it |
|---|---|---|---|
| `run_logs` | `{app_root}/RunLogs` | Browse all pipeline launch log files by session | Diagnostics, Launch, Home |
| `active_jobs` | Active jobs state folder | Inspect current launch records and active job JSON | Diagnostics, Launch, Home |
| `state` | State root directory | Browse all runtime state subdirectories | Diagnostics, Home |
| `workspace` | Workspace / LocalBase root | Browse the full local app workspace | Diagnostics |
| `pending_publish` | Pending publish folder | Browse parked output manifest files | Diagnostics, Pending Publish, Home |
| `audit_reports` | Audit reports folder | Browse all generated audit CSV/report files | Diagnostics, Reports |
| `failed_markers` | Failure markers folder | Browse per-source failure marker files | Diagnostics, Reports |
| `failed_reports` | Failed reports folder | Browse per-source failure reports and artifacts | Diagnostics, Reports |
| `config_folder` | Parent directory of the active config PSD1 | Browse config directory (template, backups, prior saves) | Diagnostics, Settings |

---

## State Summary Inline Tail Targets

The Diagnostics State Artifact Summary panel reads a bounded excerpt of the following file targets inline (without requiring a separate `GET /api/diagnostics/tail` call):

| Target key | Panel use |
|---|---|
| `queue_snapshot` | Inline queue plan summary, item count, most recent produced_at |
| `completed_manifest` | Inline completed count, recent output paths |
| `latest_failure_json` | Inline failure stage and error code |
| `last_stderr_log` | Inline recent stderr excerpt (last N bytes) |
| `sample_validation_log` | Inline recent validation records |

These are read-only bounded tail reads. No write, move, or delete operation is performed.

---

## Mutation Guarantee Per Target

All 20 targets share the same read-only guarantee:

| Action | All targets |
|---|---|
| Modify, move, or delete target file/folder | Never |
| Write or append to target file | Never |
| Launch pipeline commands | Never |
| Change settings or config | Never |
| Drain or publish pending outputs | Never |
| Rename files on disk | Never |
| Alter queue state | Never |
| Follow symlinks outside workspace root | Never |
| Accept arbitrary path strings from frontend | Never |

---

## Full Allowlist Summary

| # | Target key | Type | Open | Tail |
|---|---|---|---|---|
| 1 | `last_stderr_log` | File | Yes | Yes |
| 2 | `last_stdout_log` | File | Yes | Yes |
| 3 | `queue_snapshot` | File | Yes | Yes |
| 4 | `completed_manifest` | File | Yes | Yes |
| 5 | `latest_failure_json` | File | Yes | Yes |
| 6 | `latest_failure_report` | File | Yes | Yes |
| 7 | `cluster_log` | File | Yes | Yes |
| 8 | `config` | File | Yes | Yes |
| 9 | `latest_audit_csv` | File | Yes | Yes |
| 10 | `latest_priority_csv` | File | Yes | Yes |
| 11 | `sample_validation_log` | File | Yes | Yes |
| 12 | `run_logs` | Folder | Yes | No |
| 13 | `active_jobs` | Folder | Yes | No |
| 14 | `state` | Folder | Yes | No |
| 15 | `workspace` | Folder | Yes | No |
| 16 | `pending_publish` | Folder | Yes | No |
| 17 | `audit_reports` | Folder | Yes | No |
| 18 | `failed_markers` | Folder | Yes | No |
| 19 | `failed_reports` | Folder | Yes | No |
| 20 | `config_folder` | Folder | Yes | No |

---

## Backend Enforcement

Allowlist enforcement is performed at the backend API layer in `routes_command.py` / `contract_command.py`:

- The frontend submits only a `target` key string — never a filesystem path.
- The backend looks up the key in the allowlist; any key not in the list is rejected before path resolution.
- The backend resolves the actual path from its own workspace state.
- No target key grants access to paths outside the configured workspace root.

Frontend validation (button enabled/disabled state) is a UX convenience only. Backend rejection is the authoritative gate.

---

## WebView Integration Points

| Page | Diagnostics targets surfaced |
|---|---|
| Home | `active_jobs`, `run_logs`, `last_stderr_log`, `queue_snapshot`, `pending_publish`, `completed_manifest`, `sample_validation_log` |
| Queue | `last_stderr_log`, `queue_snapshot`, `failed_markers` — via selected-row investigation strip |
| Completed | `completed_manifest`, `last_stderr_log`, `pending_publish` — via selected-row review checklist |
| Pending Publish | `last_stderr_log`, `latest_failure_json`, `pending_publish` — via drain evidence board |
| Launch | `last_stderr_log`, `run_logs`, `active_jobs`, `queue_snapshot`, `state`, `latest_failure_json`, `audit_reports`, `failed_reports` — via start-result detail |
| Reports | `latest_failure_json`, `latest_failure_report`, `failed_markers`, `failed_reports`, `audit_reports`, `latest_audit_csv` — via selected-row detail |
| Diagnostics | All 20 targets via target-specific buttons and tail/open controls |
| Settings | `config`, `config_folder` — via saved-config trust panel |
| Network | `cluster_log` — via worker session log |

---

## See Also

- Operator runbook: `Docs/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- Full API route ownership: `Docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- API route inventory: `Docs/API_ROUTE_INVENTORY.md`
- Command ownership matrix: `Docs/COMMAND_OWNERSHIP_MATRIX.md`
