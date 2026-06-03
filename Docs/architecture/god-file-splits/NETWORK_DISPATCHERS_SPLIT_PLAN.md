# Network Dispatchers Split Plan

Date: 2026-06-03

## Scope

Target files:

- `DesktopApp/mediapipeline_desktop_app/network/worker.py`
- `DesktopApp/mediapipeline_desktop_app/network/coordinator.py`

Current audit signal:

- `worker.py`: 1,107 lines, one `WorkerDispatcher` class owning HTTP, state,
  polling, heartbeat, claim, done, release, and shutdown behavior.
- `coordinator.py`: 1,389 lines, one `CoordinatorDispatcher` class owning auth,
  HTTP server handlers, queue claim/done/release, worker snapshots, reaper, mDNS,
  state restoration, and shutdown behavior.

Network lifecycle controls remain intentionally absent from the WebView. This
split must not add coordinator/worker start, stop, retry, reclaim, release,
abort, settings-save, queue, publish, rename, state-write, or media mutation
routes.

## Placement

Use focused modules under the existing package:

- `DesktopApp/mediapipeline_desktop_app/network/`

Do not move this implementation into `app/` unless a separate architecture pass
changes ownership boundaries.

## Proposed Worker Slices

1. `worker_http.py`
   - Move headers/signing plus HTTP GET/POST helpers.
   - Candidate methods: `_headers`, `_sign_request`, `_http_get`, and
     `_http_post`.

2. `worker_state.py`
   - Move crash recovery and persisted worker/pending-done state helpers.
   - Candidate methods: `_crash_recover`, `_save_worker_state`,
     `_save_pending_done_report`, `_clear_worker_state`, and
     `_clear_worker_state_after_accepted_report`.

3. `worker_claims.py`
   - Move claim, done, release, malformed claim response, and release identity
     helpers.
   - Candidate methods: `_request_abort_reclaimed_job`,
     `_release_unstartable_claim`, `_release_claim_identity`,
     `_release_malformed_claim_response`, `_on_job_claimed`, `_do_release`,
     `claim_next`, `mark_done`, and `release`.

4. `worker_loops.py`
   - Move polling, wait, wakeup, heartbeat, stop heartbeat, and shutdown loop
     helpers.
   - Candidate methods: `wakeup`, `_resolve_wait_seconds`,
     `_wait_interruptible`, `_poll_loop`, `_heartbeat_loop`,
     `_stop_heartbeat`, and `shutdown`.

## Proposed Coordinator Slices

1. `coordinator_auth.py`
   - Move token generation, token updates, and request auth validation.
   - Candidate methods: `_load_or_generate_token`, `_validate_request_auth`,
     `get_auth_token`, and `update_auth_token`.

2. `coordinator_state.py`
   - Move inflight state restoration/path helpers and cluster log helpers.
   - Candidate methods: `_restore_inflight_state`, `_inflight_state_path`,
     `cluster_log_path`, `_format_cluster_log_line`, `_append_cluster_log`,
     `log_cluster_event`, and `_safe_log_cluster_event`.

3. `coordinator_lifecycle.py`
   - Move HTTP server bootstrap, reaper, mDNS, shutdown, and worker snapshot
     helpers.
   - Candidate methods: `_start_http_server`, `_start_reaper`, `_start_mdns`,
     `_reaper_interval_seconds`, `_reaper_loop`, `shutdown`,
     `workers_snapshot`, `idle_workers_snapshot`, and `coordinator_stats`.

4. `coordinator_queue.py`
   - Move queue claim/done/release policy helpers.
   - Candidate methods: `claim_next`, `mark_done`, `release`,
     `_scan_for_next_record`, `_compute_retry_after_seconds`,
     `_source_has_prior_failure`, `_snapshot_encode_config`,
     `_remove_from_queue`, and `_emit_done_outcome`.

5. `coordinator_http_handlers.py`
   - Move request handlers after the internal helpers are split.
   - Candidate methods: `_http_claim`, `_http_done`, `_http_heartbeat`,
     `_http_workers`, and `_http_log`.

## Parent Responsibilities To Preserve

- `WorkerDispatcher` and `CoordinatorDispatcher` remain the public classes.
- Existing public methods and status callback behavior remain stable.
- Existing Local API network contracts remain read-only unless a separate
  lifecycle-command contract implementation is explicitly scoped.
- Runtime state files, command journal behavior, queue source policy, and media
  mutation boundaries must not change.

## Validation

After each worker slice:

```powershell
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_network_worker_runtime -q
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_network_worker_source_policy -q
```

After each coordinator slice:

```powershell
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_network_coordinator_http -q
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_network_runtime_state -q
```

Shared checks:

```powershell
.\DesktopApp\Runtime\Python\python.exe scripts\dev\check_dependency_boundaries.py
.\DesktopApp\Runtime\Python\python.exe scripts\dev\check_godfiles.py --paths DesktopApp/mediapipeline_desktop_app/network/worker.py DesktopApp/mediapipeline_desktop_app/network/coordinator.py
```
