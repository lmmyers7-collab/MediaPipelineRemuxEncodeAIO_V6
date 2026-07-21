# Verified Findings

Historical IDs are retained when a finding carries forward. Suspicions and
active hypotheses remain in `RUN_LOG.md` or the coverage matrix until the
troubleshooting loop supplies discriminating evidence.

## Required Record Shape

Each verified finding records stable ID, severity, confidence, status,
disposition, first-observed baseline, affected workflows/files, expected and
actual behavior, impact, exact evidence, minimal reproduction, root cause,
competing hypotheses, applicable invariant, existing protection and its gap,
smallest safe remediation, regression test, validation rung, historical links,
missing evidence, and remaining uncertainty.

## CSW-2026-07-09-SCHEDULE-001 — Watch debounce state is lost on backend restart

- Severity: P2.
- Confidence: high.
- Status: verified, open; broad remediation not authorized.
- Disposition: still present.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current applicability: committed HEAD
  `a8bf6e1dda9629e6f818ba12f2c8274362923372` and current overlay. The
  responsible source/test files have no working-tree diff.
- Workflows: WF-13 scheduling/watch folders; WF-01 restart; PASS-03 recovery;
  PASS-05 integrity/idempotency; PASS-06 stale state/concurrency.
- Affected files: `src/mediapipeline/desktop/watch/manager.py` and
  `tests/python/desktop/test_watch_folder_manager.py`.

Expected behavior: a candidate discovered before restart should either remain
eligible after its stability window or have a durable, explicit disposition.
Restart must not silently convert pending evidence into the startup baseline.

Actual behavior: `_baseline_signature`, `_baseline_stats`, `StabilityTracker`,
`_state`, and `pending_work` exist only in the manager instance. A restarted
manager baselines the already-present candidate, so later cycles report no new
stable file.

Impact: watch-folder work arriving shortly before backend restart can be missed
without a failed state, retry record, or operator-visible recovery action. The
source file is not mutated, but automatic ingestion reliability and evidence
integrity are reduced.

Supporting evidence:

- `manager.py:123-142` initializes all baseline/tracker/state in memory.
- `manager.py:230-235` resets baseline, tracker, and `pending_work`.
- `manager.py:417-427` treats a changed/startup signature as a fresh baseline.
- `manager.py:437-481` only observes paths differing from the in-memory
  baseline and sets pending work from the in-memory tracker.
- Repository search found no manager persistence/load path and no restart test.
- Isolated reproduction on 2026-07-19 exited 0 and returned
  `after_restart_detections=0`, `after_restart_pending_work=false`, and
  `after_restart_reason="No new stable watch-folder files detected."` for a
  synthetic file created after the first manager baseline but before restart.

Minimal reproduction:

1. Start `WatchFolderManager` on an empty temporary root with five-second
   debounce and `enqueue_only`.
2. Create a synthetic `.mkv` fixture, run cycles at 10 and 14 seconds, and stop
   before it becomes stable.
3. Create a new manager for the same root and run cycles after the debounce.
4. Observe no detection and `pending_work=false`.

Root cause: watch observation and pending-intent state has process lifetime,
while restart is treated as authoritative rebasing rather than recovery.

Competing hypotheses:

- A separate durable watch store reloads state: rejected by source/import search
  and the isolated restart reproduction.
- Startup rescan eventually re-detects the file: rejected because the existing
  file becomes baseline and unchanged baseline entries are skipped.
- Duplicate-command protection compensates: rejected; it protects launch, not
  undisclosed watch candidates.

Applicable boundary: backend owns watch/queue mutation and trustworthy recovery
evidence. Source mutation remains forbidden and was not involved.

Existing protection and gap: stability tracking and `pending_work` correctly
debounce during one process lifetime, while backend launch guards reduce
duplicates. Neither survives or reconciles restart.

Smallest safe remediation: add a backend-owned, atomically written,
fingerprint-bound observation/pending ledger or an equivalent restart
reconciliation rule that preserves at-least-once discovery without duplicate
launch. Do not put this policy in WebView.

Required regression: an isolated manager test that creates a candidate inside
the debounce window, restarts the manager, and proves one eventual detection
with no duplicate dispatch; add malformed/partial ledger and stale-fingerprint
cases if persistence is selected.

Required validation rung: targeted Python watch/queue/process tests, affected
Local API/browser schedule/watch smokes, restart/duplicate adversarial check,
and strict change-packet coverage. Representative real media is not required
for the state-transition defect, though later end-to-end watch ingestion should
remain a separate operational proof.

Related findings: original July sweep schedule finding; adjacent to lifecycle
durability findings but not a duplicate.

Missing evidence and uncertainty: no long-running watch soak or real operator
restart test has been run. The source-level and isolated reproduction prove the
loss, not its field frequency.

## CSW-2026-07-09-MAINTENANCE-002 — Dry-run UI contradicts checkpoint evidence

- Severity: P2.
- Confidence: high.
- Status: verified, open; broad remediation not authorized.
- Disposition: still present.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current applicability: committed HEAD
  `a8bf6e1dda9629e6f818ba12f2c8274362923372` and current overlay. The
  responsible frontend, facade, and test files have no working-tree diff.
- Workflows: WF-12 diagnostics/evidence; WF-14 release/maintenance operations;
  PASS-02 contract consistency; PASS-09 operator failed/degraded-state UX.
- Affected files:
  `apps/desktop/webview/static/assets/maintenance/releaseCommands.js`,
  `src/mediapipeline/core/maintenance/backfill_facade.py`, and
  `ops/pipeline/tests/Unit/Invoke-CompletedManifestBackfillDryRunChecks.ps1`.

Expected behavior: operator copy should distinguish prohibited completed-
manifest/default-state mutation from the intentional external audit checkpoint
that the dry-run command writes.

Actual behavior: the UI says the action “must not rewrite completed manifests
or checkpoints,” then displays `Checkpoint:`. The backend creates a timestamped
RunLogs checkpoint and passes it to the dry-run. Focused PowerShell coverage
requires that explicit checkpoint to be written.

Impact: the command can succeed while its evidence contradicts the displayed
guardrail. Operators cannot tell whether the checkpoint proves an expected
audit write or a safety violation, weakening trust and incident triage. No
completed-manifest mutation was observed.

Supporting evidence:

- `releaseCommands.js:401-425` contains the unqualified no-checkpoint promise
  and the rendered checkpoint path.
- `backfill_facade.py:25-40,56-73` creates, passes, and returns a timestamped
  checkpoint under RunLogs (or a fallback root).
- `Invoke-CompletedManifestBackfillDryRunChecks.ps1:95-100` asserts that the
  explicit dry-run checkpoint exists and contains `dry_run_completed` and
  `dry_run=true`.
- The focused PowerShell check ran on 2026-07-19, exited 0, printed the external
  checkpoint path, and ended `Completed manifest backfill dry-run checks passed.`

Minimal reproduction: run the focused completed-manifest backfill dry-run unit
check on its generated temp fixture and compare the asserted external
checkpoint with the WebView guardrail sentence.

Root cause: “dry run” copy conflates forbidden production/default-state writes
with an intentional audit-evidence checkpoint outside the completed manifest.

Competing hypotheses:

- The backend checkpoint is accidental: rejected by explicit facade construction,
  returned evidence, and a focused assertion requiring it.
- The UI means only default state checkpoints: possible intent, but rejected as
  an adequate contract because the wording is unqualified and the same panel
  displays a checkpoint path.
- The dry run rewrites the completed manifest: rejected by the passing fixture
  assertions; this finding is evidence-language drift, not unsafe manifest I/O.

Applicable boundary: backend owns mutation/evidence; frontend must accurately
display backend-authored effects. The right-sized safety protocol favors clear,
accurate messaging over redundant ceremony.

Existing protection and gap: backend dry-run prevents completed-manifest and
default-state checkpoint mutation, and the test verifies both. The UI omits the
allowed external evidence-write distinction.

Smallest safe remediation: change the guardrail to state that the command does
not rewrite completed manifests or default state checkpoints and may write a
RunLogs audit checkpoint; retain the displayed path. Do not remove useful
checkpoint evidence merely to match stale copy.

Required regression: static/browser assertion for the qualified message and
checkpoint display, plus the existing facade/PowerShell test proving no
manifest/default-state mutation and the intentional external checkpoint.

Required validation rung: WebView static/non-browser and affected browser
maintenance smoke, targeted facade test, focused PowerShell unit check, and
strict change-packet coverage. No representative media is required.

Related findings: original July maintenance finding. FR-042 concerns a
different rerun command's `-DryRun`/`-PlanOnly` semantics and is not a duplicate.

Missing evidence and uncertainty: the current focused backend/PowerShell proof
is strong; browser rendering of the exact corrected wording remains future
remediation validation.

## CPA-2026-07-19-001 — Smoke inventory check passes stale suite counts

- Severity: P3.
- Confidence: high.
- Status: remediated and regression-covered in the current overlay on
  2026-07-20; not yet committed or shipped.
- Disposition: fixed by the narrowly scoped browser-evidence tooling packet
  `MP-CHANGE-2026-0720-009`.
- First observed baseline: committed HEAD
  `a8bf6e1dda9629e6f818ba12f2c8274362923372`; the overlay adds one further
  direct-only module.
