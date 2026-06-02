# Diagnostics Read-Only Targets Runbook

This runbook documents every diagnostics target exposed to WebView through `/api/diagnostics/open` and `/api/diagnostics/tail`, states what each is safe for, and gives operator sequences for common diagnostic scenarios.

## Scope And Safety Contract

All targets listed here are backend-allowlisted. The WebView cannot open or tail arbitrary paths — every request is validated against the allowlist before the backend resolves or reads any path. The frontend passes only target key strings, never raw filesystem paths.

`/api/diagnostics/open` → opens a target in the OS file manager (Explorer). Returns a command-journal result. Does not move, edit, delete, or write any file.

`/api/diagnostics/tail` → returns a bounded text excerpt from a file-backed target. Clamped to 64 KB by default (operator-configurable 1 KB–256 KB). Does not open a shell, write, move, or delete the file.

Neither route processes media, launches pipeline work, changes settings, publishes parked outputs, renames files, or mutates queue state.

---

## Target Catalog

### File Targets — Open and Tail Capable

These targets back a physical file. Both `/api/diagnostics/open` and `/api/diagnostics/tail` are available.

| Target key | Resolves to | Primary use |
|---|---|---|
| `last_stderr_log` | Latest launch stderr log (most recent pipeline/audit run) | First stop for FFmpeg errors, encoder failures, subtitle/audio issues |
| `last_stdout_log` | Latest launch stdout log | Pipeline start/stop sequencing, heartbeat, signal handling |
| `queue_snapshot` | Queue snapshot JSON file | Inspect raw queue plan, route decisions, exclusion reasons |
| `completed_manifest` | Completed jobs JSONL manifest | Inspect output paths, sidecar state, route/size/audio/subtitle fields |
| `latest_failure_json` | Latest failure JSON artifact | Raw failure record including error code, stage, source path |
| `latest_failure_report` | Latest failure report file | Human-readable failure summary |
| `cluster_log` | `{app_root}/cluster.log` | Multi-worker coordinator/worker session log |
| `config` | Active config PSD1 file | Current media-policy settings as seen by the pipeline |
| `latest_audit_csv` | Most recent audit output CSV | Library audit rows, issue codes, source paths |
| `latest_priority_csv` | Most recent priority CSV | Priority source paths for CSV rerun |
| `sample_validation_log` | `{state_root}/Validation/sample_validation_log.jsonl` | Operator-appended sample validation evidence records |

### Folder Targets — Open Only

These targets resolve to directories. Only `/api/diagnostics/open` (Explorer open) is available. Tail is not applicable.

| Target key | Resolves to | Primary use |
|---|---|---|
| `run_logs` | `{app_root}/RunLogs` | Browse all pipeline launch log files |
| `active_jobs` | Active jobs state folder | Inspect current launch records |
| `state` | State root directory | Browse all runtime state subdirectories |
| `workspace` | Workspace/LocalBase root | Browse the full local app workspace |
| `pending_publish` | Pending publish folder | Browse parked output manifest files |
| `audit_reports` | Audit reports folder | Browse all generated audit CSV/report files |
| `failed_markers` | Failure markers folder | Browse per-source failure markers |
| `failed_reports` | Failed reports folder | Browse per-source failure reports and artifacts |
| `config_folder` | Parent directory of the active config file | Browse config directory (template, backups) |

### State Summary Tail Targets

These file targets are also recommended by the Diagnostics State Artifact Summary panel as bounded tail targets. The panel summarizes metadata inline; when an operator chooses to read text, the WebView calls `/api/diagnostics/tail` with the backend allowlisted target key:

- `queue_snapshot`
- `completed_manifest`
- `latest_failure_json`
- `last_stderr_log`
- `sample_validation_log`

---

## What Each Target Does Not Mutate

All diagnostics targets are read-only from the WebView perspective:

- Opening a folder does not modify, move, or delete its contents.
- Tailing a file reads a bounded excerpt and does not write, append, or truncate the file.
- Neither open nor tail can launch pipeline commands, change settings, publish parked outputs, rename files, or alter queue state.
- The backend rejects raw frontend paths. It resolves each target from current backend state/config; if a configured backend target itself points through a symlink, junction, or reparse point, diagnostics reports/opens/reads that configured target using normal OS/Python path behavior. Treat unexpected resolved paths as a configuration or state issue before trusting the evidence.

---

## Operator Sequences

### Queue Issue: Source Not Appearing Or Blocked

1. Open the Queue page and inspect the selected-row review checklist and issue digest.
2. If the row shows a blocked reason code: check `queue_snapshot` (tail) for raw exclusion reason and source path.
3. If runtime history shows a recent failure: tail `last_stderr_log` for the FFmpeg or script error.
4. If the failure is persisted: tail `latest_failure_json` for stage and error code; open `failed_markers` to browse raw markers.
5. Use Queue → Review in Diagnostics bridge for the highest-priority backend-suggested target.

### Completed Issue: Missing Output, Size Growth, Or Sidecar Problem

