# Runtime Artifact Inventory

Purpose: reference map of runtime files and folders created, read, or mutated by the pipeline, desktop app, and local API. Use this when reading Diagnostics evidence, deciding whether a file is safe to inspect, or understanding what an operator-facing panel is showing.

**Warning**: Manual deletion of runtime state is unsafe unless a documented app command or runbook section explicitly says it is safe. Deleting active-job records, queue snapshots, or completed manifests while the pipeline is running may corrupt state the backend needs to resume safely. When in doubt, use the app's Diagnostics or Reports Clear Retry Blockers commands rather than editing files directly.

---

## State Root

Runtime state lives under `LocalBase\State\`. `LocalBase` is a config key; its default is the bundle root, but operators may set it to a different path.

---

## Local Work and Output Staging

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Scratch processing root | `Incoming\Processing\` | Pipeline (PS) | Source-to-scratch copy and temp subtitle/remux/encode helpers | Pipeline processing stages | No during active work; pipeline startup removes stale generated temp files and stale `src_*` scratch-copy folders only after boundary checks | N/A |
| Scratch-only rename stage undo record | `<scratch_root>\.mediapipeline-stage\rename\<operation-id>.json` | Python dispatcher | Planned/completed/rolled-back evidence for one scratch-local rename; never source, output, pending-publish, or final-library authority | Python stage runner and recovery review only | Keep until the scratch operation is accepted or recovered; removal follows scratch cleanup policy | `pipeline_stage_rename_undo.v1` |
| Scratch-only subtitle stage output/evidence | `<scratch-artifact>.srt` and `<scratch_root>\.mediapipeline-stage\subtitle-convert\<operation-id>.json` | Python dispatcher | One standalone ASS/SSA-to-SRT sidecar plus planned/completed/rolled-back evidence; never container, source, publish, or final-library authority | Python stage runner and subtitle review only | Keep until accepted or recovered; removal follows scratch cleanup policy | `pipeline_stage_subtitle_convert_evidence.v1` |
| Local encoded output staging | `Encoded\` | Pipeline (PS) | Remux/encode output before publish or pending-publish park | Publish, pending-publish park, and retry paths | No during active work; successful publish deletes local output files, and pipeline cleanup may remove only empty folders older than `CleanupStaleAgeHours` under this root | N/A |
| Remux temp root | `RemuxTemp\` | Pipeline (PS) | Remux helper work | Remux processing | No during active work | N/A |

---

## SQLite Mirror

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| SQLite state mirror | `State\mediapipeline_state.sqlite3` | Desktop app / Python stage tooling | Shadow writes from command journal entries, Python stage events, Queue dry-run snapshots, and Completed manifest rows | Troubleshooting only; JSON/state files remain authoritative | No while the backend is running; with the backend stopped it can be rebuilt opportunistically from future JSON/state activity | N/A |
| SQLite maintenance marker | `State\state_db_maintenance.json` | Desktop app / Python stage tooling | Opportunistic mirror maintenance after successful mirror writes | Long-run health evidence and Diagnostics/Home read-only summaries | No while the backend is running; with the backend stopped it can be removed to force a fresh best-effort maintenance attempt on the next mirror write | N/A |

The SQLite mirror is additive diagnostic evidence only. Do not use it as the source of truth for queue scope, completed output acceptance, pending publish drain decisions, command history rendering, or recovery actions.

---

## Progress and Queue

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Queue snapshot | `State\Progress\queue_snapshot.json` | Pipeline (PS) | `-EmitQueuePlan` flag | Desktop app, local API, WebView Queue | No — pipeline reads at startup and refresh | `queue_snapshot` |
| Progress JSON | `State\Progress\pipeline_progress.json` | Pipeline (PS) | Running pipeline | Desktop app, local API | No during active run | (via `state`) |
| Pipeline events log | `State\Progress\pipeline_events.jsonl` | Pipeline (PS) | Runtime events | Desktop app, WebView Diagnostics | No during active run; bounded-tail read is safe | (via `state`) |
| Encoder capability report | `State\Progress\encoder_capabilities.json` | Pipeline (PS) | `-DumpEncoderCapabilitiesPath` diagnostic | Operator diagnostics, `/api/settings/workspace` and `/api/launch/preflight` read-only encoder capability evidence | Yes only through journaled `POST /api/diagnostics/encoder-capabilities/refresh`; GET routes never regenerate it | N/A |
| Run log (stdout) | `State\Progress\last_stdout.log` | Pipeline (PS) | Pipeline stdout | Desktop app, Diagnostics | No during active run | `last_stdout_log` |
| Run log (stderr) | `State\Progress\last_stderr.log` | Pipeline (PS) | Pipeline stderr / FFmpeg output | Desktop app, Diagnostics | No during active run | `last_stderr_log` |
| Pipeline debug log | `pipeline_debug.log` | Pipeline (PS) | Main pipeline debug log | Pipeline Log window raw mode, Diagnostics | No during active run | `pipeline_log` |
| Run logs folder | `RunLogs\` (DesktopApp or LocalBase) | Pipeline (PS) | Per-run log files | Desktop app log-open, Diagnostics | After reviewing; old logs are safe | `run_logs` |

---

## Active Jobs

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| ActiveJobs folder | `State\ActiveJobs\` | Desktop app (Python) | Job launch commands | Status service, WebView Home / Diagnostics | No during active work | `active_jobs` |
| Per-job launch record | `State\ActiveJobs\<job-id>.json` | Desktop app (Python) | `POST /api/pipeline/start`, audit, rerun | Status service, Diagnostics | After job is confirmed complete and no longer shown in active state | `active_jobs` |

---

## Backend Lifecycle Reconciliation

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Lifecycle reconciliation transaction guard | `State\LifecycleReconciliationPending.json` | Local API (Python) | Confirmed `POST /api/backend/lifecycle/reconcile` while the archive transaction is in progress | Lifecycle lease guard and later reconciliation review if a transaction is interrupted | No — its presence deliberately blocks new lifecycle leases until transaction recovery is reviewed | N/A |
| Lifecycle reconciliation archive and manifest | `State\LifecycleArchive\<transaction-id>\Lifecycle\*`, `reconciliation-intent.json`, and `reconciliation-manifest.json` | Local API (Python) | Confirmed lifecycle reconciliation after exact dry-run correlation and strict command evidence | Operator recovery review and durable proof of the archived failed-recovery chain | No — retain the manifest and archived evidence together; never manually restore or delete individual files | N/A |

---

## Local Worker Slots

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Worker slot folder | `State\Workers\slot-<n>\` | Pipeline (PS) | Local worker execution | Pipeline worker scheduler and long-run health counters | No during active work | N/A |
| Worker metadata | `State\Workers\slot-<n>\worker_metadata.json` | Pipeline (PS) | Parent worker scheduler | Pipeline worker scheduler and operator evidence | No during active work | N/A |
| Worker result | `State\Workers\slot-<n>\worker_result.json` | Pipeline (PS) | Worker child on completion/failure | Parent worker scheduler | No during active work | N/A |
| Worker child heartbeat | `State\Workers\slot-<n>\worker_heartbeat.json` | Pipeline (PS) | Worker child on startup, stage changes, native progress, and final result | Parent worker scheduler and long-run health counters | No during active work; stale heartbeat is scheduler evidence, not an operator control surface | N/A |

---

## Completed Manifest

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Completed manifest | `State\Completed\completed_jobs.jsonl` | Pipeline (PS) | Successful job completion | Desktop app, local API, WebView Completed | No — only safe to rebuild via `Backfill-CompletedManifest` | `completed_manifest` |
| Desktop app state | `State\App\MediaPipelineRemuxEncodeAIO_DesktopApp.state.json` | Desktop app (Python) | Settings, schedule, and workspace state updates | Local API, WebView Settings/Schedule/Network | No — app owns lifecycle and legacy migration | N/A |

Legacy `DesktopApp\encode_speed_history.json` and `DesktopApp\MediaPipelineRemuxEncodeAIO_DesktopApp.state.json` are app-root runtime state from older builds. Current app state belongs under `LocalBase\State\App`; active workspaces should not keep or recreate app-root runtime state files.

---

## Failure State

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Failure markers | `State\Failures\Markers\` | Pipeline (PS) | Failed jobs | Queue exclusions, local API | Via Reports Clear Retry Blockers / `POST /api/failures/clear` only — not manual delete | `failed_markers` |
| Failure reports | `State\Failures\Reports\` | Pipeline (PS) | Failed jobs | Desktop app, Diagnostics | After reviewing and capturing evidence | `failed_reports` |
| Failure artifacts | `State\Failures\Artifacts\` and legacy `Failed\Artifacts\` | Pipeline (PS) | Failed jobs with captured scratch/output evidence | Local API `/api/failures/artifacts`, WebView Home and Reports; cleanup via `POST /api/failures/artifacts/cleanup` | No manual delete; only backend cleanup after strict confirmation; selected artifact paths still require a preview fingerprint | N/A |
| Latest failure JSON target | `State\Failures\Reports\round_failures_*.json` (newest by modification time) | Pipeline (PS) | Most recent failure report JSON | Local API, WebView Diagnostics | No during active investigation | `latest_failure_json` |
| Latest failure report target | `State\Failures\Reports\round_failures_*.txt` (newest by modification time) | Pipeline (PS) | Most recent failure report text | Desktop app, Diagnostics | After reviewing | `latest_failure_report` |
| Failure resolution journal | `State\Failures\ResolutionJournal\events.jsonl` | Desktop app (Python) | Reports failure lifecycle command | Failure Resolution Center, operator audit trail | No — retain as operator resolution evidence | N/A |
| Clear manifest | `State\Failures\ClearManifests\failure_clear_*.json` | Desktop app (Python) | Reports Clear Retry Blockers / failure-marker clear command | Operator audit trail | No — retain as evidence of cleared retry blockers | N/A |
| Cleared marker archive | `State\Failures\ClearManifests\ClearedMarkers\*` | Desktop app (Python) | Reports Clear Retry Blockers / failure-marker clear command | Operator audit trail | After confirming rerun behavior and keeping the clear manifest | N/A |
| Cleared evidence archive | `State\Failures\ClearManifests\ClearedEvidence\*` | Desktop app (Python) | Reports Advanced evidence archive / `POST /api/failures/archive-evidence` | Operator audit trail | After confirming the archive manifest is retained and active triage no longer needs the evidence | N/A |

---

## Pending Publish (Parked Outputs)

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Pending publish root | `State\PendingServerPush\` | Pipeline (PS) | Deferred publish events | Desktop app, local API, WebView Pending Publish | No — backend drain reads these | `pending_publish` |
| Pending publish manifests | `State\PendingServerPush\*.manifest.json` | Pipeline (PS) | Deferred publish, CSV rerun auto-review routing | Drain service, recovery dry-run | No — drain service owns lifecycle | `pending_publish` |
| Parked output payloads | `State\PendingServerPush\*` beside matching `.manifest.json` files | Pipeline (PS) | Deferred publish | Drain service | No — use recovery-plan to assess before draining | `pending_publish` |
| Drain summary | `State\Progress\pending_drain_summary.json` | Pipeline (PS) | Drain execution | WebView Pending Publish evidence | No during ongoing drain | `pending_publish` |

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
| Audit rerun import CSV | `State\Rerun\ImportCsv\audit_rerun_export_*.csv` | Desktop app (Python) | Reports audit export for CSV rerun | Rerun UI recent CSV picker, `/api/rerun/preview`, `/api/rerun/start` | After reviewing and when no rerun uses it | N/A |
| Scoped rerun CSV | `State\Rerun\ScopedCsv\rerun_scoped_*.csv`; `State\Rerun\ScopedCsv\rerun_continue_pending_*.csv` | Desktop app (Python) | `/api/rerun/start` when CSV preview scope excludes rows; `/api/rerun/continue` for stopped-after-current pending rows only | `Invoke-RerunCsv.ps1` launch input | After the corresponding rerun completes and evidence is retained | N/A |
| CSV rerun control marker | `State\Rerun\Control\stop_after_current.json` | Desktop app (Python) | `/api/rerun/control` | `Invoke-RerunCsv.ps1` after each completed row/window chunk | Yes after the matching rerun has written terminal manifest evidence; stale markers are ignored by batch/path/start-time checks | N/A |
| CSV rerun manifests | `RerunManifests\*.json` and `RerunManifests\*.config.psd1` | Pipeline (PS) | `Invoke-RerunCsv.ps1` | Queue/Home manifest fallback, rerun result reconciliation, Pending Publish promotion | No during active rerun; retain as launch/result evidence | N/A |
| CSV rerun workspace roots | Sibling of `LocalBase`: `<LocalBaseLeaf>_RerunWorkspace\RerunQueue\<batch>` and `<LocalBaseLeaf>_RerunWorkspace\RerunParked\<batch>` | Pipeline (PS) | `Invoke-RerunCsv.ps1` staging and parked output flows | Nested pipeline, rerun manifests, result reconciliation | No during active rerun; clean only after reviewing manifests and parked output state | N/A |
| CSV rerun replaced-final hold | `State\Rerun\FinalReplaced\<batch>\*` | Pipeline (PS) | Confirmed CSV rerun final replacement | Rerun manifest evidence and operator recovery | No until the replacement manifest/sidecar and final output have been reviewed | N/A |
| Priority CSV | Config-specified path | Pipeline (PS) | Audit run | Reports, Queue priority | After reviewing | `latest_priority_csv` |
| Audit reports folder | Config-specified path | Pipeline (PS) | Audit run | Desktop app, Diagnostics | After reviewing | `audit_reports` |

---

## Sample Validation Log

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Validation log | `State\Validation\sample_validation_log.jsonl` | Desktop app (Python) | `POST /api/sample-validation/append` | Home Validation Log, Diagnostics | Yes — operator evidence only; does not affect pipeline | `sample_validation_log` |

---

## UI Preferences

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Shared UI preferences | `State\ui_preferences.json` | Local API (Python) | `POST /api/ui-preferences` | Browser WebView and Tauri shell | After backend stop; resets local layout/theme/tab choices only | N/A |

---

## Command Journal

| Artifact | Location | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Command journal | In-memory bounded FIFO plus `RunLogs\local_api_command_history.json` when a journal path is configured | Local API (Python) | Successful command-result payloads from POST command routes | WebView Command History, Diagnostics; shadow-mirrored to SQLite when a state root is available | No while the backend is running; capture evidence before clearing historical RunLogs | (via `/api/commands`) |

---

## Config and Schedule

| Artifact | Relative path | Owner | Produced by | Consumed by | Safe to delete manually | Diagnostics target key |
|---|---|---|---|---|---|---|
| Live config | `ops\pipeline\config\MediaPipeline_config_chatgpt.psd1` | Operator / Setup wizard | Setup wizard, `POST /api/settings/save-patch` | Pipeline, all services | No — back up before editing | `config` |
| Config folder | `Pipeline\` | — | — | — | No | `config_folder` |
| Config backups | `ops\pipeline\config\backups\MediaPipeline_config*.backup_*.psd1` | Desktop app (Python) | `POST /api/settings/save-patch` (auto-backup) | Recovery only | Yes — after verifying live config is correct | `config_folder` |
| Schedule state | Config-specified path | Desktop app (Python) | Schedule UI or setup | `GET /api/schedule`, Launch page | No | (via `state`) |

---

## Diagnostics Target Quick Reference

The following `POST /api/diagnostics/open` allowlisted target keys map to the artifacts above:

`run_logs`, `pipeline_log`, `cluster_log`, `config`, `config_folder`, `workspace`, `state`, `pending_publish`, `failed_reports`, `failed_markers`, `audit_reports`, `queue_snapshot`, `active_jobs`, `completed_manifest`, `latest_failure_report`, `latest_failure_json`, `latest_audit_csv`, `latest_priority_csv`, `last_stdout_log`, `last_stderr_log`, `sample_validation_log`

Full allowlist with mutation-safety notes: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`.

---

## See Also

- Current operating state: `docs/CURRENT_PROJECT_STATE.md`
- Diagnostics target runbook: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- Failure triage: `docs/operator/FAILURE_TRIAGE_WORKSHEET.md`
- Route and mutation ownership: `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