- Workflows: WF-14 release validation; PASS-07 test quality; PASS-10 production
  readiness; OWN-10 generated navigation/inventory integrity.
- Affected files: `docs/inventories/SMOKE_TEST_INVENTORY.md`, multiple active
  testing/inventory docs, `docs/generated/SMOKE_WRAPPER_MAP.json`, and
  `src/mediapipeline/tools/dev/generate_smoke_wrapper_map.py`.

Expected behavior: canonical counts and direct-only coverage match disk, and the
no-write generator check fails when active summary claims are stale.

Actual behavior: HEAD contains 25 browser wrappers and 33 browser modules,
while active docs claim 24 wrappers and 26 modules. The current overlay contains
34 modules. The generated map correctly reports 25 wrappers and nine current
direct-only modules can be derived, yet `--check` exits 0 because it verifies
only wrapper-name presence in prose/release files, not numeric claims or
direct-only module coverage.

Impact: validation planning, result templates, and release evidence can omit or
miscount browser surfaces while the advertised drift guard remains green. This
is an evidence/coverage defect, not proof that the omitted modules fail.

Supporting evidence:

- `git ls-tree` count at HEAD: 25 wrappers and 33 modules.
- Current disk: 25 wrappers and 34 modules; the untracked Run Monitor module is
  the overlay-only addition.
- Active docs at `SMOKE_TEST_INVENTORY.md:11`,
  `BROWSER_SMOKE_TEST_RUNBOOK.md:55,88,248`,
  `VALIDATION_LADDER_RUNBOOK.md:92,422-423`, and related inventories/templates
  claim 24/26 (one test inventory claims 24/27).
- Current generated map reports `browser_smoke=25`, `drift_finding_count=0`.
- Generator lines 141-190 enumerate wrappers and check name presence only;
  lines 194-210 calculate counts but do not compare them with prose or enumerate
  direct-only browser modules.
- Canonical `generate_smoke_wrapper_map --check` exited 0 with “current and
  wrapper references match.”

Minimal reproduction: count `Test-WebViewBrowser*.ps1` and
`test_webview_browser*.py`, compare with active prose, then run the canonical
map `--check`; observe count disagreement and a green result.

Root cause: prose counts and direct-module inventory are manually maintained,
while the generated drift guard is wrapper-centric and treats simple name
presence as complete documentation alignment.

Competing hypotheses:

- The extra wrapper/modules exist only in the dirty overlay: rejected; HEAD has
  25/33. Only the Run Monitor module is overlay-only.
- The 26 count intentionally excludes census modules: rejected as adequate
  documentation because the docs say discovery covers all browser modules and
  name only two direct modules, while eight exist at HEAD.
- The generator is stale: rejected for current overlay; `--check` says its JSON
  is current. Its validation scope is insufficient.

Applicable boundary: generated maps/inventories must remain current when public
test surfaces change; green prerequisite/inventory checks must not overstate
coverage.

Existing protection and gap: wrapper-map generation catches missing wrapper
references and release-layout omissions. It does not validate prose totals,
discover direct-only modules, or check that documentation's direct-module list
is complete.

Smallest safe remediation: derive wrapper/module/direct-only counts and names
from disk in one generated inventory, update active prose from that source, and
make `--check` fail on stale numeric/direct-module claims. Avoid another manual
count source.

Required regression: generator unit fixture with an added direct-only browser
module and stale prose count/list; `--check` must report drift. Assert HEAD-style
control-census modules are classified intentionally.

Required validation rung: targeted tooling generator tests, generator `--check`,
summary/inventory integrity tests, and change-packet coverage. No browser or
real-media execution is needed for the count defect.

Related findings: historical generated-context/inventory drift items FR-057
through FR-060 are related themes but do not duplicate this current false-green
count check.

Remediation evidence: the v2 generator recursively discovers every
`test_webview_browser*.py` module, classifies 25 wrapper-backed and 9
direct-only modules, requires one exact catalog heading per wrapper, and fails
on stale reported numeric counts across 12 active inventory, operator, result,
coverage, and runbook documents. All 45 monitored count claims now reconcile
to 37 canonical wrappers overall, 25 browser wrappers, 34 browser modules, 25
wrapper-backed modules, and 9 direct-only modules. The focused generator regression tests, canonical
`generate_smoke_wrapper_map --check`, and the complete strict browser campaign
all pass; all 34 modules executed 42 tests with zero suite skips. Direct-only
modules remain visible in the generated map instead of being silently omitted.

Missing evidence and uncertainty: the remediation exists only in the current
dirty overlay until packet validation, review, commit, and release. Global
strict change-packet worktree coverage is separately affected by unrelated
dirty packets/files; that does not reopen the reproduced count/check defect.

## CPA-2026-07-19-002 — HDR10 verification drops the Run Monitor heartbeat

- Severity: P2.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: newly verified overlay finding.
- First observed baseline: current working-tree overlay. HEAD had no verification
  heartbeat arguments; the incomplete propagation is introduced by the overlay.
- Workflows: WF-05 probe/verification; WF-12 progress evidence; PASS-02 contract
  consistency; PASS-03 timeout/recovery; PASS-08 integration consistency.
- Affected files: `ops/pipeline/engine/probe/media_probe_hdr.ps1`,
  `ops/pipeline/engine/probe/media_probe_streams.ps1`, and
  `ops/pipeline/engine/process/encode_verification.ps1`.

Expected behavior: the overlay's verification poll handler reaches both bounded
HDR10 source/output metadata probes so long-running native work refreshes Run
Monitor evidence consistently with the other verification probes.

Actual behavior: `Test-Hdr10OutputMetadataPreservation` passes
`-PollHandler/-PollMilliseconds` into `Get-SourceHdr10MasteringMetadata`, and
that function forwards variables of those names to `Invoke-FFprobeCommand`, but
its parameter block declares only `FilePath`. PowerShell accepts the extra
arguments in `$args`; the undeclared variables resolve to null/zero.

Impact: the two HDR10 mastering-metadata probes can each run for up to 30 seconds
without the intended verification heartbeat. Run Monitor/progress evidence may
look stale during active work, weakening stop/recovery decisions. HDR metadata
parsing and fail-closed publish gating remain intact.

Supporting evidence:

- `encode_verification.ps1:124-130` supplies the verification poll handler.
- `media_probe_streams.ps1:497-498` forwards it to both source/output HDR probes.
- `media_probe_hdr.ps1:103` declares only `FilePath`, while line 110 uses the
  undeclared poll variables.
- The Git diff proves the heartbeat plumbing is overlay-only.
- A no-write mocked reproduction on 2026-07-19 exited 0 and captured
  `Stage=hdr10-mastering-probe`, `PollHandlerIsNull=true`, and
  `PollMilliseconds=0` after calling the function with a real scriptblock and
  `777` milliseconds.
- Search found structural HDR verification coverage but no binding assertion
  for this function's poll handler.

Minimal reproduction: dot-source the probe module, mock
`Invoke-FFprobeCommand`, call `Get-SourceHdr10MasteringMetadata` with a handler
and nonzero interval, and inspect the mock's received values.

Root cause: a cross-file signature update added heartbeat arguments at callers
and the native invocation but omitted them from the intermediate function's
parameter block. PowerShell's simple-function extra-argument behavior hides the
contract error instead of throwing.

Competing hypotheses:

- PowerShell rejects the unknown named arguments: rejected by the exit-0 mock
  reproduction.
- Dynamic scope supplies the caller's handler: rejected; the mock received null
  and zero.
- The defect changes HDR verification results: rejected by call flow; only poll
  callback/interval binding is lost.

Applicable boundary: progress, command journal, and lifecycle evidence must not
claim stale/idle work while app-owned native work is active. Media correctness
and source-mutation boundaries are unaffected.

Existing protection and gap: the overlay creates a throttled verification poll
handler and correctly threads it through other probes. No signature-level test
asserts that this HDR helper receives it.

Smallest safe remediation: declare typed `PollHandler` and
`PollMilliseconds` parameters on `Get-SourceHdr10MasteringMetadata`, matching
the other probe helpers. Avoid broader media-policy changes.

Required regression: mocked PowerShell check that passes a non-null handler and
nondefault interval through `Test-Hdr10OutputMetadataPreservation` and observes
both source/output `hdr10-mastering-probe` invocations receiving them.

Required validation rung: focused PowerShell probe/verification unit checks,
Run Monitor/heartbeat checks, pipeline processing split contracts, and strict
packet coverage. Representative real media is required to prove operator-visible
heartbeat behavior during a real HDR probe, but not to prove the binding defect.

Related findings: part of the current uncommitted Run Monitor/long-native-stage
overlay; no matching historical finding was found.

Missing evidence and uncertainty: no representative HDR media run or UI timing
capture was performed. The lost parameter binding is proven; field-visible
staleness duration depends on probe latency.

## CPA-2026-07-19-003 — Scratch reuse is not bound to source content

- Severity: P1.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: newly verified finding with independent reviewer and coordinator
  reproduction.
- First observed baseline: committed HEAD
  `a8bf6e1dda9629e6f818ba12f2c8274362923372`; applies to the overlay because
  its scratch changes add monitoring only and leave identity/reuse logic intact.
