# 2026-07-19 Production Audit Reconciliation

## Scope and evidence rule

This worker reconciled the 2026-07-19 comprehensive production audit against current HEAD `039658158d8439a868eff3c8c37e314845e9e22a` and the current working-tree overlay. The historical comparison point is `a8bf6e1dda9629e6f818ba12f2c8274362923372`.

The three settings findings `CSW-2026-07-09-SETTINGS-001`, `-002`, and `-003` were excluded for the coordinator. The five worker-10 workflow paths and `repository_audit_ledger.py` plus its focused test were also excluded. No historical status was inherited: each remaining ID was checked against current file bytes, the generated summary when present, exact current source/test lines, and focused execution where it materially changed the disposition.

The byte comparison covered all 45 unique paths named by the 16 in-scope findings. “Unchanged” below means current bytes and the Git blob are identical to the historical baseline; “changed” means the current exact source was reviewed rather than assuming the change fixed the issue.

## Result

| Finding | Baseline comparison | Current classification | Current proof |
| --- | --- | --- | --- |
| `CSW-2026-07-09-SCHEDULE-001` | Both named files unchanged | **Still present** | `manager.py:123-142`, `230-235`, and `417-444` keep baseline, tracker, and pending intent in process memory and rebase an existing candidate on a fresh manager. No restart persistence/load path or restart-inside-debounce regression exists. |
| `CSW-2026-07-09-MAINTENANCE-002` | All three named files unchanged | **Still present** | WebView copy at `releaseCommands.js:409-425` says checkpoints are not rewritten, while `backfill_facade.py:34-40,56-60` intentionally creates and returns an external RunLogs checkpoint. The focused PowerShell check passed and required that checkpoint. |
| `CPA-2026-07-19-001` | All five named paths changed | **Fixed; current generated artifact drift detected separately** | The generator now discovers 25 wrappers, 34 modules, and 9 direct-only modules and validates prose count claims. Seven behavior tests passed. The canonical `--check` and the renderer-equality test currently fail on changed line-number metadata in two other inventory docs, demonstrating that drift is no longer false-green; the original stale-count detection gap is closed. |
| `CPA-2026-07-19-002` | All three named paths changed | **Still present** | Callers pass the heartbeat at `media_probe_streams.ps1:497-498` and `encode_verification.ps1:124-130`, but `Get-SourceHdr10MasteringMetadata` still declares only `FilePath` at `media_probe_hdr.ps1:103` and uses unbound poll variables at line 110. A current no-write mock captured a null handler and null interval after supplying a handler and `777`. |
| `CPA-2026-07-19-003` | `scratch_copy.ps1` changed; `source_identity.ps1` unchanged | **Fixed** | Scratch evidence is now `scratch_source_identity.v2` with recomputed SHA-256 identities (`scratch_copy.ps1:11-15,22-100,290-316,407-449,454-529`). The focused adversarial matrix passed 15/15, including same-path/same-size/same-mtime replacement, source change during copy, forged/legacy evidence, collision, restart, and locked stale scratch, with source hashes preserved. Representative real-media release proof remains a release gate, not evidence that this root cause remains present. |
| `CPA-2026-07-19-004` | Shell guard, `lib.rs`, and lifecycle doc unchanged; `local_api_main.py` changed; backend guard/test are new current paths | **Needs native runtime proof** | `backend_instance.py` now owns a backend-process mutex/lock through listening and cleanup, and `local_api_main.py:447-462,500,577-595` acquires/releases it around the backend lifetime. Five focused tests passed, including simulated shell hard crash, backend crash, stale metadata, and cleanup race. The required packaged Windows hard-crash/relaunch census was not run, so this is not claimed terminally fixed for release. |
| `CPA-2026-07-19-005` | All four named paths changed | **Fixed** | `commands_process.py:271-300,314-377` treats missing, false, malformed, or exceptional cleanup evidence and unsafe post-cleanup readiness as failure, does not schedule shutdown on error, and returns `backend_shutdown_cleanup_failure_payload` (`command_results.py:265-301`). All 13 lifecycle tests passed, including exception, false result, journal uncertainty, and unsafe post-cleanup cases. |
| `CPA-2026-07-19-006` | Named Rust source changed | **Fixed** | `backend_process.rs:64-80,229-308` propagates `try_wait` errors into `ChildExitWait::Failed`, returns failed shutdown, and retains ownership. The focused Rust module ran 18 tests with zero failures, including both wait-error shutdown paths and crash-monitor propagation. |
| `CSW-2026-07-09-HOME-003` | Normalizer and `app.js` unchanged; refresh/lifecycle/topbar changed for other work | **Still present** | `renderCloseReadiness` normalizes its own cache, but refresh fan-out still passes raw `values["close readiness"]` at `refreshCoordinator.js:352-375,397-403`. `lifecycle.js:127-129,188-192,303` and `topbar.js:384-391` truth-test the raw field. The newly added contract smoke itself fails broadly; it does not exercise or repair the refresh boundary. |
| `CSW-2026-07-09-TELEMETRY-004` | Named file unchanged | **Still present** | `barState.js:151-163` rewrites the first backend `stale=true` sample to `stale=false` and changes warning to active until a second sample, so current backend evidence is knowingly displayed as fresh. |
| `CPA-2026-07-19-007` | `failure_records.ps1` unchanged; registry/state files changed for unrelated additions | **Still present** | BDPGS and VobSub families remain unconditionally transient at `failure_records.ps1:133-164`; retry escalation remains at `failure_state.ps1:753-769`; `failure_codes.ps1:336-358` still defaults the prerequisite codes to retryable. A current registry query returned `Retryable=true` for all nine persistent prerequisite codes. |
| `CPA-2026-07-19-008` | Builder matrix unchanged; ownership map changed but retained stale totals | **Still present** | Current authoritative counts are 206 backend keys, 156 bindings, 146 unique keys, 10 duplicates, and 60 missing. The builder matrix reports 205/156/146/10/59 and also says 155 bindings later; the ownership map reports 204/155/145/10/59. No enforcing settings-inventory freshness check was found. |
| `CSW-2026-07-09-PENDING-003` | All three named files unchanged | **Still present** | Ordinary orphan discovery at `pending_paths.py:35-57` emits no proposal; `dry_run_pending.py:223-239` only consumes proposal fields; the WebView enables dry-run from a selected key alone at `pendingPublishView.repair.js:233-255`. The safe consumer still has no production proposal producer. |
| `CSW-2026-07-09-RENAME-004` | Both named files unchanged | **Still present** | `renameHistoryView.js:29-33` replays the newest apply through the state-mutating result renderer; `commandEvidence.js:143-161` restores the apply manifest and unconditionally clears `lastUndoCompleted`, despite successful undo setting it true at `213-238`. |
| `CSW-2026-07-09-NETWORK-001` | All three named files unchanged | **Still present** | `facade.py:241-261` preflights a shorter placeholder, then `_coordinator_join_token` mutates token authority before final exact-token encoding. `join.py:92-103` enforces the 32-KiB decoded size and `auth.py` generates the longer 64-hex token. No compensation surrounds final encode failure. |
| `CSW-2026-07-09-NETWORK-003` | All three named files unchanged | **Still present** | `facade.py:224-299` reads role only for response metadata; it never gates creation. The route contract has no role precondition, and `lifecycle.view.js:199-219` enables creation from route availability rather than configured role authority. |

