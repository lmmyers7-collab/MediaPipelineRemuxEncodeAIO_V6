# Log Artifact Catalog

Date: 2026-07-15

Documents every log file, state file, and runtime artifact produced by MediaPipelineRemuxEncodeAIO: path pattern, producer service, WebView reader (if any), safe interpretation notes, and staleness behavior. Source: `contracts/`, `services/service_process_*.py`, `services/service_path_*.py`, `services/service_status_*.py`.

Path notation: `{local_base}` is the configured LocalBase (scratch root). `{state_root}` = `{local_base}/State`. `{app_root}` is the DesktopApp installation directory.

---

## State Root Directory Structure

```
{local_base}/
  State/
    ActiveJobs/         ← One JSON per running job
    Progress/           ← pipeline_progress.json, pipeline_events.jsonl, queue_snapshot.json
    Pipeline/           ← Control flags plus native-tool diagnostic lifecycle
      ToolLogs/
        Active/         ← Live native-tool captures; never failure evidence by presence alone
        Interrupted/    ← Stopped/force-terminated captures retained for short-term diagnostics
    Completed/          ← completed_jobs.jsonl (append-only manifest)
    PendingServerPush/  ← One JSON per parked output
    Failures/
      Artifacts/        ← Captures promoted only after an actual tool failure/timeout/runner exception
      Reports/          ← round_failures_*.json, round_failures_*.txt
      Markers/          ← Per-source failure marker files
      ResolutionJournal/ ← Failure Resolution Center lifecycle events
    Validation/         ← sample_validation_log.jsonl
  AuditReports/         ← audit_summary_*.csv, audit_summary_*.priority.csv
{app_root}/
  RunLogs/              ← Per-session launch logs (stdout, stderr)
  cluster.log           ← Network coordinator log
```

---

## Artifact Catalog

### Completed Jobs Manifest

| Field | Value |
|---|---|
| **Path** | `{state_root}/Completed/completed_jobs.jsonl` |
| **Format** | JSONL — one `CompletedJob` record per line |
| **Schema version** | `completed_job.v1` |
| **Producer** | Pipeline process (backend, on job completion) |
| **WebView access** | `GET /api/completed` (processed); `POST /api/diagnostics/open` (`completed_manifest` target); `GET /api/diagnostics/tail` (`completed_manifest` target) |
| **Staleness** | Append-only; never truncated. Rows appear fresh immediately after pipeline completion. Stale if pipeline crashed before writing the final record. |
| **Safe interpretation** | The presence of a row confirms the backend wrote a completion record. It does not confirm the output file still exists at `output_path`. |

---

### Pending Publish Manifests

| Field | Value |
|---|---|
| **Path** | `{state_root}/PendingServerPush/{publish_transaction_id}.json` |
| **Format** | One JSON file per parked output (`PendingPushManifest.v1`) |
| **Producer** | Pipeline process (backend, on deferred publish or park) |
| **WebView access** | `GET /api/pending-publish` (processed list); `POST /api/diagnostics/open` (`pending_publish` target) |
| **Staleness** | A manifest file remains until the drain succeeds and the record is promoted to `complete` / `published`. A `missing_payload` state means the manifest exists but its local file was deleted externally. |
| **Safe interpretation** | Check `manifest_state` before draining. States `do_not_drain` and `missing_payload` require investigation before drain. |

---

### Queue Snapshot

| Field | Value |
|---|---|
| **Path** | `{state_root}/Progress/queue_snapshot.json` |
| **Format** | JSON — one `QueuePlanSnapshot.v1` object |
| **Producer** | Queue dry-run service (backend, on each queue evaluation) |
| **WebView access** | `GET /api/queue` (processed); `POST /api/diagnostics/open` (`queue_snapshot` target); `GET /api/diagnostics/tail` (`queue_snapshot` target) |
| **Staleness** | Overwritten on each queue evaluation. If the pipeline has not run recently, the snapshot may not reflect current source library state. `produced_at` field indicates freshness. |
| **Safe interpretation** | Route decisions in the snapshot are predictions, not guarantees. The final route in the completed manifest may differ if runtime conditions change. |

---

### Pipeline Progress