- Workflows: WF-08 source/scratch/path integrity; WF-05 media routing; WF-09
  publish correctness; PASS-05 data integrity/idempotency; PASS-11 adversarial
  disproof.
- Affected files: `ops/pipeline/engine/storage/scratch_copy.ps1` and
  `ops/pipeline/engine/shared/source_identity.ps1`.

Expected behavior: an existing scratch input is reused only when it is
content-bound to the current source object. Replacing bytes at the same path
must invalidate the scratch even when metadata is preserved.

Actual behavior: the scratch directory key and `.srcinfo` match use only full
path, file length, and last-write timestamp. When those values are preserved,
`Ensure-ScratchCopy` accepts an internally valid old scratch without comparing
it to current source content.

Impact: a same-path source replacement can be routed and published using stale
scratch bytes, producing the wrong media under the newly planned destination
and evidence. Source media is not mutated, but output/data integrity and
operator trust are violated silently.

Supporting evidence:

- `scratch_copy.ps1:11-25` defines the fingerprint as path/size/mtime.
- `scratch_copy.ps1:52-59` derives the scratch directory from v1 identity, also
  path/size/mtime (`source_identity.ps1:23-37`).
- `scratch_copy.ps1:139-160` accepts the same three fingerprint fields.
- `scratch_copy.ps1:241-278` reuses the scratch after independent container
  integrity, which proves readability but not equality to the current source.
- The repository already has `Get-SourceIdentityKeyV2` and tests proving
  same-path/same-size/same-mtime replacement must invalidate probe/retry caches,
  but scratch reuse still uses v1.
- Independent reviewer reproduction and coordinator reproduction both used
  isolated temporary roots. The coordinator changed source `AAAA` to `BBBB`,
  restored size and mtime, and observed `FingerprintMatch=true`, the same scratch
  path, scratch `AAAA`, source `BBBB`, and unequal SHA-256 hashes.

Minimal reproduction:

1. Copy a temporary source into scratch through `Ensure-ScratchCopy`.
2. Replace the source contents with different same-length bytes and restore its
   original last-write timestamp.
3. Call `Ensure-ScratchCopy` again with the refreshed `FileInfo`.
4. Observe the original scratch is reused and hashes differ.

Root cause: scratch identity predates the repository's content-aware v2 source
identity. The integrity gate validates that scratch is readable/structurally
valid, not that it still represents the source selected for this run.

Competing hypotheses:

- Scratch integrity detects the replacement: rejected; it probes scratch alone.
- The scratch directory changes: rejected; v1 key uses the preserved metadata.
- Existing v2 source identity protects scratch: rejected; scratch explicitly
  calls `Get-SourceIdentityKey`, not v2.
- This requires malicious timestamp forgery: rejected as a necessary condition;
  backup/restore, copy, and synchronization tools can preserve size/mtime.

Applicable boundary: scratch isolation must prevent failed/interrupted work and
cross-source contamination. Backend publication evidence must describe the
actual source content used. Source mutation remains forbidden and did not occur.

Existing protection and gap: boundary guards, atomic `.srcinfo`, readability
checks, and path/size/mtime matching block many collisions and corrupt scratch
files. They do not bind readable scratch bytes to current source bytes.

Smallest safe remediation: persist a repository-authoritative strong content
identity with the scratch fingerprint and recompute/compare it before reuse.
Use an exact digest when equality is required; a sampled identity alone must not
be described as cryptographic equality. Migrate or invalidate legacy v1
fingerprints safely.

Required regression: same-path/same-size/same-mtime valid-media replacement
must force recopy; include legacy fingerprint migration, malformed fingerprint,
locked stale scratch, and unchanged-source reuse cases.

Required validation rung: focused scratch/path/source-identity PowerShell tests,
reliability/adversarial processing checks, and representative real-media proof
showing the replaced source is copied and published while source hashes remain
unchanged. This is a high-risk storage/media-policy gate.

Related findings: the module's historical `FIX#1` addressed same-safe-name
cross-source contamination; this is the remaining same-metadata content variant.
Probe/retry identity tests already encode the stronger expected behavior.

Missing evidence and uncertainty: representative valid-media publication was
not run. The stale-byte reuse and unequal hashes are proven; field frequency is
unknown.

## CPA-2026-07-19-004 — A shell crash releases the singleton guard while its backend survives

- Severity: P1.
- Confidence: high.
- Status: verified, open; broad remediation not authorized.
- Disposition: newly verified finding with independent reviewer and coordinator
  source-trace verification.
- First observed baseline: committed HEAD
  `a8bf6e1dda9629e6f818ba12f2c8274362923372`; applies to the overlay because
  the responsible Rust files are unchanged and the Python entry-point diff does
  not add a backend singleton or reconnect path.
- Workflows: WF-01 startup/shutdown; WF-02 process lifecycle; WF-13 watch
  folders; PASS-03 recovery; PASS-06 concurrency; PASS-10 readiness.
- Affected files: `apps/desktop/tauri/src-tauri/src/single_instance_guard.rs`,
  `apps/desktop/tauri/src-tauri/src/lib.rs`,
  `src/mediapipeline/desktop/local_api_main.py`, and
  `docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`.

Expected behavior: the one-backend/single-operator boundary survives abnormal
shell exit, or a subsequent shell reconnects to the surviving authenticated
backend instead of creating another control plane.

Actual behavior: the only named mutex is owned by the Tauri process and closes
with that process. The lifecycle contract explicitly allows the Python backend
to continue after a shell crash. A later shell therefore reacquires the mutex
and unconditionally starts a new backend on another ephemeral port, including a
second watch-folder manager over the same backend-owned state.

Impact: after a hard shell crash, two authenticated local backends/watchers can
coexist against the same configuration, queue, command journal, and runtime
files. Durable launch leases reduce duplicate media starts, but do not prevent
competing watch scans, control mutations, or contradictory lifecycle evidence.

Supporting evidence:

- `single_instance_guard.rs:10-14,18-39,47-55` places the named Windows mutex
  handle solely in a shell-owned object and closes it on drop/process exit.
- `lib.rs:114-134` acquires that shell guard, then unconditionally calls
  `start_backend`; there is no surviving-backend discovery/reconnect branch.
- `TAURI_BACKEND_LIFECYCLE_BOUNDARY.md:94-97` explicitly states that the Python
  backend continues running if the shell crashes before shutdown.
- `local_api_main.py:62-70` defaults to port zero, so the next backend can bind
  independently, and lines 500-529 start a watch-folder manager per backend.
- Repository search found no backend-owned named mutex, job object with
  kill-on-shell-close semantics, or authenticated reconnect-to-existing path.
- An independent reviewer and the coordinator traced the same boundary. The
  coordinator also confirmed the responsible Rust files are unchanged from
  HEAD; the overlay's `local_api_main.py` changes do not close the gap.

Minimal reproduction: start the shell/backend, terminate only the Tauri process
without its shutdown request, verify the Python backend remains, and relaunch
the shell. The source trace predicts a second backend on a new port. This native
hard-crash reproduction was not executed because it would create live operator
process/state risk during discovery.

Root cause: singleton ownership and backend lifetime have different failure
domains. The shell mutex protects only concurrent shells, while the backend is
deliberately allowed to outlive the mutex owner.

Competing hypotheses:

- The backend holds the mutex: rejected by ownership/source trace.
- The relaunch reconnects to the old backend: rejected by unconditional
  `start_backend` and ephemeral-port bootstrap design.
- Active-job leases fully contain the risk: rejected; they protect specific
  launches, not all watcher/state/control-plane activity.
- Shell crash always kills the child: rejected by the authoritative lifecycle
  document and lack of a Windows job-object kill-on-close boundary.

Applicable boundary: single-instance, backend lifecycle, duplicate-command,
and close-readiness controls are release-critical; backend-owned state must not
have two competing local control planes.

Existing protection and gap: the shell mutex blocks a second healthy shell,
backend launch leases guard some media starts, and restart reconciliation
handles stale ActiveJobs. None binds the surviving backend to the singleton or
prevents a new backend while it remains alive.

Smallest safe remediation: give the shell/backend pair one durable ownership
boundary: preferably assign the backend to a Windows job object configured for
kill-on-owner-close, or implement a backend-owned singleton plus authenticated
reconnect/ownership transfer. Preserve the normal graceful shutdown contract.

Required regression: a native Tauri hard-crash test must prove either the child
backend terminates and a relaunch creates exactly one backend, or the relaunch
authenticates to the single survivor without starting another watcher. Include
normal close, startup failure, and stale-bootstrap cases.

Required validation rung: Tauri check/build, shell scaffold and lifecycle tests,
isolated native crash/relaunch process census, watcher/duplicate-launch checks,
and strict packet coverage. Representative media is not required to prove the
process-count defect, but a later isolated watch/queue test should prove no
duplicate dispatch.

Related findings: `CSW-2026-07-09-SCHEDULE-001` concerns pending watch evidence
lost on restart; this finding concerns two live backends after abnormal shell
exit and is not a duplicate.

Missing evidence and uncertainty: native hard-crash/relaunch execution was not
run. The lifetime mismatch is source-proven; the frequency of orphaned backends
in operator use is unknown.

## CPA-2026-07-19-005 — Forced shutdown succeeds even when active-work cleanup fails

