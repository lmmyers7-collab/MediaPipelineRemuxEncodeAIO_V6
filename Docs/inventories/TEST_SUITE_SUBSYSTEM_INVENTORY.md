# Test Suite Subsystem Inventory

Purpose: map the `DesktopApp\tests\` test suite by subsystem so contributors can choose targeted tests for a given change. All counts are approximate; the suite grows over time.

Validation command:

```powershell
Get-ChildItem DesktopApp\tests -Filter test_*.py | Measure-Object
```

---

## Running Targeted Tests

All tests use the bundled Python:

```powershell
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m unittest <module.path> -q
```

Run a full subsystem via discovery:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "<pattern>" -q
```

---

## PowerShell Guard Checks

These focused PowerShell checks sit outside `DesktopApp\tests` and guard cross-cutting repo hygiene or pipeline contracts:

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-ActiveDocsReferenceChecks.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-RepoHygieneChecks.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-RuntimeStateHygieneChecks.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-PortablePathChecks.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-PendingPublishOwnershipChecks.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-PendingPublishSafetyChecks.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-FailureCodeRegistryChecks.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Invoke-AdversarialForceKillEncodeChecks.ps1
```

`Invoke-ActiveDocsReferenceChecks.ps1` guards post-reorg active-doc links for moved source-of-truth docs, blocks root-level references to superseded housekeeping report names unless they point at `Docs/archive/admin-audits`, and prevents high-level status/checklist docs from embedding absolute local current-handoff paths. Historical archive files and the forensic changelog are intentionally excluded so old evidence can remain unchanged.

`Invoke-RepoHygieneChecks.ps1` guards root generated log/jsonl captures, DesktopApp root API validation captures, rebuildable pytest/Tauri artifacts, and the ignore entries that keep those artifacts out of source review.

`Invoke-AdversarialForceKillEncodeChecks.ps1` is a runtime adversarial smoke rather than a static guard. It creates generated media in `%TEMP%`, starts the real backend in `-Once`, force-kills a live CPU fallback encode after an `encode_temp_cpu_*.mkv` artifact exists, then proves the partial was not accepted as completed output/pending publish and the source remains queued.

`Invoke-FailureCodeRegistryChecks.ps1` guards the `FailureCodes.ps1` registry: every classifier return code must be known, every registry row must include family/stage/when-fires/retryability/operator severity/handler/operator-action metadata, representative high-risk metadata rows must stay accurate, broader pipeline outcome/error codes emitted by PowerShell surfaces must be known, and unknown-code metadata lookup must fail closed.

`Invoke-ConfigKeyRegistryChecks.ps1` guards `ConfigKeys.ps1`: the PowerShell config-key registry must stay in the same order as `ConfigSchema.ps1`, template/live PSD1 files may not contain unknown keys, helper lookups must fail closed, and literal PowerShell `$config[...]`, `$config.ContainsKey(...)`, and `Get-Config*` call sites may not reference unknown config keys. `test_config_keys.py` also guards Python-side Network runtime and settings/media-policy raw registered-key lookups, plus a package-wide registered-key raw-lookup scan across `mediapipeline_desktop_app`.

---

## Subsystem Index

### Config

Tests for config loading, PSD1 parsing, key resolution, profile validation, and save/reload runners.

| Test file | What it covers |
|---|---|
| `test_config_service.py` | General config service behavior |
| `test_service_config_psd1.py` | PSD1 parse, key types, defaults |
| `test_service_config_profiles.py` | Profile loading and merging |
| `test_service_config_value_checks.py` | Value validation rules |
| `test_service_config_validation.py` | Cross-field config validation, path overlap warnings, and BDPGS OCR enabled-without-tool-path warning |
| `test_config_keys.py` | Config-key registry alignment across Python settings schema, network defaults, PowerShell ordered pipeline config keys, Network runtime raw-lookup drift, settings/media-policy raw-lookup drift, and package-wide registered-key lookup drift |
| `Pipeline/Tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1` | PowerShell config-key registry alignment, PSD1 known-key coverage, and literal PowerShell config-reference drift |
| `test_service_config_path_warnings.py` | Path key warning logic |
| `test_service_config_numeric_policy.py` | Numeric range and policy checks |
| `test_service_config_document_runner.py` | Config document runner, subprocess capture handoff, and Protocol-typed config service boundary |
| `test_service_config_save_runner.py` | Config atomic-save/profile runner and Protocol-typed save service boundary |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*config*.py" -q
```

Coverage gap: live-config write integration test against a real PSD1 file.

---

### Status, Progress, and Telemetry

Tests for pipeline state, progress tracking, event reading, snapshot assembly, and CPU/RAM/GPU sampling.