| Field | Value |
|---|---|
| **Path** | `{state_root}/Progress/pipeline_progress.json` |
| **Format** | JSON — one `ProgressState` object |
| **Producer** | Pipeline process (backend, updated continuously during processing) |
| **WebView access** | `GET /api/snapshot` (embedded in snapshot payload) |
| **Staleness** | Stale if pipeline is idle or has crashed. The `last_update` field is the primary staleness indicator. The Live page surface a warning if `last_update` is older than the configured threshold. |
| **Safe interpretation** | `current_stage_percent` and `current_file` reflect the pipeline's last reported state. Do not interpret a stale progress record as proof the pipeline is still running. |

---

### Pipeline Events Log

| Field | Value |
|---|---|
| **Path** | `{state_root}/Progress/pipeline_events.jsonl` |
| **Format** | JSONL — one `PipelineEvent.v1` record per line |
| **Producer** | Pipeline process (backend, on stage transitions and completions) |
| **WebView access** | `GET /api/diagnostics` (recent events, processed) |
| **Staleness** | Appended during active pipeline runs. Old events are retained until the file is rotated by `LogRetentionDays`. |
| **Safe interpretation** | Events reflect backend-reported stage transitions. A `completed` event does not substitute for a Completed manifest record. |

---

### Active Job Records

| Field | Value |
|---|---|
| **Path** | `{state_root}/ActiveJobs/{launch_id}.json` |
| **Format** | JSON — one `ActiveJobRecord.v1` object per file |
| **Producer** | Process launch service (backend, written on launch and updated on status change) |
| **WebView access** | `GET /api/snapshot` (embedded); `POST /api/diagnostics/open` (`active_jobs` target) |
| **Staleness** | Records survive process termination. An `orphaned` status means the process record exists but no matching PID is running. Cleanup removes old records on startup. |
| **Safe interpretation** | A `completed` or `failed` active job record does not mean the output is in the Completed manifest — confirm via `completed_jobs.jsonl`. |

---

### Control Flag Files

| Field | Value |
|---|---|
| **Paths** | `{state_root}/Pipeline/pipeline_pause.flag`, `pipeline_stop.flag`, `pipeline_rescan.flag` |
| **Format** | Touch files — presence/absence is the signal; content is informational |
| **Producer** | `POST /api/pipeline/control` (`action: pause`, `stop`, or `rescan`) |
| **Consumer** | Pipeline process (reads and clears on next poll cycle) |
| **WebView access** | Indirectly via `GET /api/snapshot` (flag state reflected in status) |
| **Staleness** | Flags are consumed by the pipeline within one poll cycle. A stale flag (pipeline not running) has no effect — it will be ignored or cleaned up on next start. |
| **Safe interpretation** | A flag file present while the pipeline is idle is harmless. It will take effect when the pipeline restarts. |

---

### Failure Reports

| Field | Value |
|---|---|
| **Path** | `{state_root}/Failures/Reports/round_failures_*.json` and `round_failures_*.txt` |
| **Format** | JSON (structured failure record) and TXT (human-readable summary) |
| **Producer** | Pipeline process (backend, on job failure) |
| **WebView access** | `GET /api/failures` (processed); `POST /api/diagnostics/open` (`failed_reports` target, `latest_failure_report` target, `latest_failure_json` target); `GET /api/diagnostics/tail` (`latest_failure_json`, `latest_failure_report` targets) |
| **Staleness** | Written per failure round. The `latest_failure_json` and `latest_failure_report` targets always resolve to the most recent file by modification time. |
| **Safe interpretation** | A failure report confirms the pipeline encountered an error for the named source. It does not mean the source is permanently unprocessable — the failure may be transient. |

---

### Native-Tool Diagnostic Captures

| Field | Value |
|---|---|
| **Live path** | `{state_root}/Pipeline/ToolLogs/Active/*.log`; worker children use `{state_root}/Workers/slot-<n>/Logs/ToolLogs/Active/*.log` |
| **Interrupted path** | `{state_root}/Pipeline/ToolLogs/Interrupted/*.log`; worker children use the equivalent slot-local path |
| **Failure path** | `{state_root}/Failures/Artifacts/*.log`; worker children use their slot-local `Failures/Artifacts` path |
| **Format** | Plain text streamed from native-tool stderr |
| **Producer** | PowerShell native-tool wrapper (`tool_log_lifecycle.ps1`, currently FFmpeg integration) |
| **WebView access** | No direct file route. `tool_started`/`tool_completed` events carry `diagnostic_log_path` and `diagnostic_log_disposition` evidence. |
| **Staleness** | Successful captures are deleted. Operator stops move captures to `Interrupted`. Forced termination can leave `Active` files; the next exclusive startup reconciles them to `Interrupted`. Interrupted files older than `InterruptedToolLogRetentionDays` are deleted (default 3 days). |
| **Safe interpretation** | An `Active` capture means a tool started or the prior process ended before finalization; it is not a failure report. Only a `failure` disposition promotes the capture into `Failures/Artifacts`. |