- Severity: P1.
- Confidence: high.
- Status: verified, open; broad remediation not authorized.
- Disposition: newly verified finding with independent reviewer and coordinator
  reproduction.
- First observed baseline: committed HEAD
  `a8bf6e1dda9629e6f818ba12f2c8274362923372`; applies to the overlay. The
  overlay changes adjacent process evidence but retains the success/scheduling
  behavior.
- Workflows: WF-02 close/process lifecycle; WF-05 media execution; WF-09
  publish safety; PASS-03 recovery; PASS-05 integrity; PASS-09 operator UX.
- Affected files: `src/mediapipeline/core/api/commands_process.py`,
  `src/mediapipeline/core/api/command_results.py`,
  `src/mediapipeline/core/processes/kill.py`, and
  `tests/python/desktop/test_application_facade_local_api_lifecycle.py`.

Expected behavior: when force-close is confirmed for active work, backend exit
is scheduled only after cleanup provides verified terminal evidence, or the
response remains failed/degraded and the backend stays available for recovery.

Actual behavior: both cleanup exceptions are converted to warning strings;
the backend shutdown callback is always scheduled; and the returned command
payload has `ok=true`. A lower process-tree path can likewise return a degraded
message when descendant exit is unverified, which the caller treats as a normal
cleanup message rather than a failed terminal condition.

Impact: the backend can terminate while media/helper descendants remain alive
or unverified, removing the local API and operator recovery surface while work
continues. The UI/journal receives a successful forced-shutdown result even
though process ownership and terminal state are not established.

Supporting evidence:

- `commands_process.py:270-289` catches both cleanup exceptions and returns
  them as messages; lines 329-340 then schedule shutdown unconditionally.
- `command_results.py:218-250` returns `ok=true`, warning severity, and a
  shutdown refresh hint for any forced active-work path, including cleanup
  failure strings.
- `kill.py:478-500` can return a degraded/unverified process-tree message rather
  than raise; the shutdown layer has no structured terminal-evidence check.
- The same control flow exists at HEAD. Overlay changes do not change the
  unconditional shutdown/success contract.
- An independent reviewer reproduced the result. The coordinator repeated an
  isolated in-memory reproduction with both cleanup methods raising and got
  `ok=true`, `severity=warning`, `shutdown_requested=true`, and both failure
  strings in `cleanup_messages`.
- Existing lifecycle coverage at
  `test_application_facade_local_api_lifecycle.py:246-300` tests only successful
  cleanup and asserts that shutdown is scheduled.

Minimal reproduction: construct the existing command mixin with unsafe close
readiness, make both cleanup methods raise, call `_backend_shutdown_payload`
with strict `force_active_work_shutdown=true`, and observe success plus a fired
shutdown callback.

Root cause: human-readable cleanup messages conflate verified kills, degraded
cleanup, and exceptions, while the force-close branch treats confirmation as
authorization to report/schedule success rather than authorization to attempt a
cleanup whose terminal result must still be verified.

Competing hypotheses:

- Cleanup exceptions prevent backend exit: rejected by the fired callback.
- Warning severity makes `ok=true` safe: rejected; consumers and journal still
  receive a successful terminal command and the API exits.
- The lower kill path always raises on unverified descendants: rejected by its
  explicit degraded-message return.
- Tauri will necessarily kill every descendant afterward: rejected as a
  backend contract and by direct-child termination fallback limitations.

Applicable boundary: command journal, close-readiness, forced shutdown, and
process terminal evidence are release-critical; unsafe work must not become
unowned through an optimistic control response.

Existing protection and gap: strict boolean confirmation, readiness blocking,
tracked/related cleanup attempts, reconciliation flags, and warning evidence
exist. The API does not require structured verified-exit evidence before it
removes itself.

Smallest safe remediation: return structured cleanup outcomes with verified
root/descendant terminal status; keep the backend running and return `ok=false`
when required cleanup throws or remains unverified. If an emergency abandon
mode is desired, make it a separately named, explicitly evidenced policy rather
than treating cleanup failure as successful shutdown.

Required regression: failed tracked cleanup, failed related cleanup, degraded
taskkill/descendant verification, mixed success, and all-success cases must
assert callback scheduling, result `ok`, journal severity, and reconciliation
state. Only verified all-success may schedule the normal forced shutdown.

Required validation rung: targeted Python lifecycle/process-kill tests, strict
route/journal and duplicate-command tests, Tauri close integration, isolated
child/descendant failure simulation, and strict packet coverage. Do not perform
live operator force-close during audit discovery.

Related findings: historical close-readiness/process cleanup items improved
visibility and reconciliation, but none documents this success-on-cleanup-
failure contract.

Missing evidence and uncertainty: no live child process was left running and no
native Tauri force-close was performed. The API success/scheduling defect is
reproduced; OS-specific descendant behavior remains separately gated.

## CPA-2026-07-19-006 — Tauri treats a child wait error as verified backend exit

- Severity: P2.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: newly verified HEAD and overlay finding.
- First observed baseline: committed HEAD
  `a8bf6e1dda9629e6f818ba12f2c8274362923372`; the responsible Rust file is
  unchanged in the overlay.
- Workflows: WF-01 startup/shutdown; WF-02 lifecycle; PASS-03 recovery;
  PASS-08 runtime consistency; PASS-09 operator evidence.
- Affected file: `apps/desktop/tauri/src-tauri/src/backend_process.rs`.

Expected behavior: `try_wait` errors remain errors/unknown terminal state and
must not release process ownership or produce a successful shutdown result.

Actual behavior: `wait_for_child_exit` returns `true` for `Err(_)`. Both callers
interpret that as exit: one removes the child from managed state, while the
other already took it from managed state. The local `Child` is then dropped and
shutdown returns `Requested` without kill/wait verification.

Impact: an OS handle/wait error can orphan a still-running backend while Tauri
reports shutdown requested and loses the handle needed for further cleanup.

Supporting evidence:

- `backend_process.rs:475-487` maps `Err(_)` to `true`.
- Lines 134-144 and 146-157 treat `true` as successful exit and release child
  ownership; the timeout path alone attempts termination.
- The monitoring path at lines 93-108 correctly propagates `try_wait()?`,
  proving error propagation is already the adjacent contract.
- Tests only assert that the helper/call/fallback strings exist; no error-path
  behavior is exercised.
- The official Rust `std::process::Child` documentation says `try_wait` returns
  an error when an error occurs and dropping `Child` does not terminate or wait
  for the process: <https://doc.rust-lang.org/std/process/struct.Child.html>.

Minimal reproduction: inject a child/wait abstraction whose `try_wait` returns
an I/O error and call both shutdown branches; observe `Requested` and released
ownership without `terminate_child`. A native OS-error injection was not run.

Root cause: a boolean helper collapses three states—exited, still running, and
wait failed—into two, classifying failure as exit.

Competing hypotheses: an error proves the process is gone is rejected by the
Rust contract; dropping `Child` kills it is rejected by the same contract; the
backend shutdown request necessarily succeeds is rejected because the same
helper is used after request failure; monitoring repairs ownership is rejected
because the child has been removed from managed state.

Applicable boundary: shell/backend lifecycle and terminal process evidence must
remain fail-closed and truthful.

Existing protection and gap: bounded graceful wait, tree termination on timeout,
and lifecycle monitoring exist. None runs when `try_wait` itself errors.

Smallest safe remediation: return a typed three-state/result value, preserve
managed ownership on wait error, log the error, and report `Failed` unless a
separate verified termination succeeds.

Required regression: injectable unit tests for exited/running/timeout/error in
both request-success and request-failure branches, asserting ownership,
termination calls, and final outcome.

Required validation rung: Rust unit/check/build, Tauri scaffold/lifecycle tests,
isolated child error/timeout integration, and strict packet coverage.

Related findings: `CPA-2026-07-19-004` covers abnormal shell death and `005`
covers backend force-cleanup failure; this is a distinct Rust wait-error path.

Missing evidence and uncertainty: no native Windows wait-handle fault was
injected, so field frequency is unknown; the false-state transition is
source- and runtime-contract-proven.

## CSW-2026-07-09-HOME-003 — Raw malformed close readiness can render as safe

- Severity: P2.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: still present.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current applicability: committed HEAD and overlay. Overlay changes in the two
  frontend files are unrelated to close-readiness normalization/truth testing.
- Workflows: WF-01/WF-02 lifecycle; WF-12 diagnostics; PASS-02 contracts;
  PASS-09 operator failure-state UX.
- Affected files: `apps/desktop/webview/static/assets/app/closeReadiness.js`,
  `apps/desktop/webview/static/assets/app.js`,
  `apps/desktop/webview/static/assets/app/refreshCoordinator.js`,
  `apps/desktop/webview/static/assets/app/lifecycle.js`, and
  `apps/desktop/webview/static/assets/app/lifecycle/topbar.js`.

Expected behavior: every consumer receives the fail-closed normalized
close-readiness object; non-boolean `safe_to_close` never renders ready/safe.

Actual behavior: the primary renderer normalizes and stores the response, but
the same refresh continues passing the raw truthy response to downstream
consumers because `values["close readiness"] || lastCloseReadiness` prefers the
raw object. Lifecycle facts and summaries use JavaScript truthiness, so the
string `"false"` renders `Safe`/ready. The strict topbar lifecycle state keeps
the shutdown button disabled, producing contradictory output.