| Test file | What it covers |
|---|---|
| `test_status_service.py` | General status service |
| `test_service_status_errors.py` | Error state classification |
| `test_service_status_progress.py` | Progress field parsing |
| `test_service_status_ffmpeg_progress.py` | FFmpeg progress proof payload parsing, read-only contract shape, parse-error reporting for active encode/remux evidence without key/value fields, and idle no-fake-row behavior |
| `test_service_status_eta.py` | ETA telemetry payload calculation from worker-progress percent/elapsed evidence, unavailable-reason reporting when ETA cannot be estimated, read-only contract shape, and idle no-fake-row behavior |
| `test_service_status_files.py` | Status file discovery |
| `test_service_status_summary.py` | Summary aggregation |
| `test_service_status_presentation.py` | Presentation formatting |
| `test_service_status_events.py` | Event log reading |
| `test_service_status_summary_sections.py` | Summary section assembly |
| `test_service_status_snapshot_runner.py` | Snapshot runner and Protocol-typed status snapshot service boundary |
| `test_application_facade_snapshot.py` | Application-facade snapshot assembly, progress bar presentation for publish/audit/subtitle/copy work, ActiveJobs diagnostics rows, and zero-percent GPU telemetry mapping |
| `test_service_app_schedule.py` | Schedule state service |
| `test_telemetry_service.py` | CPU/RAM/GPU telemetry |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*status*.py" -q
& $py -m unittest DesktopApp.tests.test_telemetry_service -q
```

---

### Queue

Tests for queue priority marking, snapshot reading, dry-run planning, preview builder, and dry-run runner.

| Test file | What it covers |
|---|---|
| `test_service_queue_priority.py` | Priority marker detection and ordering |
| `test_service_queue_snapshot.py` | Snapshot file reading and validation |
| `test_service_queue_dry_run.py` | Dry-run route planning logic |
| `test_service_queue_dry_run_runner.py` | Dry-run runner execution and Protocol-typed queue dry-run service boundary |
| `test_service_queue_preview_builder.py` | Queue preview payload builder and Protocol-typed queue preview service boundary |
| `test_application_facade_queue.py` | Application-facade queue preview snapshot-read behavior, stale evidence, visible blocked rows versus exclusions, runtime outcome correlation, and backend row-key queue open allowlists |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*queue*.py" -q
```

Coverage gap: end-to-end queue → launch → completed flow; adversarial blocked/excluded row coverage beyond what fixture data provides.

---

### Process Launch and Lifecycle

Tests for launch environment setup, launch plans, spawn, kill, readiness checks, cleanup, control flags, and runner coordination.

| Test file | What it covers |
|---|---|
| `test_subprocess_runner.py` | Subprocess runner utilities |
| `test_service_process_active_jobs.py` | ActiveJobs record read/write/reconcile behavior and logger Protocol boundary |
| `test_service_process_control_flags.py` | Pause/stop/rescan flag read/write and logger Protocol boundary |
| `test_service_process_launch_env.py` | PATH setup, bundled tool injection |
| `test_service_process_logs.py` | Log file location and rotation |
| `test_service_process_runtime_artifacts.py` | Runtime artifact management |
| `test_service_process_launch_plans.py` | Launch plan construction |
| `test_service_process_kill.py` | Process kill/cleanup behavior and warning logger Protocol boundary |
| `test_service_process_spawn.py` | Process spawn logic |
| `test_service_process_readiness.py` | Pre-launch readiness checks and spawn readiness logger Protocol boundary |
| `test_service_process_launch_cleanup.py` | Post-launch cleanup and warning logger Protocol boundary |
| `test_service_process_launch_runner.py` | Launch runner coordination and Protocol-typed launch service boundary |
| `test_service_process_control_runner.py` | Control flag runner and Protocol-typed control service boundary |
| `test_service_process_runtime_runner.py` | Runtime runner and Protocol-typed runtime cleanup service boundary |
| `test_service_process_active_job_runner.py` | ActiveJobs record management and Protocol-typed ActiveJobs service boundary |
| `test_service_process_spawn_runner.py` | Spawn runner and Protocol-typed spawn service boundary |
| `test_process_service.py` | General process service |
| `test_facade_process_control_policy.py` | Facade: control policy |
| `test_facade_process_schedule_policy.py` | Facade: schedule policy |
| `test_facade_process_guard_policy.py` | Facade: guard policy |
| `test_facade_process_audit_policy.py` | Facade: audit launch policy |
| `test_facade_process_pipeline_policy.py` | Facade: pipeline launch policy |
| `test_facade_process_rerun_policy.py` | Facade: rerun policy |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*process*.py" -q
& $py -m unittest discover -s DesktopApp\tests -p "test_facade_process*.py" -q
```

Closed coverage gap: `test_application_facade_process_launch.py` now starts one pipeline, reports the first bundle-owned child process as still running, and confirms a second pipeline launch is rejected before the service launcher is called again.

Closed runtime safety gap: `Pipeline\Tests\Invoke-AdversarialForceKillEncodeChecks.ps1` force-kills a real backend encode process tree and confirms the byte-bearing temp output is not accepted as complete, no completed/pending-publish state is written, the source hash remains unchanged, and the source remains backend-queued after restart planning.

---

### Completed

Tests for completed manifest reading, consistency checks, and backfill.

| Test file | What it covers |
|---|---|
| `test_service_completed_validation_state.py` | Completed validation-state contract from completed rows, including output-presence proof, missing-output blockers, unavailable probe/hash/playback proof, and future complete proof |
| `test_service_completed_manifest.py` | Manifest read and validation |
| `test_service_completed_backfill.py` | Backfill runner logic |
| `test_facade_completed_open_policy.py` | Facade: completed open policy |
| `test_application_facade_completed.py` | Application-facade completed preview manifest/progress evidence, validation-state child payload, size/runtime/missing-output classification, completed-open row-key allowlists, and completed-manifest backfill dry-run behavior |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*completed*.py" -q
```