---

### Failure Markers

| Field | Value |
|---|---|
| **Path** | `{state_root}/Failures/Markers/` — one file per failed source |
| **Format** | Touch file or small JSON — filename encodes source identity |
| **Producer** | Pipeline process (backend, on persistent failure after retries) |
| **Consumer** | Queue service (reads to exclude previously failed sources) |
| **WebView access** | `POST /api/diagnostics/open` (`failed_markers` target) |
| **Staleness** | Markers persist until the pipeline clears them or an operator manually removes them. A stale marker from an earlier pipeline version may incorrectly suppress a source that has since been fixed. |
| **Safe interpretation** | Marker presence means the source was failed on a prior run. Use Diagnostics `failed_markers` open → Reports selected-row detail → re-queue decision before re-attempting. |

---

### Failure Resolution Journal

| Field | Value |
|---|---|
| **Path** | `{state_root}/Failures/ResolutionJournal/events.jsonl` |
| **Format** | JSONL — one operator lifecycle event per line |
| **Producer** | Desktop app Failure Resolution Center (`POST /api/failures/lifecycle`; clear/archive commands append completion events when scoped to a group) |
| **Consumer** | Local API failure preview enrichment and Reports Failure Resolution Center |
| **WebView access** | `GET /api/failures` renders grouped lifecycle state; no diagnostics open target in v1 |
| **Staleness** | Append-only evidence; old events remain useful as audit trail even after active markers are cleared or archived. |
| **Safe interpretation** | Journal state records operator triage progress only. It does not prove media was repaired, rerun, published, or safe to delete. |

---

### Run Logs (Per-Session Launch Logs)

| Field | Value |
|---|---|
| **Path** | `{app_root}/RunLogs/` — one stdout log and one stderr log per launch |
| **Format** | Plain text |
| **Producer** | Process launch service (backend, on each pipeline/audit/rerun launch) |
| **WebView access** | `POST /api/diagnostics/open` (`run_logs` target); `GET /api/diagnostics/tail` (`last_stdout_log`, `last_stderr_log` targets) |
| **Staleness** | Log files are written for the lifetime of each launch. `last_stderr_log` and `last_stdout_log` always resolve to the most recent session. `LogRetentionDays` controls rotation (default 7 days). |
| **Safe interpretation** | `last_stderr_log` is the first diagnostic target for any FFmpeg, encoder, subtitle, or audio failure. The error message in stderr typically identifies the failed stage and source path. |

---

### Pipeline Debug Log

| Field | Value |
|---|---|
| **Path** | `{local_base}/pipeline_debug.log` |
| **Format** | Plain text |
| **Producer** | PowerShell pipeline logging |
| **WebView access** | `GET /api/diagnostics/tail` (`pipeline_log` target); `POST /api/diagnostics/open` (`pipeline_log` target); Pipeline Log window Raw tail mode |
| **Staleness** | The active process may not write or flush immediately. Treat timestamps as the evidence boundary for whether the tail belongs to the current run. |
| **Safe interpretation** | Use Raw tail mode when the compacted Pipeline Log activity view hides repeated progress lines or injected active-work evidence. |

---

### Cluster Log

| Field | Value |
|---|---|
| **Path** | `{app_root}/cluster.log` |
| **Format** | Plain text — structured log lines |
| **Producer** | Network coordinator and worker services |
| **WebView access** | `GET /api/diagnostics/tail` (`cluster_log` target); `POST /api/diagnostics/open` (`cluster_log` target) |
| **Staleness** | Appended by the coordinator process. Stale if no coordinator is running. |
| **Safe interpretation** | Use for network mode issues: worker registration failures, heartbeat timeouts, job assignment errors. Not produced in standalone mode. |