Impact: a malformed backend/intermediary response can show close readiness,
pipeline state, and watcher facts as ready while the request-status control says
blocked. The mutation guard remains fail-closed, but operator diagnosis and
trust are degraded at a release-critical boundary.

Supporting evidence: normalizer lines 16-29 reject non-booleans; `app.js:105-134`
stores the normalized result; `refreshCoordinator.js:338-425` repeatedly
prefers the raw value; `lifecycle.js:127-130,187-193,292-316` truth-tests it;
`lifecycle/topbar.js:428-458` uses strict equality for command enablement.
An isolated Node DOM-stub reproduction passed `safe_to_close:"false"` and
returned a disabled button/status `Blocked` while facts rendered Close-readiness
`Safe`, Pipeline state `ready`, and Watcher `ready`.

Minimal reproduction: invoke `renderBackendLifecycle` with a raw object whose
`safe_to_close` is the string `"false"`; inspect the button/status and rendered
facts.

Root cause: normalization is a side effect of one renderer rather than a single
data-boundary transform shared by every consumer.

Competing hypotheses: all consumers use `lastCloseReadiness` is rejected by the
raw-value preference; JavaScript string `"false"` is falsey is rejected by the
reproduction; unsafe shutdown becomes enabled is rejected by the strict
topbar function—this finding is contradictory safety presentation, not route
authorization bypass.

Applicable boundary: frontend must display backend lifecycle evidence
consistently and fail closed without implementing independent policy.

Existing protection and gap: the normalizer and strict command gate prevent
unsafe enablement. Raw data still bypasses normalization for display consumers.

Smallest safe remediation: normalize once immediately after route resolution,
replace the value in the refresh model, and pass only that object; use strict
boolean checks in every lifecycle renderer.

Required regression: malformed/null/array/string boolean payloads passed
through the full refresh fan-out must render uniformly unavailable/blocked and
keep controls disabled.

Required validation rung: Node/static tests, affected browser Home/Diagnostics
smokes, Local API malformed contract check, and strict packet coverage.

Related findings: original `HOME-003`; no replacement ID issued.

Missing evidence and uncertainty: no full browser screenshot was captured. The
contradictory rendered model is reproduced in the actual module with DOM stubs.

## CSW-2026-07-09-TELEMETRY-004 — First backend-stale observation is rendered active

- Severity: P2.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: still present.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current applicability: committed HEAD and overlay; responsible file unchanged.
- Workflows: WF-12 telemetry/progress; WF-02 stop/recovery evidence; PASS-02
  contracts; PASS-03 recovery; PASS-09 operator UX.
- Affected file: `apps/desktop/webview/static/assets/progress/barState.js`.

Expected behavior: backend-authored `stale=true` is displayed as stale/warning
immediately; presentation hysteresis must not negate an authoritative safety
state.

Actual behavior: the module requires two stale observations. On the first it
sets `stale=false` and rewrites warning status to active.

Impact: for at least one refresh interval, an already-stale worker/tool bar can
look actively healthy, delaying failure recognition or stop/recovery action.

Supporting evidence: lines 3-5 set confirmation count two; lines 151-163 clear
the first stale flag and rewrite warning to active. Repository search found no
behavioral test for this transition. An isolated Node execution produced first
`{status:"active",stale:false}` and second
`{status:"warning",stale:true}` from the same backend-stale bar.

Minimal reproduction: create the real bar-state module, call
`progressBarWithStaleDisplayHysteresis` twice with the same stale warning bar and
item identity, and compare results.

Root cause: UI anti-flicker policy overrides backend freshness authority rather
than applying hysteresis only before backend classification or to non-safety
cosmetics.

Competing hypotheses: backend may be transiently wrong does not authorize the
frontend to claim active; only color changes is rejected because both status
and stale flag change; a test protects the contract is rejected by search.

Applicable boundary: backend owns state/evidence; WebView must not weaken stale
classification independently.

Existing protection and gap: item-keyed reset prevents carryover and the second
observation displays stale. The first authoritative stale result is still lost.

Smallest safe remediation: display backend `stale=true` immediately; if
anti-flicker remains desirable, apply it only to locally inferred uncertainty
and never change warning to active.

Required regression: first/second stale, fresh reset, item change, and locally
inferred uncertainty cases must preserve backend-authored stale truth.

Required validation rung: targeted Node/static progress tests, affected browser
progress/Diagnostics smoke, and strict packet coverage.

Related findings: original `TELEMETRY-004`; no replacement ID issued.

Missing evidence and uncertainty: no timed browser capture was run; actual delay
depends on refresh cadence, while the first-observation rewrite is reproduced.

## CPA-2026-07-19-007 — Persistent subtitle prerequisites are automatically retried

- Severity: P2.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: newly verified HEAD and overlay finding.
- First observed baseline: committed HEAD
  `a8bf6e1dda9629e6f818ba12f2c8274362923372`; overlay changes add unrelated
  failure evidence/codes and retain the classification behavior.
- Workflows: WF-06 subtitles; WF-03 queue retries; PASS-03 failure/recovery;
  PASS-07 test quality; PASS-09 operator UX.
- Affected files: `ops/pipeline/engine/subtitles/failure_records.ps1`,
  `ops/pipeline/engine/failures/failure_state.ps1`,
  `ops/pipeline/engine/shared/failure_codes.ps1`, and subtitle unit/integration
  tests.

Expected behavior: missing/unsupported OCR tools, missing tessdata, and unknown
OCR language are immediately operator-required/non-retryable because repeating
the same source cannot repair persistent prerequisites. Execution/timeout faults
may remain transient.

Actual behavior: BDPGS, VobSub, and ASS failure families are registered
universally as `transient`; code metadata defaults all subtitle prerequisite
codes to retryable; failure state automatically consumes retry attempts before
escalating at the configured limit.

Impact: unattended queues can repeatedly perform extraction/OCR setup and fail
the same sources, adding churn, logs, delayed work, and misleading retryability
before exposing the configuration action already required.

Supporting evidence:

- `failure_records.ps1:133-180` routes whole BDPGS/VobSub/ASS families to
  `Classification 'transient'` without code-specific persistence policy.
- `failure_state.ps1:753-769` increments every transient code and escalates only
  at the retry limit.
- `failure_codes.ps1:336-358` defaults unrecognized subtitle codes to `true`,
  while lines 436-443 prescribe tool/tessdata/language repair or disabling OCR.
- The same behavior exists at HEAD; overlay diffs do not alter it.
- A no-write PowerShell check returned `True` for nine BDPGS/VobSub missing,
  unsupported, tessdata, language, Tesseract, and extraction-tool codes.
- Existing subtitle tests assert distinct codes and operator action text, but no
  test asserts non-retryability/classification for persistent prerequisites.

Minimal reproduction: load the failure-code registry and query retryability for
the nine prerequisite codes; observe `true`, then trace a registered transient
record through the retry counter.

Root cause: retry policy is family/default based rather than failure-code based,
and the recorder discards the semantic distinctions its helpers already emit.

Competing hypotheses: settings validation always prevents runtime occurrence is
rejected because tools/tessdata can disappear after save and runtime helpers
emit these codes; retry can repair configuration is rejected absent external
operator mutation; retry limit prevents impact is incomplete because it causes
the unnecessary attempts; all subtitle failures should be permanent is rejected
because timeouts/execution faults can be transient.

Applicable boundary: subtitle conversion failure routes to review rather than
silent bad publish, and retry evidence must distinguish recoverable execution
faults from persistent operator prerequisites.

Existing protection and gap: config validation, distinct failure codes,
preservation defaults, suggested actions, and eventual escalation exist. The
runtime retry decision ignores the code distinctions.

Smallest safe remediation: make persistent prerequisite codes explicitly
non-retryable/operator-required at registration and metadata layers; retain
transient policy for bounded execution/timeouts and preserve original tracks.

Required regression: table-driven registry and recorder tests for each
prerequisite versus transient execution/timeout code, asserting classification,
retry count, queue terminal state, suggested action, and preserved subtitle.

Required validation rung: focused subtitle builder/OCR/failure-code/failure-state
checks, queue retry/recovery tests, and representative subtitle media for final
preservation/OCR behavior. The classification defect itself needs no live media.

Related findings: historical FR-015 retains a separate representative subtitle
evidence gap; this finding is runtime retry policy.

Missing evidence and uncertainty: no representative PGS/VobSub media or queue
soak was run. Classification and retryability are proven; cost frequency is
unknown.

## CSW-2026-07-09-SETTINGS-001 — Hidden authentication tokens can traverse the browser patch request

- Severity: P1.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: still present.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current applicability: committed HEAD and overlay; responsible files are
  unchanged.
- Workflows: WF-04 settings/profiles; WF-11 network coordinator/worker;
  PASS-04 security; PASS-08 integration consistency.
- Affected files: `src/mediapipeline/core/config/settings_patch_candidate_facade.py`,
  `tests/python/desktop/test_application_facade_settings_patch.py`, and
  `docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md`.

Expected behavior: authentication-token values remain outside browser storage,
developer tools, request payloads, and JavaScript heap; a browser-originated
settings patch rejects real secret values rather than merely redacting its
response.