## Fixed IDs and proof boundary

- `CPA-2026-07-19-001`: stale wrapper/module/direct-only count claims are now executable inputs to the generator. Current line-number drift makes the check red instead of silently green.
- `CPA-2026-07-19-003`: exact content identity now authorizes reuse; 15 adversarial scratch cases passed with unchanged-source hash evidence.
- `CPA-2026-07-19-005`: forced shutdown is not acknowledged and the shutdown callback is not scheduled when cleanup cannot be verified; 13 focused lifecycle tests passed.
- `CPA-2026-07-19-006`: child wait errors are no longer treated as exit; 18 focused Rust tests passed.
- `CPA-2026-07-19-004` is deliberately not in the fixed list: the source-level backend-owned singleton and five tests are credible, but the original native packaged hard-crash/relaunch proof is still absent.

## Root-cause deduplication

- `CPA-2026-07-19-001` and `CPA-2026-07-19-008` share an inventory-drift theme but not the same current defect: the smoke inventory now has an enforcing generator, while the settings inventories remain manually stale and unenforced.
- `CPA-2026-07-19-004`, `-005`, and `-006` are separate lifecycle failure boundaries: cross-process singleton ownership, backend forced-cleanup acknowledgement, and Rust child-exit verification respectively.
- `CSW-2026-07-09-HOME-003` and `CSW-2026-07-09-TELEMETRY-004` are separate frontend evidence defects: raw contract normalization bypass versus intentional stale-state hysteresis.
- `CSW-2026-07-09-NETWORK-001` and `-003` are not duplicates: one is token-rotation transaction ordering; the other is missing configured-role authorization.
- `CSW-2026-07-09-SCHEDULE-001` remains independent of the backend singleton remediation: preventing a second backend does not persist a watch candidate across a legitimate backend restart.

## Validation executed

- Backend singleton ownership: 5/5 Python tests passed.
- Forced-shutdown lifecycle: 13/13 Python tests passed; expected injected cleanup exceptions were logged by the passing tests.
- Rust backend-process lifecycle: 18/18 tests passed.
- Scratch identity: 15/15 PowerShell adversarial cases passed with source hash proofs.
- Maintenance backfill dry-run: passed and showed the intentional external checkpoint.
- HDR heartbeat no-write mock: reproduced null handler/null interval.
- Subtitle registry query: all nine persistent prerequisite codes remained retryable.
- Settings count reproduction: `206/156/146/10/60`.
- Close-readiness contract smoke: failed, corroborating the still-open fail-closed normalization gap.
- Smoke map `--check` and renderer-equality test: failed only on current line-number drift in other inventory documents; seven behavioral generator tests passed.

No source media, production settings, queue state, pending-publish state, network token authority, or runtime process lifecycle was mutated by this reconciliation.
