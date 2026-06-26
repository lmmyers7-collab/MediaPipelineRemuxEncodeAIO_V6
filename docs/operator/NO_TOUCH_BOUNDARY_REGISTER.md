# No-Touch Boundary Register

Purpose: list areas that must not be casually edited during admin, WebView parity, or documentation work. Each entry explains why the boundary exists and what gate is required before touching it.

This register applies to all admin, documentation, and WebView frontend tasks. Engineering changes to these areas require separate planning, testing, and operator review.

---

## Historical Fallback Workspace

**What**: The older historical fallback workspace or any file path under it.

**Why**: The older historical fallback evidence must remain untouched. The external rollback workspace is the fallback for this current folder. Any change to older fallback evidence destroys the safety reference.

**Safe alternative**: Do active work in this current workspace. If an older reference doc needs updating, copy the relevant context into current documentation instead of editing that fallback.

**Gate before touching**: None acceptable. Historical fallback evidence must remain untouched.

---

## External Rollback Workspace

**What**: The external rollback/fallback workspace or any file path under it.

**Why**: The external rollback workspace is the active rollback safety net for this promoted current workspace.
Changing it during current-workspace work can destroy the operator's known fallback evidence and
make rollback behavior ambiguous.

**Safe alternative**: Do active work in this current workspace. If an external rollback behavior or note is needed,
copy the relevant context into current documentation instead of editing the external rollback workspace.

**Gate before touching**: Explicit operator approval, a real-media validation
plan, and an operator rollback decision.

---

## Removed Legacy Desktop-Shell Surface

**What**: removed legacy desktop-shell launchers, controllers, views, runtime package files, and any attempt to reintroduce them into this current folder.

**Why**: This workspace intentionally removed the legacy desktop-shell surface. The external rollback workspace remains the rollback/fallback workspace. Reintroducing partial legacy shell files into this workspace would create a misleading launcher path and split operator authority.

**Safe alternative**: Keep fallback work in the external rollback folder. In this workspace, validate WebView/Tauri behavior through the local API, smoke wrappers, validation ladder, and real-media pilot evidence.

**Gate before touching**: Explicit operator approval to restore a legacy desktop-shell surface to this workspace, plus a new architecture decision explaining why the WebView-first split direction changed.

---

## Media Policy (FFmpeg Command Generation)