Actual behavior: the candidate builder accepts registered sensitive keys with
any value other than the literal `<redacted>`. The request-evidence model also
retains the raw `changes` mapping. A focused test intentionally sends a real
replacement `CoordinatorAuthToken` through the application-facade preview and
expects success.

Impact: an operator who edits or previews a coordinator/worker token through
this surface exposes that credential to the WebView request boundary and its
debugging/inspection environment, contrary to the documented security model.
Response redaction occurs after the prohibited exposure.

Supporting evidence:

- `SETTINGS_RAW_KEY_TRIAGE.md:70-79` marks both auth-token keys hidden and says
  they must not reach browser storage, developer tools, or JavaScript heap.
- `settings_patch_candidate_facade.py:257-319` accepts registered sensitive
  values and rejects only the placeholder; lines 272-277 retain raw changes in
  request evidence.
- `test_application_facade_settings_patch.py:189-215` sends a new real token
  and asserts successful preview/redacted response.
- The focused bundled-Python test passed, proving this is the intended current
  contract rather than dead code.
- The responsible source, test, and architecture document are unchanged from
  HEAD, so the defect applies to both committed and overlay baselines.

Minimal reproduction: call the application-facade settings-patch preview with
`CoordinatorAuthToken` set to a non-placeholder string and observe success
while the request-side model has already carried the raw token.

Root cause: response redaction is treated as equivalent to keeping secrets out
of an untrusted browser-originated request boundary.

Competing hypotheses: response redaction prevents exposure is rejected because
the secret has already traversed the browser/request objects; hidden metadata
blocks the key is rejected by the focused passing test; this is only a test
artifact is rejected by the production candidate-builder path it exercises.

Applicable boundary: auth secrets and security-sensitive configuration remain
backend-owned and do not enter browser-controlled state.

Existing protection and gap: sensitive response values are redacted and the
placeholder is rejected. Neither control prevents a real token from entering
the browser request path.

Smallest safe remediation: make token rotation a distinct backend/native secret
input path, or reject these keys at every WebView settings patch boundary;
retain response redaction as defense in depth.

Required regression: browser-originated preview/save must reject both token
keys for real and placeholder values without echoing them into evidence,
journal, logs, or errors; an authorized non-browser rotation path must retain
its own strict tests.

Required validation rung: focused settings/API security tests, WebView request
inspection, log/journal redaction checks, packaged Tauri integration, and
strict packet coverage.

Related findings: original `SETTINGS-001`; no replacement ID issued.

Missing evidence and uncertainty: no live browser/devtools capture or packaged
token-rotation flow was executed. The prohibited request path and intended test
contract are source- and test-verified.

## CSW-2026-07-09-SETTINGS-002 — Legacy extras remain executable runtime configuration

- Severity: P1.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: still present; earlier inert-classification closure is disproven.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current applicability: committed HEAD and overlay; responsible files are
  unchanged.
- Workflows: WF-04 settings/profiles; WF-05–WF-09 media and publish policy;
  PASS-04 security; PASS-08 runtime consistency.
- Affected files: `src/mediapipeline/core/config/settings_store.py`,
  `ops/pipeline/engine/config/config_schema.ps1`,
  `ops/pipeline/engine/config/runtime_merge.ps1`, and settings inventory/tests.

Expected behavior: compatibility `legacy_extras` are inert preservation data,
or every executable runtime key is schema-registered, validated, documented,
and intentionally projected.

Actual behavior: the Python settings store merges every legacy extra into the
active PSD1 projection. PowerShell schema validation does not reject unknown
keys, and runtime merge converts every non-reserved config key into a script
variable. An actual-function no-write reproduction turned
`LegacyLabOnlyToggle='keep-for-projection'` into a live script variable.

Impact: stale, misspelled, retired, or externally introduced keys can influence
PowerShell behavior if any engine path consumes a matching script variable,
while operator documentation describes them as inert. This widens the active
configuration surface beyond the validated schema.

Supporting evidence:

- `settings_store.py:235-240` merges `legacy_extras` into the PSD1 projection.
- `config_schema.ps1:15-45` validates required/path/policy constraints but does
  not reject unknown keys.
- `runtime_merge.ps1:28-43` calls `Set-Variable -Scope Script` for every config
  key except a small reserved-name list.
- The API route inventory describes legacy extras as inert, and settings-store
  tests retain the value under the label `keep-for-projection`.
- A no-write PowerShell invocation of the actual merge function returned
  `{"Exists":true,"Value":"keep-for-projection"}`.
- Responsible implementation files are unchanged from HEAD.

Minimal reproduction: construct a config object with one arbitrary legacy
extra, call the actual runtime merge with a valid array-key set, and inspect
the script scope for the arbitrary variable.

Root cause: compatibility preservation, persisted projection, validation, and
runtime-variable materialization do not share an allowlisted authority model.

Competing hypotheses: the value is preserved only for round trips is rejected
by PSD1 projection and `Set-Variable`; schema validation removes unknown keys
is rejected by the validator; arbitrary names cannot affect behavior is not a
safety guarantee because current or future engine code can consume them.

Applicable boundary: settings schema/defaults/persistence and runtime overlay
evidence must keep authority explicit; unknown compatibility data must not
silently become executable policy.

Existing protection and gap: reserved runtime variable names are skipped and
known values receive validation. Unknown non-reserved keys remain accepted and
materialized.

Smallest safe remediation: serialize legacy extras separately from the active
PSD1/runtime projection and make runtime merge allowlist schema-owned keys;
provide an explicit migration for any intentionally restored key.

Required regression: unknown/retired/misspelled keys survive the compatibility
round trip if required but never appear in active PSD1 or script scope; every
registered key still projects and validates normally.

Required validation rung: settings-store/schema/runtime-merge unit and
integration tests, packaged configuration reload, representative policy
sampling, and strict packet coverage.

Related findings: original `SETTINGS-002`; no replacement ID issued.

Missing evidence and uncertainty: no current engine consumer of the synthetic
name was claimed and no production configuration was loaded. Executability of
arbitrary extras is reproduced; concrete field prevalence is unknown.

## CSW-2026-07-09-SETTINGS-003 — Cross-process settings saves can lose disjoint updates

- Severity: P1.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: partially fixed; single-process stale-save protection exists,
  but the cross-process race remains.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current applicability: committed HEAD and overlay; responsible file is
  unchanged.
- Workflows: WF-04 settings/profiles; WF-01 startup; PASS-05 data integrity;
  PASS-06 concurrency.
- Affected files: `src/mediapipeline/core/config/settings_patch_facade.py` and
  its tests.

Expected behavior: simultaneous settings saves either serialize across all
backend processes, fail one writer with a stale-authority conflict, or merge
non-conflicting updates without loss.

Actual behavior: save uses a process-local `threading.Lock`. Two facade
instances can both read the same authority digest before either writes, then
each construct a full candidate from its cached config and both report success.
The later full projection silently drops the other writer's disjoint change.

Impact: concurrent backends or helpers can acknowledge two successful settings
changes while persisting only one. The abnormal-shell-restart path documented
in `CPA-2026-07-19-004` makes multiple backend processes a credible operating
state, not merely an artificial unit-test topology.

Supporting evidence:

- `settings_patch_facade.py:187-257` acquires an instance/process-local lock,
  loads authority and compares its digest, builds from cached
  `resolved.config_data`, writes, releases the lock, and only then reloads.
- The existing sequential stale-authority test proves the earlier
  single-process overwrite was fixed but does not exercise simultaneous reads
  or separate locks/processes.
- A deterministic isolated two-facade reproduction synchronized both authority
  reads, applied disjoint `RoutingProfile` and `DebugMode` changes, and returned
  two successful saves/two writes.
- The final projection retained routing but restored `DebugMode=False`, proving
  one acknowledged update was lost.
- The responsible file is unchanged from HEAD.

Minimal reproduction: create two facades with separate locks over one isolated
authority, barrier both immediately after authority read, save disjoint keys,
and compare the two success responses with the final full projection.

Root cause: optimistic digest comparison and mutual exclusion are not atomic at
the shared filesystem authority; cached full-object writes amplify the race.

Competing hypotheses: the digest check prevents the race is rejected because
both checks precede both writes; the lock is global is rejected because it is
instance/process local; last-write-wins is acceptable is rejected because both
writers report success for disjoint changes; a second backend cannot exist is
rejected by `CPA-2026-07-19-004`.

Applicable boundary: settings persistence is atomic, provenance-bound, and
truthful across process lifecycle and duplicate-backend conditions.

Existing protection and gap: process-local serialization and sequential stale
digest rejection cover one facade. They do not create a cross-process lock or
filesystem compare-and-swap.

Smallest safe remediation: place the authoritative compare-and-write inside a
cross-process lock with atomic replacement, rebuilding from the just-read
authority; reject a changed digest rather than acknowledging an overwritten
update.

Required regression: deterministic two-process same-key and disjoint-key save
tests must yield serialization/merge or one explicit stale conflict, never two
successes with lost data; crash-before/after-replace recovery must preserve a
valid authority.

Required validation rung: focused settings concurrency tests using real
processes and isolated files, duplicate-backend integration, reload/restart
proof, and strict packet coverage.