---

### Rename

Tests for TV and movie name parsing, rename planning, discovery, apply, preview, and runner logic.

| Test file | What it covers |
|---|---|
| `test_service_rename_utils.py` | Shared rename utilities |
| `test_application_facade_rename.py` | Application-facade rename preview/apply command behavior, confirmation guard, selected-source scope, multi-select handling, and apply-lock guarding |
| `test_application_facade_local_api.py` | Local API rename browse command-result payload with injected path picker, route effect contract, and absent/false apply-confirmation rejection without rename mutation |
| `test_api_path_dialogs.py` | Windows rename path-dialog host selection, encoded PowerShell invocation, selected-path payload parsing, missing-host reporting, and process-failure diagnostics |
| `test_service_rename_movie.py` | Movie name parsing and scrub |
| `test_service_rename_tv.py` | TV name parsing and episode detection |
| `test_service_rename_tv_folder.py` | TV folder-level rename handling |
| `test_service_rename_discovery.py` | Source file discovery for rename |
| `test_service_rename_plan_policy.py` | Rename plan policy rules |
| `test_service_rename_planner.py` | Rename planning orchestration, Protocol-typed rename planning service boundary, and service-layer duplicate-destination blocking for every colliding row |
| `test_service_rename_preview.py` | Preview generation |
| `test_service_rename_preview_runner.py` | Preview runner and Protocol-typed naming-preview service boundary |
| `test_service_rename_apply.py` | Apply logic and transactional rename |
| `test_service_rename_apply_runner.py` | Apply runner and Protocol-typed apply/rollback service boundary |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*rename*.py" -q
& $py -m unittest DesktopApp.tests.test_api_path_dialogs -q
```

Coverage gap noted in `Docs/inventories/RENAME_SAFETY_TEST_INVENTORY.md`: native dialog display in real interactive Windows shell, undo manifest verification, and network path-rewrite behavior.

---

### Pending Publish

Tests for manifest parsing, path resolution, manifest row validation, and general service behavior.

| Test file | What it covers |
|---|---|
| `test_service_pending_publish_format.py` | Manifest format and parsing |
| `test_service_pending_publish_paths.py` | Path resolution from manifests |
| `test_service_pending_publish_manifest.py` | Manifest state validation |
| `test_service_pending_publish_manifest_rows.py` | Per-row manifest validation |
| `test_pending_publish_service.py` | General pending publish service |
| `test_application_facade_pending_publish.py` | Application-facade pending-publish preview classification, durable drain-summary evidence, publish reconciliation, row-key open allowlists, scan-failure surfacing, and recovery dry-run planning |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*pending_publish*.py" -q
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-PendingPublishOwnershipChecks.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-PendingPublishSafetyChecks.ps1
```

Remaining gaps noted in `Docs/inventories/PENDING_PUBLISH_FIXTURE_INVENTORY.md`: recovery-plan action coverage, completed-manifest/drain-summary cross-check depth, and coordinator-mode pending-publish handoff.

PowerShell ownership coverage now includes `Pipeline\Tests\Unit\Invoke-PendingPublishOwnershipChecks.ps1`, which parses the publish/pending modules and guards the documented parked-output-as-media-plus-sidecars ownership boundary.

---

### Audit and Rerun

Tests for audit record reading, CSV handling, I/O, metadata, and export.

| Test file | What it covers |
|---|---|
| `test_service_audit_rerun_records.py` | Audit record format |
| `test_service_audit_rerun_csv.py` | CSV read/write logic |
| `test_service_audit_rerun_io.py` | Audit I/O operations |
| `test_service_audit_rerun_metadata.py` | Metadata reading and Protocol-typed rerun metadata service boundary |
| `test_service_audit_rerun_export.py` | Export logic and Protocol-typed rerun CSV export service boundary |
| `test_service_failure_markers.py` | Failure marker read/write |
| `test_service_failure_retry_state.py` | Failure retry-state contract from failure rows/markers, including transient next-queue-pass retries and blocked operator/permanent/exhausted rows |
| `test_facade_audit_policy.py` | Facade: audit policy |
| `test_facade_failures_policy.py` | Facade: failures policy and retry-state child payload |
| `test_application_facade_reports.py` | Application-facade read-only failure JSON/marker preview, retry-state payload, and audit CSV preview behavior |
| `Pipeline/Tests/Unit/Invoke-PortablePathChecks.ps1` | PowerShell audit/legacy GUI parser and portable audit-root default guard |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*audit*.py" -q
& $py -m unittest DesktopApp.tests.test_service_failure_markers -q
& $py -m unittest DesktopApp.tests.test_service_failure_retry_state -q
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-PortablePathChecks.ps1
```

---

### Settings

Tests for settings validation, patch preview, save, and facade policies.

| Test file | What it covers |
|---|---|
| `test_facade_settings_policy.py` | Facade: settings workspace policy |
| `test_facade_settings_patch_policy.py` | Facade: settings patch/save policy |
| `test_application_facade_settings_workspace.py` | Application-facade Settings workspace redaction, metadata, media-policy readiness, tool-path evidence, and Validate command-result envelope |
| `test_application_facade_settings_patch.py` | Application-facade Settings Preview Patch/Save Patch command behavior, redacted diff fallback logging, risk summaries, save-lock guarding, backup/secret preservation, and no-op same-value handling |
| `test_settings_risk_policy_rules.py` | Settings risk classification plus clean template source-safety defaults |
| `test_facade_maintenance_policy.py` | Facade: maintenance policy |
| `test_facade_maintenance_command_policy.py` | Facade: maintenance command policy |
| `test_application_facade_maintenance.py` | Application-facade Maintenance workspace environment-health rows, Release Package dry-run plan/progress behavior, and maintenance command-lock fail-closed behavior |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test_facade_settings*.py" -q
```