**What**: `ops\pipeline\engine\*.ps1` code that generates FFmpeg arguments — video codec selection, quality/preset settings, container selection, stream copy/encode decisions. Do not recreate legacy `Pipeline\Modules\*.ps1` shim paths; active PowerShell implementation belongs under `ops\pipeline\engine\<domain>\`.

**Why**: FFmpeg arguments directly determine output quality, compatibility, and encode safety. A one-character typo can produce silent bitrate misconfiguration or stream corruption.

**Safe alternative**: Document the current behavior in `docs\`. Propose changes via a separate PR with a real-media test plan.

**Gate before touching**: PowerShell unit tests + reliability regression + tool integration checks + real-media validation on at least one encode and one remux sample.

---

## Subtitle Conversion Logic

**What**: TX3G → SRT conversion, BDPGS OCR (PgsToSrt), ASS/SSA drop/convert/preserve logic in pipeline modules.

**Why**: Subtitle handling is complex, format-specific, and operator-configuration-dependent. Silent drops or double-conversions are hard to detect without inspecting output files.

**Safe alternative**: Review config via `SubKeepLanguages`, `ConvertTx3gToSrt`, etc. in the Settings WebView builder. Document known behavior.

**Gate before touching**: Unit tests + real-media validation with subtitle-bearing samples (TX3G, BDPGS, ASS).

---

## Audio Routing Logic

**What**: Passthrough policy, transcode policy, channel cap, downmix mode, language preference resolution in pipeline modules.

**Why**: Audio policy determines whether direct-play audio tracks survive, get re-encoded, or get dropped. Silent errors here produce files that appear correct but require transcoding by Plex.

**Safe alternative**: Adjust `AudioPassthroughProfile`, `AudioTranscodeCodec`, `AudioMaxChannels` via the Settings WebView builder. Document expectations.

**Gate before touching**: Unit tests + real-media validation with multi-audio samples.

---

## Pending Publish Mutation Path

**What**: The drain execution path in `ops\pipeline\entrypoints\MediaPipeline.ps1` that moves parked outputs to their final destination via Robocopy, updates manifests, and writes the drain summary.

**Why**: Drain moves files. A bug here can result in files moved to wrong destinations, partial copies, or manifest corruption that blocks future drain operations.

**Safe alternative**: Use the WebView Pending Publish recovery dry-run and drain decision checklist. The drain command remains backend-owned.

**Gate before touching**: Unit tests + pending publish fixture tests + real-media validation of the deferred publish → drain lifecycle.

---

## Source File Deletion

**What**: Any code path that deletes or overwrites source media files.

**Why**: Source deletion is irreversible. The pipeline is designed to never delete source files under normal operation. Any new deletion path requires explicit operator confirmation and a documented rollback plan.

**Safe alternative**: Document the current no-delete invariant. Source cleanup (if ever needed) must be a separate, explicitly gated command.

**Gate before touching**: Full review by operator; explicit real-media pilot evidence per `docs/implementation/release-foundation/PHASE_6_REAL_MEDIA_PILOT.md`; separate test plan.

---

## Scratch-Copy Invariants

**What**: The scratch folder workflow — the pipeline copies the source to scratch, processes it there, then publishes the result.

**Why**: Scratch isolation prevents source corruption if encoding fails mid-stream. Breaking scratch invariants can expose source files to partial writes.

**Safe alternative**: Document the scratch path in `docs\inventories\RUNTIME_ARTIFACT_INVENTORY.md`. Adjust scratch path only via config.

**Gate before touching**: Pipeline unit tests + reliability regression + real-media validation.

---

## Command Journal

**What**: The backend-owned bounded FIFO command journal in the local API (`src\mediapipeline\desktop\api\command_journal.py` and `command_journal_policy.py`). Normal Local API launch also persists bounded summaries to `apps\desktop\runlogs\local_api_command_history.json` and mirrors entries to SQLite when a state root is available.

**Why**: The command journal is the source of truth for WebView Command History and Diagnostics. Deduplication behavior, success-status-only recording, and bounded FIFO are deliberate design choices. Changing them silently changes what the operator sees.

**Safe alternative**: Review the active API route inventory, command ownership matrix, command journal policy tests, and archived command-history audit before changing command evidence behavior. Document any new command types in the journal.

**Gate before touching**: Unit tests for command journal policy + WebView smoke for command evidence rendering.

---

## Close Readiness Logic

**What**: `GET /api/backend/close-readiness` implementation and the Tauri shell's response to it.

**Why**: If close readiness is reported safe when active processing is in progress, the operator may kill the pipeline mid-encode, causing partial outputs or manifest corruption.

**Safe alternative**: Observe close readiness in the WebView Home / Diagnostics panes. Document expected states.

**Gate before touching**: Process lifecycle tests + adversarial test: kill during active encode → confirm close-readiness returns unsafe.

---

## Strict JSON Handling

**What**: All backend routes that require `confirm_apply` (rename) or `confirm_save` (settings) as explicit boolean true values in the request body.

**Why**: These guards prevent accidental mutation from test scripts, browser dev tools, or frontend bugs that omit the confirmation field. Removing or relaxing them creates silent mutation risk.

**Safe alternative**: Always include `confirm_apply: true` for apply routes. For `settings/save-patch`, first call backend preview and include its matching `review_confirmation` with `confirm_save: true`. Document this in test files.

**Gate before touching**: Command contract review + unit tests for all confirmation-required routes.

---

## Duplicate-Command Guards

**What**: Launch-lock and in-progress guards that prevent a second pipeline start while one is already running.

**Why**: Two simultaneous pipeline processes operating on the same source and output paths will produce race conditions, file overwrites, and manifest corruption.

**Safe alternative**: Observe active-job state in the WebView Home. Issue `pipeline/control` stop before re-launching.

**Gate before touching**: Process lifecycle tests + manual test: launch twice, confirm second launch is rejected.

---

## Release Gates

**What**: `ops\scripts\release\test.ps1` assertions that a clean release does not include live config, run logs, state files, or optional tool bulk.

**Why**: If personal config ships in a release package, the recipient gets the operator's private UNC paths, credentials, and source/output locations.

**Safe alternative**: Use `ops\scripts\release\build.ps1` with default flags (strips live config, excludes logs/state). Use `-KeepPersonalConfig` only for private machine-to-machine mirror.

**Gate before touching**: Full release self-test with `-Verify -IncludeTests`.

---

## Network Lifecycle Controls

**What**: Coordinator and worker start/stop commands; these remain outside the WebView until backend-owned lifecycle routes are deliberately promoted.

**Why**: Network lifecycle controls have process-safety implications similar to pipeline start/stop. Premature or incorrect lifecycle calls can orphan workers or corrupt shared state.

**Safe alternative**: Use the WebView Network page for read-only worker-state visibility. Use the documented backend/manual network process workflow until lifecycle routes are designed, tested, and promoted.

**Gate before touching**: Network mode checklist review + explicit design for the new backend command contract.

---

## Summary Table

| Boundary | Why critical | Safe admin alternative | Gate |
|---|---|---|---|
| Older fallback evidence | Historical fallback evidence | Work only in current docs/code | None: never touch |
| External rollback workspace | Production operator safety net | Document WebView parity gaps | Real-media validation + operator decision |
| FFmpeg command generation | Encode correctness | Settings builder / config | PS unit + reliability + real-media |
| Subtitle conversion | Format-specific, silent errors | Settings builder | Unit + real-media with subtitle samples |
| Audio routing | Direct-play compatibility | Settings builder | Unit + real-media with audio samples |
| Pending publish drain | File movement, manifest integrity | Recovery dry-run + drain checklist | Unit + pending publish tests + real-media |
| Source deletion | Irreversible | Document no-delete invariant | Full review + explicit operator accept |
| Scratch invariants | Source corruption risk | Config path only | Unit + reliability + real-media |
| Command journal | Operator diagnostic trust | Document new command types | Unit + smoke for rendering |
| Close readiness | Mid-encode kill risk | Observe in WebView Home | Process lifecycle tests + adversarial test |
| Strict JSON guards | Silent mutation risk | Include confirm fields in tests | Contract review + unit tests |
| Duplicate-command guards | Race conditions | Observe active-job state | Process lifecycle + manual test |
| Release gates | Personal config leak | Use default build flags | Release self-test with -Verify |
| Network lifecycle | Orphaned workers | Backend/manual lifecycle workflow | Network checklist + backend command design |

---

## See Also

- Global rules reference: `..\..\AGENTS.md`; older AI directive redirects are archived under `..\archive\ai\`.
- Archived AI handoff inventory: `..\ARCHIVED_MD_INDEX.md`
- Current safety status: `docs/CURRENT_PROJECT_STATE.md`
- Validation ladder: `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- Lifecycle boundary: `docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
