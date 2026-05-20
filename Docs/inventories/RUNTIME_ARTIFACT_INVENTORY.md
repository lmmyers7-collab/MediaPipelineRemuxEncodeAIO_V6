# Runtime Artifact Inventory

Purpose: reference map of runtime files and folders created, read, or mutated by the pipeline, desktop app, and local API. Use this when reading Diagnostics evidence, deciding whether a file is safe to inspect, or understanding what an operator-facing panel is showing.

**Warning**: Manual deletion of runtime state is unsafe unless a documented app command or runbook section explicitly says it is safe. Deleting active-job records, queue snapshots, or completed manifests while the pipeline is running may corrupt state the backend needs to resume safely. When in doubt, use the app's Diagnostics or Reports Clear Retry Blockers commands rather than editing files directly.

---

## State Root

Runtime state lives under `LocalBase\State\`. `LocalBase` is a config key; its default is the bundle root, but operators may set it to a different path.

---

## Progress and Queue

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Queue snapshot | `State\Progress\queue_plan_snapshot.json` | Pipeline (PS) | `-EmitQueuePlan` flag | Desktop app, local API, WebView Queue | No — pipeline reads at startup and refresh | `queue_snapshot` |
| Progress JSON | `State\Progress\pipeline_progress.json` | Pipeline (PS) | Running pipeline | Desktop app, local API | No during active run | (via `state`) |
| Pipeline events log | `State\Progress\pipeline_events.jsonl` | Pipeline (PS) | Runtime events | Desktop app, WebView Diagnostics | No during active run; bounded-tail read is safe | (via `state`) |
| Run log (stdout) | `State\Progress\last_stdout.log` | Pipeline (PS) | Pipeline stdout | Desktop app, Diagnostics | No during active run | `last_stdout_log` |
| Run log (stderr) | `State\Progress\last_stderr.log` | Pipeline (PS) | Pipeline stderr / FFmpeg output | Desktop app, Diagnostics | No during active run | `last_stderr_log` |
| Run logs folder | `RunLogs\` (DesktopApp or LocalBase) | Pipeline (PS) | Per-run log files | Desktop app log-open, Diagnostics | After reviewing; old logs are safe | `run_logs` |

---

## Active Jobs

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| ActiveJobs folder | `State\ActiveJobs\` | Desktop app (Python) | Job launch commands | Status service, WebView Home / Diagnostics | No during active work | `active_jobs` |
| Per-job launch record | `State\ActiveJobs\<job-id>.json` | Desktop app (Python) | `POST /api/pipeline/start`, audit, rerun | Status service, Diagnostics | After job is confirmed complete and no longer shown in active state | `active_jobs` |

---

## Completed Manifest

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Completed manifest | `State\Completed\completed_jobs.jsonl` | Pipeline (PS) | Successful job completion | Desktop app, local API, WebView Completed | No — only safe to rebuild via `Backfill-CompletedManifest` | `completed_manifest` |
| Desktop app state | `State\App\MediaPipelineRemuxEncodeAIO_DesktopApp.state.json` | Desktop app (Python) | Settings, schedule, and workspace state updates | Local API, WebView Settings/Schedule/Network | No — app owns lifecycle and legacy migration | N/A |

Legacy `DesktopApp\encode_speed_history.json` and `DesktopApp\MediaPipelineRemuxEncodeAIO_DesktopApp.state.json` are app-root runtime state from older builds. Current V6 app state belongs under `LocalBase\State\App`; active workspaces should not keep or recreate app-root runtime state files.

---

## Failure State

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Failure markers | `State\Failures\Markers\` | Pipeline (PS) | Failed jobs | Queue exclusions, local API | Via Reports Clear Retry Blockers / `POST /api/failures/clear` only — not manual delete | `failed_markers` |
| Failure reports | `State\Failures\reports\` | Pipeline (PS) | Failed jobs | Desktop app, Diagnostics | After reviewing and capturing evidence | `failed_reports` |
| Latest failure JSON | `State\Failures\latest_failure.json` | Pipeline (PS) | Most recent failure | Local API, WebView Diagnostics | No during active investigation | `latest_failure_json` |
| Latest failure report | `State\Failures\latest_failure_report.txt` | Pipeline (PS) | Most recent failure | Desktop app, Diagnostics | After reviewing | `latest_failure_report` |
| Clear manifest | `State\Failures\ClearManifests\failure_clear_*.json` | Desktop app (Python) | Reports Clear Retry Blockers / failure-marker clear command | Operator audit trail | No — retain as evidence of cleared retry blockers | N/A |
| Cleared marker archive | `State\Failures\ClearManifests\ClearedMarkers\*` | Desktop app (Python) | Reports Clear Retry Blockers / failure-marker clear command | Operator audit trail | After confirming rerun behavior and keeping the clear manifest | N/A |

---

## Pending Publish (Parked Outputs)

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Pending publish root | `State\PendingServerPush\` | Pipeline (PS) | Deferred publish events | Desktop app, local API, WebView Pending Publish | No — backend drain reads these | `pending_publish` |
| Per-batch manifests | `State\PendingServerPush\<batch>\manifest.json` | Pipeline (PS) | Deferred publish | Drain service, recovery dry-run | No — drain service owns lifecycle | `pending_publish` |
| Parked output payloads | `State\PendingServerPush\<batch>\<files>` | Pipeline (PS) | Deferred publish | Drain service | No — use recovery-plan to assess before draining | `pending_publish` |
| Drain summary | `State\PendingServerPush\pending_drain_summary.json` | Pipeline (PS) | Drain execution | WebView Pending Publish evidence | No during ongoing drain | `pending_publish` |

---

## Pipeline Control Flags

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Pause flag | `State\Pipeline\pipeline_pause.flag` | Desktop app (Python) | `POST /api/pipeline/control` (pause) | Running pipeline | No — app owns lifecycle; use app commands | N/A |
| Stop flag | `State\Pipeline\pipeline_stop.flag` | Desktop app (Python) | `POST /api/pipeline/control` (stop) | Running pipeline | No | N/A |
| Rescan flag | `State\Pipeline\pipeline_rescan.flag` | Desktop app (Python) | `POST /api/pipeline/control` (rescan) | Running pipeline | No | N/A |

---

## Audit and Rerun

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Audit CSV output | Config-specified audit path | Pipeline (PS) | `POST /api/audit/start` | Reports, Rerun UI | After reviewing | `latest_audit_csv` |
| Priority CSV | Config-specified path | Pipeline (PS) | Audit run | Reports, Queue priority | After reviewing | `latest_priority_csv` |
| Audit reports folder | Config-specified path | Pipeline (PS) | Audit run | Desktop app, Diagnostics | After reviewing | `audit_reports` |

---

## Sample Validation Log

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Validation log | `State\Validation\sample_validation_log.jsonl` | Desktop app (Python) | `POST /api/sample-validation/append` | Home Validation Log, Diagnostics | Yes — operator evidence only; does not affect pipeline | `sample_validation_log` |

---

## Command Journal (In-Memory)

| Artifact | Location | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Command journal | In-memory bounded FIFO | Local API (Python) | Every POST command route | WebView Command History, Diagnostics | N/A — in-memory; resets on backend restart | (via `/api/commands`) |

---

## Config and Schedule

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Live config | `Pipeline\MediaPipeline_config_chatgpt.psd1` | Operator / Setup wizard | Setup wizard, `POST /api/settings/save-patch` | Pipeline, all services | No — back up before editing | `config` |
| Config folder | `Pipeline\` | — | — | — | No | `config_folder` |
| Config backups | `Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1` | Desktop app (Python) | `POST /api/settings/save-patch` (auto-backup) | Recovery only | Yes — after verifying live config is correct | `config_folder` |
| Schedule state | Config-specified path | Desktop app (Python) | Schedule UI or setup | `GET /api/schedule`, Launch page | No | (via `state`) |

---

## Diagnostics Target Quick Reference

The following `POST /api/diagnostics/open` allowlisted target keys map to the artifacts above:

`run_logs`, `cluster_log`, `config`, `config_folder`, `workspace`, `state`, `pending_publish`, `failed_reports`, `failed_markers`, `audit_reports`, `queue_snapshot`, `active_jobs`, `completed_manifest`, `latest_failure_report`, `latest_failure_json`, `latest_audit_csv`, `latest_priority_csv`, `last_stdout_log`, `last_stderr_log`, `sample_validation_log`

Full allowlist with mutation-safety notes: `Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`.

---

## See Also

- State layout summary: `Docs/TLDR.md` (Runtime State section)
- Diagnostics target runbook: `Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- Failure triage: `Docs/operator/FAILURE_TRIAGE_WORKSHEET.md`
- Route and mutation ownership: `Docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