---

### Folder Policy

Tests for folder validation contracts, probing, and I/O.

| Test file | What it covers |
|---|---|
| `test_service_folder_policy_contracts.py` | Folder policy contract rules |
| `test_service_folder_policy_probe.py` | Folder probe logic |
| `test_service_folder_policy_io.py` | Folder I/O helpers |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*folder_policy*.py" -q
```

---

### Paths and Files

Tests for path normalization, layout, state migration, defaults, and resolution runners.

| Test file | What it covers |
|---|---|
| `test_service_paths.py` | General path service |
| `test_service_path_layout.py` | Path layout resolution |
| `test_service_path_state_migration.py` | Legacy state migration and Protocol-typed app-state migration service boundary |
| `test_service_path_defaults.py` | Default path computation |
| `test_service_path_host_runner.py` | Host path runner and Protocol-typed PowerShell host service boundary |
| `test_service_path_resolution_runner.py` | Path resolution runner and Protocol-typed resolved-path service boundary |
| `test_service_file_open_plan.py` | File open plan construction |
| `test_service_file_open.py` | File open service |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*path*.py" -q
```

---

### Network Mode

Tests for coordinator/worker state, persistence, auth, source policy, mDNS, local IP detection, and WebView network boundary rules.

| Test file | What it covers |
|---|---|
| `test_network_security.py` | Network auth/token handling, coordinator request caps, worker identity validation, URL validation, registry ownership rejection, bounded worker HTTP reads, and log sanitization |
| `test_network_workflow.py` | Workflow enhancement regressions for local claim/release resilience, heartbeat and done/release HTTP outcomes, queue-removal scheduling, coordinator hardening, cluster-log formatting, retry hints, and worker wait policy |
| `test_network_worker_runtime.py` | Worker runtime and resilience coverage for diagnostics bounds, daemon-thread failures, source path mapping, status callbacks, cluster-log posting, poll-loop handoff, heartbeat failures, malformed claims, reclaimed jobs, and claim handoff diagnostics |
| `test_network_coordinator_helpers.py` | Coordinator URL/share-block helpers, coordinator/worker auth probes, coordinator HTTP helper validation, coordinator policy coercion, encode-config snapshot delegation, and prior-failure policy |
| `test_network_coordinator_http.py` | Bounded HTTP JSON helpers, coordinator JSON response and OPTIONS handling, coordinator request-body and identifier rejection, heartbeat/done registry failures, `/api/log` sanitization, and HTTP error previews |
| `test_network_protocol_runtime.py` | Protocol non-finite validation, in-flight registry runtime snapshot sanitization, reclaimed heartbeat handling, worker claim-record handoff, done-request builders, and worker poll policy |
| `test_network_firewall.py` | Firewall rule parsing, add-rule command construction, bounded `netsh` subprocess checks, nonzero/admin warning messages, and firewall output surfacing |
| `test_network_worker_state.py` | Worker-state atomic writes, job identity and pending done-report round trips, save-failure operator visibility, non-finite JSON rejection, temporary cleanup diagnostics, and guarded cleanup context |
| `test_network_inflight_registry.py` | In-flight registry persistence, concurrent save safety, registry save-failure diagnostics, non-finite value sanitization, config JSON rejection, and malformed row loading |
| `test_network_crash_recovery.py` | Worker crash recovery, pending done-report retry, bounded failure diagnostics, malformed worker-state handling, cluster-log failure handling, and accepted-report cleanup failures |
| `test_network_done_release.py` | Worker done/release reporting, pending done-report save failure handling, accepted-report cleanup, bounded diagnostics, unstartable-claim release reporting, and `DoneRequest` terminal fields |
| `test_network_coordinator_startup.py` | Coordinator startup behavior |
| `test_network_coordinator_source_policy.py` | Coordinator source policy and path handling |
| `test_network_worker_source_policy.py` | Worker source policy, path handling, and worker poll interval handoff through the named config key plus shared policy helper |
| `test_network_local_ip.py` | Local IP selection helpers |
| `test_network_mdns.py` | mDNS registration/discovery helpers |
| `test_network_view_source_policy.py` | Network view source policy presentation |
| `test_application_facade_network.py` | Application-facade read-only Network worker-state metadata, progress bars, backend-authored heartbeat age, state-file evidence, and lifecycle-control absence |
| `test_webview_network_read_only_boundary.py` | Rendered Workers page read-only boundary, diagnostics-open-only buttons, design-only lifecycle contract display reference, and route-effect checks |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test_network*.py" -q
& $py -m unittest DesktopApp.tests.test_api_contract_payload DesktopApp.tests.test_application_facade_network DesktopApp.tests.test_webview_network_read_only_boundary -q
```

---

### Local API and Contracts

Tests for API route payloads, command payloads, handler dispatch, command journal, static file serving, HTTP helpers, and backend bootstrap.

| Test file | What it covers |
|---|---|
| `test_api_read_payloads_policy.py` | Read route payload shapes |
| `test_api_command_results_policy.py` | Command route result payload handling |
| `test_api_contract_payload.py` | Route contract payload, auth/effect classification, effectful POST command-result history contract, Network lifecycle design-only dry-run/rollback/source-policy/exposure contracts, repair/reconcile design-only dry-run/rollback/source-policy/exposure contracts, and CSV rerun copy/keep/park defaults |
| `test_api_command_journal_policy.py` | Command journal recording policy |
| `test_api_handler_policy.py` | Handler dispatch policy |
| `test_api_static_files_policy.py` | Static file serving policy, WebView include expansion for shell/Home/Telemetry/Queue/Completed/Pending/Rename/Launch/Reports/Schedule/Maintenance/Workers/Diagnostics/Settings partials, rendered bootstrap replacement, and unsafe include rejection |
| `test_api_path_dialogs.py` | Windows path-dialog helper behavior for Rename browse host resolution, command invocation, JSON payload parsing, and failure diagnostics |
| `test_api_http_helpers.py` | HTTP helper utilities |
| `test_backend_bootstrap.py` | Backend startup and token bootstrap |
| `test_application_facade_core_contracts.py` | Command-result serialization, runtime outcome normalization/indexing, command journal bounded persistence and strict JSON cleanup, Local API HTTP helper guards, static bootstrap/asset helper behavior, and route-map coverage against the documented contract |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test_api*.py" -q
& $py -m unittest DesktopApp.tests.test_backend_bootstrap -q
```