Related findings: original `SETTINGS-003`; `CPA-2026-07-19-004` supplies the
credible multiple-backend path.

Missing evidence and uncertainty: the deterministic reproduction used isolated
in-memory services rather than two packaged backend processes. The race window
and lost-update result are proven; field frequency is unknown.

## CPA-2026-07-19-008 — Settings coverage inventories pass while their counts are stale

- Severity: P3.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: newly verified HEAD and overlay finding.
- First observed baseline: committed HEAD
  `a8bf6e1dda9629e6f818ba12f2c8274362923372`.
- Current applicability: committed HEAD and overlay; counted source and
  inventory files are unchanged.
- Workflows: WF-04 settings/profiles; PASS-02 contracts; PASS-07 test quality;
  PASS-10 release readiness.
- Affected files: settings field definitions and metadata plus
  `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md` and
  `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`.

Expected behavior: active settings inventories are generated or checked against
the current definitions/metadata and agree on backend key, binding, unique-key,
duplicate, and missing-structured-control counts.

Actual behavior: current source contains 206 backend keys, 156 metadata
bindings, 146 unique bindings, 10 duplicates, and 60 keys without a structured
binding. One matrix reports 205/156/146/10/59 and elsewhere calls the binding
count 155; the ownership map reports 204/155/145/10/59. Repository search found
no generator/check that rejects this drift.

Impact: release and audit reviewers can accept a green settings-coverage claim
while one or two backend keys and one binding are omitted from the documented
coverage denominator, weakening review of a high-risk configuration surface.

Supporting evidence: a read-only count over current definitions and metadata
returned `backend=206`, `bindings=156`, `unique=146`, `duplicates=10`, and
`missing=60`; both active inventories contain the contradictory counts; the
responsible files have no HEAD-to-overlay diff; no enforcing generator/check
was found.

Minimal reproduction: parse `CONFIG_FIELD_DEFINITIONS`, extract metadata
bindings, compute the five counts, and compare them to both active inventory
documents.

Root cause: manually maintained numeric summaries are not derived from or
validated against the authoritative definitions and metadata.

Competing hypotheses: the matrices intentionally use different scopes is
rejected because both describe the same backend/metadata contract without a
scope explanation; overlay drift explains it is rejected by unchanged files;
rounding explains it is rejected by exact integer claims.

Applicable boundary: additions to config keys and public settings surfaces must
update the matching inventory or generated contract in the same change.

Existing protection and gap: the inventories enumerate mappings and call out
duplicates/missing controls. No executable freshness assertion protects their
totals or rows.

Smallest safe remediation: generate the tables/counts from authoritative
definitions and metadata, or add a check that fails on any row/count mismatch.

Required regression: a fixture/addition/removal test must make the settings
inventory check fail until regenerated, including duplicate and missing counts.

Required validation rung: settings inventory generator/check, metadata and
field-definition contract tests, generated-context checks, and strict packet
coverage.

Related findings: `CPA-2026-07-19-001` is the analogous browser-smoke inventory
false-green but concerns a different generator and surface.

Missing evidence and uncertainty: this finding proves inventory drift, not a
runtime setting defect. Row-by-row semantic accuracy still requires the
remaining WF-04 trace.

## CSW-2026-07-09-PENDING-003 — Orphan reconcile remains unavailable from ordinary production discovery

- Severity: P3.
- Confidence: high.
- Status: verified, open; remediation not authorized.
- Disposition: still present; the earlier superseded/fixed classification is
  disproven.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current applicability: committed HEAD and overlay; responsible Python and
  WebView files are unchanged.
- Workflows: WF-09 publish/pending publish; PASS-02 contract consistency;
  PASS-07 test quality; PASS-09 operator UX.
- Affected files: `src/mediapipeline/core/publish/pending_paths.py`,
  `src/mediapipeline/core/repair_reconcile/dry_run_pending.py`,
  `apps/desktop/webview/static/assets/pendingPublishView.repair.js`, and
  pending-publish docs/tests.

Expected behavior: an exposed orphan-payload reconcile workflow either has a
production backend producer for its complete provenance-checked
`pending_push_manifest.v1` proposal, or clearly disables/labels the action as
unavailable until such evidence exists.

Actual behavior: ordinary pending discovery emits only payload facts and no
proposal. Repository search found proposal field names only in the dry-run
consumer; successful tests inject the proposal by replacing the production
preview. The WebView enables “Dry Run Orphan” for any selected row key, so the
normal orphan path deterministically returns blocked and can never enable
apply.

Impact: the operator is presented with a recovery workflow that cannot succeed
from normal product state. It creates a repeated diagnostic dead end and can
misdirect recovery effort, although the backend safely prevents guessed or
unsafe manifest creation.

Supporting evidence:

- `pending_paths.py:35-57` builds ordinary orphan rows with payload/size/error
  only and no backend proposal.
- `dry_run_pending.py:223-229` accepts only one of three proposal fields already
  present on the row; no production writer for those names exists elsewhere.
- Successful dry-run/apply tests manually inject `backend_manifest_proposal`
  into a preview row; the ordinary-orphan test asserts
  `proposed_manifest_available=false` and blocked.
- Focused current tests passed for both ordinary discovery and dry-run,
  confirming this is intentional current behavior rather than a stale branch.
- `pendingPublishView.repair.js:233-250` enables the dry-run from row selection
  alone while only apply is gated by a safe proposal-bearing result.
- Current status and contract docs explicitly say ordinary orphan rows remain
  blocked, but still describe the exposed reconcile surface as available.

Minimal reproduction: create an isolated orphan payload, obtain the normal
Pending Publish preview, submit its row key to the reconcile dry-run, and
observe blocked/no proposal; compare with the only successful tests, which
monkeypatch a proposal into that preview.

Root cause: the safe consumer/apply surface was promoted without connecting a
trusted transaction/evidence source that can construct proposals for normal
orphan rows, and UI availability does not reflect that missing capability.

Competing hypotheses: dry-run derives the proposal is rejected because it only
reads preexisting fields; normal scan supplies it is rejected by source/search
and focused tests; blocked is a valid successful recovery outcome is rejected
as an operability claim—fail-closed behavior is correct but the action remains
unusable; accepting browser-supplied proposal would fix it is rejected by the
backend-ownership invariant.

Applicable boundary: Pending Publish repair/reconcile remains backend-owned and
must never guess manifest authority from an orphan filename or browser payload.

Existing protection and gap: strict schema/path/size/sidecar validation,
fingerprint revalidation, confirmation, and manifest-only apply are strong.
They protect the mutation but do not provide or accurately expose production
eligibility.

Smallest safe remediation: disable/label orphan reconcile unavailable when the
selected backend row lacks a proposal, or add a narrowly scoped backend
producer derived from durable transaction/sidecar evidence. Do not relax the
proposal requirement.

Required regression: ordinary orphan rows must render an explicit unavailable
reason without offering a futile dry-run, while a genuine backend-proposal row
must complete dry-run/apply with exact fingerprint and unchanged media hashes.

Required validation rung: focused service/dry-run/WebView tests and strict
packet coverage; any new proposal producer additionally requires pending
fixture tests and representative deferred-publish/recovery/drain validation.

Related findings: original `PENDING-003`; no replacement ID issued.

Missing evidence and uncertainty: no live orphan was created and no mutation
route was invoked. The normal source-to-dry-run dead end is source- and
test-verified; field frequency is unknown.

## CSW-2026-07-09-RENAME-004 — Apply-history refresh re-enables an already completed rename undo

- Severity: P2.
- Confidence: high.
- Status: verified open.
- Disposition: still present.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current baselines: committed `HEAD` and working-tree overlay; responsible
  frontend files are unchanged from `HEAD`.
- Workflows: WF-10, PASS-02, PASS-03, PASS-06, PASS-09.
- Responsible files:
  `apps/desktop/webview/static/assets/renameHistoryView.js` and
  `apps/desktop/webview/static/assets/rename/commandEvidence.js`.

Expected behavior: once a rename undo succeeds, refreshing recent command
history must retain the completed/disabled undo state for that manifest. A
historical apply record must not be treated as fresh mutable authority.

Actual behavior: `renderRenameUndoResult()` sets `lastUndoCompleted=true`,
disables the Undo Last Apply button, and renders `Undo completed.`. The next
`renderRenameApplyHistory()` call takes the newest historical `rename.apply`
entry and unconditionally passes it back through `renderRenameApplyResult()`.
That function reloads the old manifest and resets `lastUndoCompleted=false`,
so the same manifest is presented as available again.

Impact: an ordinary history refresh or restart can contradict completed backend
state and invite a futile second undo. The backend manifest guard prevents the
second filesystem reversal, so this is a stale-authority/operator-trust defect,
not a demonstrated duplicate mutation.

Evidence: a Node VM execution of the actual two modules produced
`completed=true`, button disabled, and `Undo completed.` immediately after the
undo result; after rendering the historical apply entry it produced
`completed=false`, button enabled, `Undo available for the last apply.`, and
the same manifest path. The exact behavior exists in committed `HEAD` and the
overlay. The focused rename suite passed 57 tests but contains no
apply-success -> undo-success -> history-refresh assertion.