---

### Sample Validation Log

| Field | Value |
|---|---|
| **Path** | `{state_root}/Validation/sample_validation_log.jsonl` |
| **Format** | JSONL — one operator-appended evidence record per line |
| **Producer** | `POST /api/sample-validation/append` (operator action) |
| **WebView access** | `GET /api/sample-validation` (processed list); `POST /api/diagnostics/open` (`sample_validation_log` target); `GET /api/diagnostics/tail` (`sample_validation_log` target) |
| **Staleness** | Append-only. Records are never removed. Stale evidence (source/output no longer matches current state) is flagged by the backend reconciliation payload in `GET /api/sample-validation`. |
| **Safe interpretation** | A validation record is operator evidence only. It does not mark a job as completed, clear failures, or trigger any backend action. |

---

### Audit Report CSVs

| Field | Value |
|---|---|
| **Paths** | `{local_base}/AuditReports/audit_summary_*.csv`, `audit_summary_*.priority.csv` |
| **Format** | CSV — one row per audited source file |
| **Producer** | Audit service (`POST /api/audit/start`) |
| **WebView access** | `GET /api/audit-results` (processed); `POST /api/diagnostics/open` (`audit_reports` target, `latest_audit_csv` target, `latest_priority_csv` target); `GET /api/diagnostics/tail` (`latest_audit_csv`, `latest_priority_csv` targets) |
| **Staleness** | Each audit run appends a new dated file. `latest_audit_csv` and `latest_priority_csv` targets resolve to the most recent file. |
| **Safe interpretation** | A priority CSV lists sources flagged as needing attention; it does not rerun them automatically. Use as input to `POST /api/rerun/start`. |

---

### Local API Command History

| Field | Value |
|---|---|
| **Path** | `{app_root}/RunLogs/local_api_command_history.json` (or equivalent per-session journal) |
| **Format** | JSON — array of command journal entries |
| **Producer** | Local API handler (backend, on every POST command route invocation) |
| **WebView access** | `GET /api/commands` |
| **Staleness** | Written on every command invocation. `limit` query param controls how many recent entries are returned. |
| **Safe interpretation** | The command history reflects what the frontend has called — not what the backend has completed. A `process-launch` entry means the launch was requested, not that the process succeeded. |

---

### Active Config File

| Field | Value |
|---|---|
| **Path** | `{config_folder}/MediaPipeline_config_chatgpt.psd1` |
| **Format** | PowerShell data file (PSD1) |
| **Producer** | `POST /api/settings/save-patch` (backend, with backup) |
| **WebView access** | `GET /api/settings/workspace` (redacted read); `POST /api/diagnostics/open` (`config` target); `GET /api/diagnostics/tail` (`config` target) |
| **Staleness** | Updated atomically by save-patch. Backend state is reloaded after each save. A backup copy is created before each write. |
| **Safe interpretation** | Do not edit the PSD1 directly while the backend is running. Use `POST /api/settings/save-patch` to stage and apply changes. |

---

## Staleness Reference

| Artifact | Stale indicator | Action |
|---|---|---|
| `pipeline_progress.json` | `last_update` older than threshold | Check ActiveJobs to see if pipeline is still running |
| `queue_snapshot.json` | `produced_at` older than `SourceScanIntervalSeconds` | Trigger rescan or wait for next poll cycle |
| Active job record | `status: orphaned` | No live process; check `last_stderr_log` for crash details |
| `completed_jobs.jsonl` | Output path no longer exists on disk | Gap between manifest record and filesystem; manual investigation |
| `sample_validation_log.jsonl` | Reconciliation flags stale evidence | Re-validate or note as historical context only |
| Failure markers | From prior pipeline version | Review: the source may be safely reprocessable now |
| Config file | `last_update` differs from backend in-memory | Settings reload (`POST /api/settings/reload`) or restart |

---

## See Also

- State schema reference: `docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md`
- Diagnostics target allowlist: `docs/archive/completed-audits/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`
- Operator failure triage: `docs/operator/FAILURE_TRIAGE_WORKSHEET.md`
- Completed/Pending failure playbook: `docs/operator/COMPLETED_PENDING_FAILURE_PLAYBOOK.md`