---

### Desktop Controllers

Tests for historical legacy desktop-shell controller boundaries, controller-owned UI state, status server helpers, queue/report/dashboard rendering, worker job reporting, process lifecycle orchestration, and controller failure logging.

| Test file | What it covers |
|---|---|
| `test_controllers_pipeline.py` | Pause/stop/rescan flag command-surface handling and sleep-second parsing |
| `test_controllers_notification.py` | Background completion/failure notification dispatch, test toast delivery, Windows notification failure logging, and focus-check failure logging |
| `test_controllers_telemetry.py` | Telemetry dashboard non-finite CPU/GPU/RAM display sanitization and ffmpeg GPU-note rendering |
| `test_controllers_status_presentation.py` | Topbar chip/window title/taskbar/command-bar updates, audit current-file formatting, and taskbar progress failure logging |
| `test_controllers_home.py` | Home dashboard idle-state rendering, pending-publish summary/timing, pending payload stat failure logging, and live queue overview/selection |
| `test_controllers_diagnostics.py` | Historical diagnostics log-search reset failure logging and current-match reset failure logging under the removed legacy desktop-shell shim |
| `test_controllers_process_lifecycle.py` | Completed pipeline/audit handle synchronization, shutdown cleanup failure logging, pipeline/audit launch prep, schedule-window launch state, and kill-and-quit cleanup |
| `test_controllers_worker_jobs.py` | Worker completion event matching, fail-closed completion reports, malformed event skipping, dispatcher completion reporting, single-file launch failure handling, start UI failure handling, and worker abort/reclaim kill coverage |
| `test_controllers_network.py` | Coordinator status notice rendering, coordinator notice failure logging, coordinator button update failure logging, dispatcher error/shutdown failure logging, and worker status post failure logging |
| `test_controllers_navigation.py` | View routing/refresh/sidebar behavior, Network tab lifecycle failure logging, sidebar badge rendering, shortcut overlay guards, global shortcut bindings, filter trace/sort-heading/detail-copy wiring, and detail-copy failure logging |
| `test_controllers_queue.py` | Queue filtering/quick views, selection/detail rendering, thumbnail lookup/failure handling, priority staging/menus/marker application/commit behavior, refresh progress/watchdog behavior including backend scan-detail label updates, drag reordering, tree rendering/active-row selection, remaining-record context, ETA/preview health text, and queue file open/copy/export actions |
| `test_controllers_feedback.py` | Action-status toast display, previous-toast cancellation, auto-dismiss scheduling, toast dismissal, recent-action recording, and recent-action text propagation |
| `test_controllers_worker_board.py` | Live worker-board snapshot row rendering, stale-row cleanup logging, snapshot failure fail-closed behavior, missing-worker-id logging, and per-row render failure isolation |
| `test_controllers_audit.py` | Audit report filtering/detail rendering, duplicate index behavior, multi-selection summaries, quick-view filters, context menu behavior, CSV apply/report metadata handling, creation-time failure logging, selected-row copy/open/priority actions, and selected/filtered CSV export |
| `test_controllers_failure.py` | Failure report filtering/detail/trend rendering, filter reset behavior, JSON/marker/clear-result application, selected-source open/copy/priority/audit-match actions, context menu behavior, and selected-failure re-run prioritization |
| `test_controllers_completed.py` | Completed-tree sorting/tags/detail rendering, CPU fallback encoder display, route breakdown chart updates, encode-speed history read/write/migration behavior under `LocalBase\State\App`, refresh/backfill busy-state disabling, and backfill result handling |
| `test_controllers_settings.py` | Settings profile save/load, list/path helper behavior, dirty-state and structured-control toggles, structured-control failure logging, unsaved-start prompt handling, config form validation/preview, missing saved-config diff logging, and save-in-place reload behavior |
| `test_controllers_file_actions.py` | Resolved log/local-base/report/config open handoffs, latest failure/audit CSV lookups, loaded audit CSV handoff, and empty path warning behavior |
| `test_controllers_maintenance.py` | Progress-file skeleton reset, resolved progress-path updates, reset action/status recording, confirmation dialogs, environment-health background dispatch, and environment-health result formatting |
| `test_controllers_folder_policy.py` | Folder-policy validation result status text, action-status text, command history action recording, success info dialog, and error/warning detail dialog formatting |
| `test_controllers_release.py` | Release package success status/action handling, manifest and zip path storage, manifest summary output formatting, and timeout output without success action recording |
| `test_controllers_pending_publish.py` | Pending-publish dashboard summary application, missing parked payload detail text, tree row tags, default selection/focus/scroll behavior, and manifest/sidecar detail rendering |
| `test_controllers_rerun.py` | Rerun CSV preview handling for disabled rows, unsafe policy overrides, duplicate planned output hints, status text, preview text, and failed nested-pipeline root-cause action history |
| `test_controllers_work_guard.py` | Work-guard active progress detection, stop-request handling, and related-process block messaging |
| `test_controllers_app_state.py` | App-state controller persistence, widget failure logging, refresh-state snapshot/autoload, polling completed-manifest refresh, and apply-snapshot-to-UI behavior |
| `test_controllers_status_server.py` | Status-server path redaction, shutdown-failure logging, pause-flag read-failure logging, and non-finite telemetry JSON safety |
| `test_controllers.py` | Controller helper import-boundary regression coverage for split helper modules |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test_controllers*.py" -q
```

---

### Facade and Schedule

General facade policy and desktop shell bootstrap tests not covered by subsystem-specific groups.

| Test file | What it covers |
|---|---|
| `test_app_bootstrap.py` | Historical app bootstrap state/controller setup and static legacy launcher fallback contract |
| `test_application_facade.py` | Shared fixture/helper module for split application-facade tests; intentionally owns no direct tests |
| `test_application_public_api.py` | Application facade/DTO public API boundary: package-level exports, per-module literal `__all__` declarations, export uniqueness/completeness, and declared export importability |
| `test_application_facade_close_readiness.py` | Application-facade close-readiness fail-closed behavior for active/unknown runtime state, fresh progress, progress read failures, ActiveJobs, schedule-stop watcher, and related-process inspection failures |
| `test_application_facade_completed.py` | Application-facade completed/output preview evidence, validation-state child payload, size/runtime/missing-output classification, completed-open row-key allowlists, and completed-manifest backfill dry-run behavior |
| `test_application_facade_core_contracts.py` | Application-facade core contract helpers: command-result serialization, runtime outcome normalization, command journal bounds, strict JSON guards, Local API HTTP helper guards, static bootstrap/asset helpers, and route-map coverage |
| `test_application_facade_diagnostics.py` | Application-facade diagnostics allowlists, read-only state-summary artifact evidence, blocked BDPGS OCR path surfacing, and diagnostics path lookup failure logging |
| `test_application_facade_local_api.py` | Local API server auth/public-token boundaries, route contracts, design-only Network lifecycle contract payload, diagnostics allowlists, queue state routes/source scope/journaling, completed validation-state payload exposure, rename apply confirmation rejection without mutation, launch preflight nested readiness DTO exposure, process/schedule/shutdown lifecycle behavior, backend shutdown cleanup/logging, layout-manager schema-reset/gated-drag static asset coverage, and broad workflow contract coverage |
| `test_application_facade_maintenance.py` | Application-facade Maintenance workspace environment-health rows, toolchain evidence/progress rows, Release Package dry-run plan/progress behavior, and maintenance command-lock fail-closed behavior |
| `test_application_facade_network.py` | Application-facade Network worker-state metadata, progress bars, backend-authored heartbeat age, state-file evidence, and lifecycle-control absence for `/api/network/workers` |
| `test_application_facade_pending_publish.py` | Application-facade pending-publish preview classification, durable drain-summary evidence, publish reconciliation, row-key open allowlists, scan-failure surfacing, and backend-authored recovery dry-run planning |
| `test_application_facade_process_control.py` | Application-facade pipeline control flag contract, invalid action rejection, and control-lock fail-closed behavior |
| `test_application_facade_process_launch.py` | Application-facade pipeline/audit/rerun launch handoff, duplicate pipeline launch rejection while a prior child process is still running, launch-lock fail-closed behavior, schedule-gated launch handling, schedule-stop watcher preservation, read-only launch preflight guard coverage, and backend-authored Launch readiness DTO coverage |
| `test_application_facade_queue.py` | Application-facade queue preview snapshot-read behavior, stale evidence, blocked-vs-excluded rows, runtime outcome correlation, and row-key open allowlists |
| `test_application_facade_rename.py` | Application-facade rename preview/apply command behavior, selected-source scoping, multiple-selection handling, undo-manifest cleanup in temp fixtures, and apply-lock guarding |
| `test_application_facade_reports.py` | Application-facade Reports behavior for failure JSON, failure markers, marker-clear confirmation handoff, and audit CSV rows |
| `test_application_facade_schedule.py` | Application-facade Schedule workspace rendering, backend watcher evidence, preview/save confirmation, app-state preservation, and invalid-time rejection |
| `test_application_facade_settings_patch.py` | Application-facade Settings Preview Patch/Save Patch behavior, risk summaries, redacted diff fallback, save-lock guard, backup/secret preservation, and no-op same-value handling |
| `test_application_facade_settings_workspace.py` | Application-facade Settings workspace redaction, path/field metadata, validation warning surfacing, backend media-policy readiness evidence, tool-path evidence, and Validate command-result envelope coverage |
| `test_application_facade_snapshot.py` | Application-facade snapshot assembly, progress bar shaping, active-job diagnostics rows, pending-publish copy byte progress, and zero-percent GPU telemetry presence |
| `test_application_facade_web_static.py` | Backend-served WebView/Tauri static integration, route references, command allowlists, Dashboard command-surface ownership, evidence/read-only panel guardrails, canonical rendered page H1 titles, Settings BDPGS OCR path builder/no-path-picker guard, Settings subtitle keyword list builder wiring, Completed validation-state checklist/proof copy, table selection/accessibility helpers, diagnostics handoff, state-aware Launch command controls, emergency topbar Force Stop posture, UI tooltip/error/telemetry guards, page-scoped IDs, and headless backend bootstrap payload coverage |
| `test_facade_schedule_policy.py` | Facade: schedule policy |
| `test_facade_status_policy.py` | Facade: status policy |
| `test_facade_diagnostics_open_policy.py` | Facade: diagnostics open policy |

---

### Release / Packaging

Tests for release plan construction and result validation.

| Test file | What it covers |
|---|---|
| `test_service_release_plan.py` | Release plan logic |
| `test_service_release_result.py` | Release result validation |

Targeted command:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test*release*.py" -q
```