Minimal reproduction: load `commandEvidence.js` and `renameHistoryView.js` with
DOM stubs; render a successful apply carrying an undo manifest; render a
successful undo for it; then call `renderRenameApplyHistory()` with that apply
entry. Observe the completed flag and button state revert.

Root cause: the frontend projects the latest apply-only journal slice as the
current undo state without correlating later `rename.undo` evidence or querying
authoritative manifest status. The apply renderer also always clears the local
completion flag.

Competing hypotheses: history only renders text is rejected because it calls
the state-mutating apply renderer; the command journal updates the apply record
after undo is rejected because undo is a separate command result; a second undo
can mutate again is rejected by the backend completed-manifest guard; local
completion survives refresh is rejected by the actual-module reproduction.

Applicable invariant: generated/history evidence is not automatically
authoritative, and frontend state must not contradict backend-owned mutation
lifecycle.

Existing protection and gap: the backend rejects manifests whose
`undo_status` is already completed, and strict confirmation still applies. The
UI has no chronological apply/undo correlation or backend manifest-status
refresh, so it repeatedly offers an action backend authority will reject.

Smallest safe remediation: derive undo availability from the latest correlated
apply and undo evidence for the same manifest, or expose a read-only backend
manifest-status projection. At minimum, do not clear a completed flag when the
history entry names the same manifest.

Required regression: in both Node VM and real browser coverage, apply success
followed by undo success and command-history refresh must leave undo completed
and disabled. A restart/history-only case must reach the same state from
correlated backend evidence, while a newer distinct apply remains undoable.

Required validation rung: focused WebView state tests, browser rename smoke,
Local API command-journal correlation, backend already-undone rejection, and
strict change-packet coverage.

Related findings: original `RENAME-004`; no replacement ID issued.

Missing evidence and uncertainty: the stale state is reproduced with actual
frontend modules, but a packaged WebView refresh/restart was not run. Operator
frequency and the clarity of the backend rejection after a repeated click are
unknown.

## CSW-2026-07-09-NETWORK-001 — Token rotation can still commit before final join-blob validation

- Severity: P1.
- Confidence: high.
- Status: verified open.
- Disposition: partially fixed, still present.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current baselines: committed `HEAD` and working-tree overlay; responsible
  Network source files are unchanged from `HEAD`.
- Workflows: WF-11, PASS-03, PASS-04, PASS-05, PASS-08, PASS-11.
- Responsible files: `src/mediapipeline/core/network/facade.py`,
  `src/mediapipeline/core/network/join.py`, and
  `src/mediapipeline/core/network/auth.py`.

Expected behavior: rotate-and-create is one transaction. Every fallible blob
operation must succeed before config, app-state, or a running coordinator token
changes, or every changed authority must be restored before failure returns.

Actual behavior: the current fix preflights the blob with the literal
26-character token `preflight-token-0123456789`, then rotates/persists the real
token, then encodes again. Generated coordinator tokens are 64 hexadecimal
characters. A payload whose placeholder form is 32,731 decoded bytes passes the
32 KiB preflight, while the real-token form is 32,769 bytes and fails after the
token save. The error response contains no blob and no rollback is attempted.

Impact: at this narrow but valid payload boundary, a confirmed rotate request
can invalidate existing worker credentials immediately or at coordinator
restart without delivering the replacement secret. This is availability and
recovery loss, not media mutation.

Evidence: source order is preflight encode -> `_coordinator_join_token()` ->
final encode. `generate_token()` always returns 64 characters. An isolated
boundary construction using seven 3,990-character source roots plus one
3,819-character root measured 32,731 bytes with the placeholder and failed the
real-token encode at 32,769 bytes. The actual facade returned `ok=false`, no
blob, and `join_blob decoded payload is too large`, while the isolated settings
service recorded one successful changed-token save and no save restoring the
old token. Current responsible source matches committed `HEAD`.

Minimal reproduction: provide the near-limit library rows above; configure an
existing coordinator token; confirm rotate/create with a valid URL; observe
preflight success, token save, final size failure, no blob, and no rollback.

Root cause: preflight validates a surrogate secret of different serialized
length rather than preparing the exact candidate blob before mutation. The
exception handler reports failure but has no transaction/compensation context
for the already committed token.

Competing hypotheses: all inputs are prevalidated is rejected because serialized
size depends on the real token; generated token length matches the placeholder
is rejected by `token_hex(32)`; the size limit is unreachable is rejected by
the accepted eight-row fixture; save is rolled back is rejected by the single
changed-token save and source control flow.

Applicable invariant: auth/secret changes and lifecycle recovery evidence must
be atomic, truthful, and compensating; source media remains untouched.

Existing protection and gap: malformed URL/field inputs now fail before
rotation, and running-coordinator update failure attempts config/runtime
rollback. Final blob construction still occurs after mutation, outside those
compensation branches.

Smallest safe remediation: generate the exact candidate token without mutating
authority, encode and retain the complete candidate blob, then commit config,
app state, and runtime token as a compensating transaction. Do not return the
blob unless commit succeeds, and restore every changed authority on failure.

Required regression: near-limit placeholder/real-token cases and an injected
final-encode failure must leave config, app state, and running dispatcher token
unchanged. Settings-save and runtime-update failures must also prove restoration
and no secret leakage.

Required validation rung: focused join/settings/runtime transaction tests,
Local API secret/journal tests, two-process coordinator/worker auth recovery,
packaged restart, and strict change-packet coverage. No real media is required
unless worker execution policy is touched.

Related findings: original `NETWORK-001`; `NETWORK-003` compounds role
authority but is independently actionable.

Missing evidence and uncertainty: the commit call and missing rollback are
actual-facade reproduced with an isolated settings service; a real persisted
settings store and running two-host coordinator were not rotated. The normal
trigger is a narrow 38-byte serialized-size window near 32 KiB, so field
frequency is likely low but unmeasured.

## CSW-2026-07-09-NETWORK-003 — Coordinator join-blob creation still bypasses configured role authority

- Severity: P2.
- Confidence: high.
- Status: verified open.
- Disposition: still present.
- First observed baseline: 2026-07-09 full code sweep dirty overlay.
- Current baselines: committed `HEAD` and working-tree overlay; responsible
  Network source and route contract are unchanged from `HEAD`.
- Workflows: WF-11, PASS-02, PASS-04, PASS-08, PASS-09.
- Responsible files: `src/mediapipeline/core/network/facade.py`,
  `src/mediapipeline/desktop/api/contract_command_network.py`, and
  `apps/desktop/webview/static/assets/network/lifecycle.view.js`.

Expected behavior: the coordinator-named secret-creation route either requires
`NetworkRole=coordinator`, or is explicitly modeled, named, documented, and
tested as a separate offline bootstrap operation with its own authority rules.

Actual behavior: the facade reads the configured role only to echo it in the
response. It never gates the operation. The route contract and WebView likewise
expose Create Join Blob without a role precondition or documented offline
bootstrap policy.

Impact: any authenticated local caller in standalone or worker mode can rotate
coordinator token state and mint cluster credentials. This is a role-authority
bypass and confusing configuration mutation within the already authenticated
Local API boundary; it is not a remote unauthenticated exploit.

Evidence: an isolated actual-facade call with `NetworkRole=standalone` returned
success, reported role `standalone`, set `rotated=true`, produced a join blob,
and persisted a coordinator token in temporary app state. A second reproduction
through the actual loopback Local API returned HTTP 200 with the same role,
rotation, blob, and app-state mutation. Repository search found no active
offline-bootstrap policy or negative role test.

Minimal reproduction: start an isolated Local API resolved as standalone; POST
the coordinator join-blob route with a valid URL and both strict confirmations;
observe HTTP 200, a secret blob, and coordinator token state creation.

Root cause: route ownership, configured-role authority, and setup/bootstrap
policy are not encoded in a shared precondition. Route confirmation protects
secret transfer but is treated as sufficient authorization for any local role.

Competing hypotheses: a handler-level role gate is rejected by the Local API
reproduction; the WebView hides the route is rejected by its contract-based
enablement; offline minting is intentional is unresolved but unsupported by
the active contract/docs; authentication alone is sufficient is rejected by
the product's role-specific lifecycle and ownership model.

Applicable invariant: backend owns Network lifecycle and auth policy, and role
boundaries must be explicit rather than inferred by the frontend.

Existing protection and gap: Local API authentication, strict confirmation,
secret-safe unjournaled response handling, strong token generation, and field
bounds all remain effective. None establishes coordinator-role authority.

Smallest safe remediation: fail closed unless the resolved role is coordinator.
If offline bootstrap is genuinely required, create a separately named backend
route/contract with explicit preconditions, warnings, mutation scope, and
tests; do not silently overload the coordinator lifecycle route.

Required regression: standalone and worker roles reject create/rotate without
config/app-state/runtime writes; coordinator succeeds. Any explicit offline
bootstrap route must have separate confirmation, redaction, and lifecycle
interaction tests.

Required validation rung: facade and Local API role matrix, WebView route-state
tests, secret/journal checks, packaged setup flow, and strict packet coverage.

Related findings: original `NETWORK-003`; `NETWORK-001` is the independent
transactional rotation defect.

Missing evidence and uncertainty: actual facade and loopback route behavior are
reproduced, but no packaged UI click was used. Product intent for offline
credential minting is not documented, so the correct named policy requires an
owner decision during remediation.