1. Open the Completed page and inspect the selected-row review checklist and consistency/size-growth panels.
2. Tail `completed_manifest` for the raw output path, route, sidecar fields, and size comparison.
3. If a size-growth outlier: tail `last_stderr_log` for encoder decision and growth boundary.
4. If a sidecar mismatch: open `pending_publish` folder to check whether a parked sidecar manifest exists.
5. If no output path: open `run_logs` to browse log files for the session that produced the row.

### Pending Publish Issue: Do-Not-Drain, Missing Payload, Or Unreadable Manifest

1. Open Pending Publish, inspect the selected-row review checklist, drain evidence board, and recovery dry-run output.
2. If `do_not_drain` or `missing_payload`: tail `last_stderr_log` for the drain attempt error; tail `latest_failure_json` if a failure was recorded during the drain run.
3. If `unreadable_manifest` or `invalid_contract`: open the `pending_publish` folder to inspect the raw JSON manifest file.
4. If `orphan_payload`: the payload file exists without a manifest — open `pending_publish` and compare against Completed manifest rows via the cross-check panel.
5. Use Pending Publish → Recovery Dry-Run to get backend-authored planned actions before any drain attempt.

### Settings Issue: Saved Config Appears Invalid Or Mismatched

1. Open Settings, inspect the Saved Settings Trust panel and Active Media Policy Handoff rows.
2. Tail `config` to verify the raw saved config key values seen by the backend.
3. If validation warnings: check Settings workspace `/api/settings/workspace` risk-preview for the flagged keys.
4. Open `config_folder` to inspect backup files or compare against the template.
5. Use Settings → Preview Patch / Save Patch through backend-owned routes only; do not edit the file directly.

### General: Unexplained Error After Pipeline Run

1. Tail `last_stderr_log` for the most recent run's raw output (try this first).
2. Tail `last_stdout_log` for sequencing, heartbeat, or unexpected exit signals.
3. Open `run_logs` to browse earlier sessions if the error predates the most recent run.
4. Tail `queue_snapshot` to verify the source was in the plan and had the expected route.
5. Tail `completed_manifest` to check whether a completed record was written.
6. Open `state` to browse all runtime state if the issue involves control flags, active jobs, or pending events.

---

## Integration With WebView Panels

- **Diagnostics page** — State Artifact Summary, log triage, ActiveJobs, and tail reader all use these target keys. The investigation trail suggests open/tail sequences based on detected severity.
- **Queue, Completed, Pending Publish** — Selected-row diagnostics action strips offer direct open/tail buttons for the most relevant targets for that row's state.
- **Launch** — Immediate start-result detail includes read-first/open-next guidance pointing to `last_stderr_log`, `run_logs`, `active_jobs`, `queue_snapshot`, `state`, `latest_failure_json`, `audit_reports`, and `failed_reports` depending on flow.
- **Reports** — Failure/Audit selected-row detail offers open buttons for `latest_failure_json`, `latest_failure_report`, `failed_markers`, `failed_reports`, `audit_reports`, and `latest_audit_csv`.
- **Home** — Runtime artifact quick-opens offer `active_jobs`, `run_logs`, `last_stderr_log`, `queue_snapshot`, `pending_publish`, and `completed_manifest`.

### Scope Preview Panels as Pre-Investigation Context

Before tailing any target for a launch or drain issue, read the relevant scope preview panel first:

- **Queue Backend Launch Scope Preview** (Queue page, read-only) — shows the loaded-row count versus visible-filtered-row count, the backend launch route authority, the most recent cached preflight evidence, and recent launch command evidence from the command journal. Use this to confirm that no blocked rows are hidden by an active filter before proceeding to `queue_snapshot` or `last_stderr_log` investigation.
- **Pending Backend Drain Scope Preview** (Pending Publish page, read-only) — shows the parked-row count versus visible-filtered-row count, the backend drain route authority, the most recent durable drain summary, and recent drain command evidence. Use this to confirm the scope of the next drain before running a Recovery Dry-Run or tailing `last_stderr_log`.

Both panels are evidence-only reads — they issue no routes, change no state, and do not narrow or widen backend scope. They are context, not a replacement for diagnostics tail and open investigation.

---

## See Also

- Scope preview operator guide: `Docs/operator/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md`
- Completed/Pending failure playbook: `Docs/operator/COMPLETED_PENDING_FAILURE_PLAYBOOK.md`
- Diagnostics target allowlist audit: `Docs/archive/completed-audits/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`
- Log artifact catalog: `Docs/inventories/LOG_ARTIFACT_CATALOG.md`

---

## Freshness Review — 2026-05-15 (CLN4-025)

Added **Scope Preview Panels as Pre-Investigation Context** section recommending `Queue Backend Launch Scope Preview` and `Pending Backend Drain Scope Preview` as initial context checks before tailing any diagnostics target for launch or drain issues. Added **See Also** section with crosslink to `WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md`.

```
Task ID: CLN4-025
Files inspected: Docs\operator\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md (all 20 targets, operator sequences, integration section)
Files changed: Docs\operator\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md (scope preview pre-investigation context section added; See Also section added)
Validation: Select-String -Path Docs\operator\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md -Pattern "Backend Launch Scope Preview|Backend Drain Scope Preview"
Findings: No prior scope preview reference; both panels added to Integration section as pre-investigation context.
Open questions: None.
Risk: Low — documentation only.
```