---

### Tauri Shell and WebView (Non-Browser)

Static and scaffold tests for Tauri shell setup and WebView JS assets.

| Test file | What it covers |
|---|---|
| `test_tauri_shell_scaffold.py` | Tauri shell file layout, backend launch/bootstrap/contract/WebView asset gates, close-readiness shutdown boundary, backend lifecycle monitor wiring, per-user Windows single-instance guard, read-only WebView lifecycle bridge/banner, production-surface audit script presence, no direct pipeline/FFmpeg launch, no `Invoke-Expression` in wrappers, PS7 syntax |
| `test_webview_css_design_tokens.py` | WebView CSS design-token discipline, token/theme/layout/component/page/control/layout-manager/queue import split, layout-manager drag-hint selector ownership, focus/status-chip styling, and workflow-table/status-chip static wiring |
| `test_webview_inventory_docs.py` | Rendered DOM ID inventory drift, WebView global export inventory/manifest drift, and `window.mediaPipeline*` namespace object JSDoc boundary coverage |
| `test_webview_navigation_static.py` | WebView rendered HTML/JS asset structure, nav links, DOM ID uniqueness |
| `test_webview_frontend_mutation_boundary.py` | WebView `apiPost` call ownership, documented POST route usage, shell-open selector payloads, confirmation payloads, centralized fetch, no direct frontend filesystem/process/Tauri APIs except the event-only `tauriLifecycleBridge.js`, lifecycle bridge read-only assertions, frontend media-policy risk helpers labelled advisory-only, and repair/reconcile command-route exposure blocked while `/api/contract` remains design-only with dry-run/rollback/source-policy/exposure fields |
| `test_webview_network_read_only_boundary.py` | Rendered WebView Workers page read-only boundary, diagnostics-open-only buttons, no lifecycle controls, design-only lifecycle contract display reference, and `/api/network/workers` as the only network route |

Targeted command:

```powershell
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
& $py -m unittest DesktopApp.tests.test_webview_css_design_tokens -q
& $py -m unittest DesktopApp.tests.test_webview_inventory_docs -q
& $py -m unittest DesktopApp.tests.test_webview_navigation_static -q
& $py -m unittest DesktopApp.tests.test_webview_frontend_mutation_boundary -q
powershell -NoProfile -ExecutionPolicy Bypass -File DesktopApp\tauri_shell\Test-TauriShell-ProductionSurface.ps1
```

---

### WebView Browser-Backed Smokes

Browser-backed smoke tests under `DesktopApp\tests\`. Require Chrome or Edge; skip cleanly if absent.

| Test file | What it covers |
|---|---|
| `test_webview_browser_high_risk_smoke.py` | Blocked Queue, broken Completed, do-not-drain Pending rows under real browser |
| `test_webview_browser_schedule_smoke.py` | Schedule Editor preview/save routing, command-history ownership, Launch timing trust after refresh |
| `test_webview_browser_lifecycle_smoke.py` | Backend lifecycle and Close Readiness; watcher-armed shutdown blocked; safe shutdown via backend-owned route only |
| `test_webview_browser_diagnostics_handoff_smoke.py` | Table clicks, filter guardrails, diagnostics bridge/tail/open, owner-row navigation |
| `test_webview_browser_pending_drain_guard_smoke.py` | Publish Button Guard refresh, blocked drain does not POST |
| `test_webview_browser_completed_pending_proof_smoke.py` | Completed-to-Pending proof board, Completed Manifest correlation |
| `test_webview_browser_large_table_smoke.py` | 260-row render-cap disclosure, filter warnings, hidden selected-row detail, no mutation posts |
| `test_webview_browser_maintenance_reports_smoke.py` | Maintenance health/dry-run result rendering, Reports triage, retry-state display, read-only Launch/Diagnostics handoff |
| `test_webview_browser_sample_validation_smoke.py` | Home sample-validation pilot/readiness/reconciliation, worksheet detail, preview-only backend route |
| `test_webview_browser_home_live_state_smoke.py` | Home Daily-Driver, Operator Readiness, active work, command history, live progress evidence, page-switch viewport reset |
| `test_webview_browser_launch_queue_readiness_smoke.py` | Launch/Queue/Schedule readiness, scope reconciliation, sample proof handoff, no POSTs |
| `test_webview_browser_layout_manager_smoke.py` | Layout Editor drawer coverage across page tabs, subtabs, and generated subsections with no mutation posts |
| `test_webview_browser_rename_smoke.py` | Rename row click, Apply Readiness, duplicate-target blocking does not call apply |
| `test_webview_browser_network_smoke.py` | Read-only Network worker visibility and filter guardrails |
| `test_webview_browser_telemetry_smoke.py` | Idle NVENC at 0%, GPU detail rows, CPU/RAM-only fallback |
| `test_webview_browser_settings_launch_smoke.py` | Staged settings patch handoff, Settings-to-Launch intent, save-patch not called |

Run all via:

```powershell
& $py -m unittest discover -s DesktopApp\tests -p "test_webview_browser_*.py" -q
```

Use `SmokeTests/` wrappers for the operator-friendly path: `.\SmokeTests\Test-WebViewBrowser*.ps1`.

---

### WebView Non-Browser Smokes

Node.js-backed smoke tests that evaluate WebView JS with mocked DOM state.

| Test file | What it covers |
|---|---|
| `test_webview_command_evidence_smoke.py` | Shared command owner/issue evidence across all page histories |
| `test_webview_row_detail_smoke.py` | Queue, Completed, Pending selected-row detail rendering, including Completed validation-state proof-gap copy |
| `test_webview_rename_readiness_smoke.py` | Apply Readiness for ready and blocked duplicate-target scopes |
| `test_webview_real_media_smoke.py` | Fixture-backed backend API + WebView asset agreement for one TV sample |

Run via `SmokeTests/` wrappers: `.\SmokeTests\Test-WebViewCommandEvidenceSmoke.ps1`, `.\SmokeTests\Test-WebViewRowDetailSmoke.ps1`, etc.

---

## Known Coverage Gaps

| Area | Gap | Priority |
|---|---|---|
| Rename | Duplicate-destination at service layer; `confirm_apply: false` rejection; undo manifest verification | Medium |
| Pending Publish | Parked state coverage; drain summary cross-check; drain execution end-to-end | Medium |
| Process lifecycle | Adversarial duplicate-launch guard test | Medium |
| Real-media routing | No automated test covers FFmpeg encode/remux correctness on real files | High (needs real-media playbook) |
| Subtitle conversion | No automated test converts a real TX3G/BDPGS file | High (needs real-media playbook) |

Coverage gaps are tracked as documentation observations. They do not require immediate code changes.

---

## See Also

- Rename safety inventory: `Docs/inventories/RENAME_SAFETY_TEST_INVENTORY.md`
- Pending publish fixture inventory: `Docs/inventories/PENDING_PUBLISH_FIXTURE_INVENTORY.md`
- Validation ladder: `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- Browser smoke runbook: `Docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`

