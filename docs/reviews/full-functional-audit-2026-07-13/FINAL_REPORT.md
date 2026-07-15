# Full Functional Touchpoint Audit — Final Evidence Report

Audit window: 2026-07-13 through 2026-07-14  
Repository: current MediaPipelineRemuxEncodeAIO workspace  
Primary change packet: `MP-CHANGE-2026-0713-006`

## Disposition

**The current source snapshot has a complete, zero-unclassified inventory of
970 authored WebView touchpoints. The broader audit is not eligible for the
requested “complete, non-destructive, exhaustive” claim.**

The authored-control censuses recorded 757 passed activations, 160 blocked
cases, 53 intentional skips, 0 remaining failed cases, and 0 unclassified
cases after remediation. Runtime-generated controls were also inventoried and
exercised using per-instance or normalized-family strategies described below.
Those strategies do not represent a literal Cartesian test of every possible
runtime state.

The original safety completion criterion is permanently unmet. Four audit
runs associated with `MP-CHANGE-2026-0712-020` accessed live/operator state:
operator media was read, and production runtime evidence was archived. No
evidence of source-media mutation was found during containment, but the audit
cannot claim that production state was neither accessed nor modified. Those
four runs are explicitly invalid and contribute no acceptance credit in this
report.

Representative real-media validation was not performed. FFmpeg route
decisions, output quality, subtitle/OCR behavior, audio policy, size policy,
and final publish behavior therefore remain outside the proof supplied here.

## Counting and evidence rules

The authoritative authored denominator comes from
`docs/generated/WEBVIEW_TOUCHPOINT_LEDGER.json`. Dynamic outcomes and blockers
are curated in `docs/inventories/WEBVIEW_TOUCHPOINT_EVIDENCE.json` and enforced
by the six census modules listed in the evidence catalog.

- An **authored touchpoint** is one source-authored interactive control. Each
  appears exactly once in the 970-control denominator.
- **Passed** means a physical browser or native input reached the expected
  stable state under the cited disposable fixture.
- **Blocked** means the control was classified but its exact supported
  precondition, full-effect isolation, dependency, visibility, or native
  accessibility could not be established. A blocked case is not a pass.
- **Skipped** means execution was intentionally withheld, including the two
  destructive controls and other controls whose external/native effect was
  outside the established fixture.
- Runtime-generated counts are reported separately. The root census contains
  896 app-wide shared layout/table/disclosure instances which overlap controls
  observed by the page-specific generated censuses. Accordingly, raw generated
  counts are **not summed into a misleading global total**.
- “All finite values” means all values of one finite control were exercised in
  isolation. It does not mean the full Cartesian product across all controls.

## Authored inventory

### Classification before execution

| Classification | Count | Meaning |
| --- | ---: | --- |
| Safe/read-only/local display | 874 | Navigation, display, filtering, sorting, or local staging |
| Safely reversible | 88 | Mutation can be safe only with the required isolated backend/state preconditions |
| Destructive | 2 | Verified-matrix deletion arm/action; dynamically skipped |
| Unreachable | 6 | Authored, disabled future Network controls |
| Unclassified | 0 | No authored control lacks a classification |
| **Total** | **970** | 967 main-SPA controls plus 3 Pipeline Log window controls |

The two destructive touchpoints are `Delete Verified Full Matrix` and its
`Delete Arm Text` confirmation input on Diagnostics. The six unreachable
touchpoints are the authored future Network actions `Abort Current`, `Disable
New Work`, `Drain`, `Pause`, `Quarantine Worker`, and `Reclaim Job`.

### Denominator by surface

| Surface | Authored controls | Surface | Authored controls |
| --- | ---: | --- | ---: |
| App shell | 32 | Completed | 37 |
| Home | 49 | Pending Publish | 31 |
| Launch | 36 | Rename | 39 |
| Metrics | 17 | Reports | 87 |
| Queue | 98 | Network | 82 |
| Libraries | 17 | Schedule | 10 |
| Settings | 324 | Diagnostics | 75 |
| Maintenance | 30 | Settings save dialog | 3 |
| Pipeline Log window | 3 | **Total** | **970** |

### Curated dynamic outcomes without double counting

| Census partition | Authored denominator | Passed | Blocked | Skipped | Failed / unclassified |
| --- | ---: | ---: | ---: | ---: | ---: |
| App shell + Launch + Queue + Rename | 205 | 157 | 30 | 18 | 0 / 0 |
| Settings + Libraries + Schedule | 351 | 285 | 66 | 0 | 0 / 0 |
| Completed + Pending Publish + Reports + Network | 237 | 189 | 15 | 33 | 0 / 0 |
| Home + Metrics + Diagnostics + Maintenance + Settings save dialog | 174 | 123 | 49 | 2 | 0 / 0 |
| Auxiliary Pipeline Log window | 3 | 3 | 0 | 0 | 0 / 0 |
| **Total** | **970** | **757** | **160** | **53** | **0 / 0** |

The root census physically discovered 206 authored nodes, including the same
32 App-shell controls already owned by the workflow census. Its raw outcome was
153 activated, 51 blocked, and 2 destructive skips. The table subtracts the
duplicated App-shell result (30 activated and 2 blocked), leaving the 174
unique controls shown above.

The Settings/Libraries/Schedule browser run itself emitted 285 activated, 54
skipped, and 12 blocked outcomes. During evidence curation, all 66
non-activations were normalized to **blocked** because none had earned full
effect acceptance credit: they lacked an exact isolated backend mutation,
path-picker, upstream-selection, persistence, or rollback precondition. This
preserves the raw run while preventing a skipped safe control from appearing
equivalent to a destructive skip.

No product case is classified as flaky. Transient UI Automation enumeration
was handled by bounded retries, and the separate fixed9 cleanup timeout is
reported as a harness incident below rather than as a product pass.

## Runtime-generated and conditional controls

Generated controls depend on backend payloads, list sizes, profiles, layout
state, and conditional rendering. The censuses use stable family IDs and
instance counts so repeated rows are not confused with distinct authored
controls.

| Census | Runtime scope | Outcome |
| --- | --- | --- |
| Launch/Queue/Rename workflow | 168 generated controls plus 17 global keyboard-shortcut cases | 168/168 controls activated; 17/17 shortcuts passed |
| Completed/Pending/Reports/Network | 715 generated instances normalized into 149 families | 692 activated, 19 blocked, 4 skipped, 0 failed/unclassified |
| Settings/Libraries/Schedule | 1,145 generated instances in 36 families | 953 activated, 173 blocked, 19 skipped, 0 failed/unclassified |
| Root surfaces | 1,129 raw instances normalized into 87 stable records | 80 family records activated, 7 blocked, 0 skipped/failed/unclassified |

The final ledger contains 987 accounting records: 970 authored static
controls, 12 runtime-generated aggregate records, and 5 native-family records.
Their `instance_count` values total 4,180 evidence-accounting observations:
970 static, 3,174 runtime-generated, and 36 native. Record-level outcomes are
765 passed, 165 blocked, and 57 skipped; instance-weighted outcomes are 3,741
passed, 363 blocked, and 76 skipped. Zero are unclassified. These are not
4,180 unique rendered controls or individual physical activations: shared
generated families overlap across runs, and some family passes use
representative activation strategies as described below.

The root denominator consists of 78 page-owned records covering 233 instances
and 9 shared families covering 896 instances. Nineteen page-owned row families
exercised every enabled instance with click, Enter, and Space. The nine highly
repetitive shared layout/table/disclosure families used representative
activation and restoration. Therefore, “80 activated records” describes 80
successful family strategies; it does not assert that all 1,129 raw nodes were
individually clicked.

The root census's 896 shared instances include panel movement, Advanced/hidden
gates, disclosures, column menus, column visibility, sorting, and resizing
across the app. Those same kinds of nodes appear in the Settings, evidence, and
workflow generated runs. This report preserves each run's denominator and does
not add 168 + 715 + 1,145 + 1,129 as though they were disjoint controls.

Combined authored/generated evidence-page outcomes were:

| Surface | Cases | Activated | Blocked | Skipped |
| --- | ---: | ---: | ---: | ---: |
| Completed | 280 | 267 | 6 | 7 |
| Pending Publish | 166 | 160 | 2 | 4 |
| Reports | 285 | 259 | 12 | 14 |
| Network | 221 | 195 | 14 | 12 |
| **Total** | **952** | **881** | **34** | **37** |

## Configuration and state coverage

The configuration matrix used exhaustive finite-domain coverage per control
and modeled coverage for independent or unbounded dimensions. It was not a
full Cartesian product.

- The 351 authored Settings/Libraries/Schedule controls included 107 finite
  domains: 69 checkboxes were driven through both values and 38 enabled selects
  through every enabled option. Five additional selectors were asserted
  disabled in their supported fixture state.
- The 1,145 generated Settings/Libraries/Schedule instances included 214
  finite or bounded editable domains: 53 checkboxes, 46 selects, 19 radios, 52
  numeric inputs, and 44 text inputs. Booleans and finite enums were exhaustive
  per control; numeric and text fields used boundary or representative
  edit-and-restore cases.
- All 336 half-hour Schedule blocks and all 28 day actions were activated. All
  154 generated Library override controls were activated. Reset controls whose
  values were inherited and unavailable remained blocked rather than having
  state manufactured around their guards.
- The root census covered 39 authored and 16 generated finite domains. It used
  both boolean states, every enabled select value, and representative/boundary
  edits for unbounded inputs.
- Empty, selected, multi-row, disabled, hidden, available/unavailable,
  read-only, success, failure/retry, and representative busy states were
  exercised where the disposable fixture could create them through supported
  UI/backend behavior.
- Native or OS path pickers, unsupported backend mutations, hidden recovery
  controls without a real precondition, and unavailable external dependencies
  remained blocked or skipped. Guards and confirmations were not bypassed.

Source/output snapshot proofs in the generated Settings census retained seven
disposable media/sidecar files byte-for-byte. Browser censuses rejected or
intercepted prohibited non-read requests and recorded zero operator-path
window opens. These fixture proofs do not repair or erase the separate live
boundary breach disclosed below.

## Native Tauri/WebView2 results

### Clean isolated navigation pass

The successful isolated native run used:

- audit root:
  `C:\Users\lmmye\AppData\Local\Temp\MP-tauri-uia-final-20260713-235928-429d1e5d`
- verified WebView2 user-data directory beneath that root:
  `WebView2\EBWebView`
- 350 UI Automation elements inspected
- 15 primary destinations activated with Enter and the same 15 activated with
  Space: **30/30 passed**
- source/output file count: 0 before, 0 after
- main-window/process cleanup: passed

Each keyboard case established a different sentinel page, focused the target
navigation control, posted the key, and verified that the target became active
while focus remained on the target. The native probe now fails closed if the
observed WebView2 `--user-data-dir` is not equal to or beneath the expected
isolated root.

### Pipeline Log secondary window

After the Tauri permission repair, invoking `Open Log Window` from the native
shell opened a secondary window titled `Pipeline Log`. That proves the custom
command/window boundary. It does not prove the three secondary-window controls
through native UI Automation:

- The secondary WRY WebView exposed only one `WRY_WEBVIEW` pane to UI
  Automation, so `Follow`, display mode, and `Refresh Now` were not individually
  discoverable. Native content accessibility is **blocked**.
- A native close request was posted, but UI Automation and Win32 visibility did
  not prove that the independent secondary window became hidden or destroyed.
  Independent-close verification is **blocked**.
- The three controls themselves were separately exercised in the disposable
  browser/API Pipeline Log census, including both Follow states, both display
  modes, refresh loading/success/failure/retry, and unchanged media hashes.

The native command-open observation is accepted only for opening the secondary
window. It is not promoted into evidence for the inaccessible content controls
or independent-close behavior.

## Deterministic findings repaired during the audit

### AUDIT-001 — Completed evidence-row selection referenced unavailable aliases

**Observed:** Selecting a Completed size-evidence row reached
`selectCompletedSizeEvidenceRow` and attempted to call
`captureCompletedReviewSelectionScroll` /
`restoreCompletedReviewSelectionScroll`, which were not available in that
module scope. The resulting reference failure interrupted the promised row
selection/render/scroll-restoration sequence.

**Repair:** `metricsValidation.js` now uses the injected
`captureSelectionScroll` and `restoreSelectionScroll` aliases. The
Completed/Pending/Reports/Network census then completed with no failed or
unclassified case; Completed recorded 267 activated cases out of 280 combined
authored/generated cases, with the remaining 13 explicitly blocked/skipped.

**Regression evidence:**
`tests/webview/test_webview_browser_evidence_control_census.py` and
`apps/desktop/webview/static/assets/completed/review/metricsValidation.js`.

### AUDIT-002 — Remote Tauri WebView lacked permission for its custom command

**Observed:** Native `Open Log Window` failed deterministically with
`open_pipeline_log_window not allowed. Plugin not found`. The backend-served
loopback WebView was a remote Tauri origin, while the custom command was not in
the generated application manifest/capability permission set.

**Repair:** `src-tauri/build.rs` registers `open_pipeline_log_window` in the
Tauri application manifest, and `src-tauri/capabilities/default.json` grants
`allow-open-pipeline-log-window` to the existing loopback remote capability.
The bridge still uses browser fallback when the Tauri API is unavailable.

**Regression evidence:** Nine Pipeline Log static tests passed, including exact
command registration, permission, remote URL scope, exact no-argument invoke,
and browser fallback. Repeated native observation confirmed that the titled
secondary window opens. Native content and independent close remain blocked as
documented above.

## Safety incident register

### SAFETY-001 — Live production runtime and operator-media access

This is a confirmed breach of the audit's disposable-root-only boundary and a
permanent limitation on the original completion claim.

Four runs recorded in `MP-CHANGE-2026-0712-020` are **INVALID** and excluded
from all acceptance totals:

1. A live Diagnostics lifecycle reconciliation preview read production runtime
   state under `E:\Videos\Scratch\State`.
2. A live Diagnostics lifecycle reconciliation apply archived production
   runtime evidence under `E:\Videos\Scratch\State`, changing production
   runtime state.
3. A Reports source scan read operator-configured outsource and shared media
   roots.
4. A Reports audit start read 3,144 operator media records from live roots.

Containment identity-checked and stopped Local API PID 22060; the recorded
audit child PID 32568 had already ended. **No evidence of source-media mutation
was found, but operator media was read and production runtime state was
changed.** “No evidence found” is not represented as proof that no other read
or side effect occurred. The affected runs remain invalid even though later
hermetic regressions passed.

### SAFETY-002 — Existing LocalAppData WebView2 profile was accessed

An earlier native attempt omitted the isolated WebView2 user-data override and
caused WebView2 to read/write the existing application profile at
`%LOCALAPPDATA%\com.mediapipeline.remuxencodeaio\EBWebView`. The accessed/leaked
UDF tree was later removed during containment. This attempt is excluded from
native acceptance evidence. Later native evidence used an explicit disposable
user-data root and verified the observed `--user-data-dir` before crediting the
run.

No operator media root was involved in this incident, but accessing an existing
application profile still violated the required isolation boundary.

### SAFETY-003 — Isolated fixed9 process tree survived an outer timeout

The fixed9 native debug command used only the disposable root
`C:\Users\lmmye\AppData\Local\Temp\MP-tauri-log-debug-20260714-001443-4e811967`.
An outer command timeout interrupted the probe before its `finally` cleanup,
temporarily leaving the isolated npm/Tauri/backend/WebView2 process tree alive.

Cleanup identity-checked npm root PID 45784, Tauri PID 30464, the descendant
relationships, and the isolated WebView2 user-data command lines. Fourteen
tracked processes were force-stopped. A follow-up query, excluding the cleanup
shell, reported `residue_count=0` for both the fixed9 root and the disposable
Tauri executable. No operator media roots were involved.

The harness now uses one bounded tracked-process wait and immediately forces
the isolated tree after the graceful-close timeout. Parser/static regression
checks pass. The timed-out fixed9 invocation is not treated as a clean
end-to-end native pass; only separately verified observations are cited.

## Evidence catalog

| Evidence | Scope |
| --- | --- |
| `docs/generated/WEBVIEW_TOUCHPOINT_LEDGER.json` | Stable authored IDs, source/handler mapping, safety classification, expected transition, required evidence, aggregate counts |
| `docs/inventories/WEBVIEW_TOUCHPOINT_EVIDENCE.json` | Curated dynamic outcome/blocker overlay and generated/native family evidence |
| `tests/webview/test_webview_browser_shell_launch_queue_rename_control_census.py` | 205 authored workflow controls, 168 generated controls, 17 shortcuts |
| `tests/webview/test_webview_browser_settings_control_census_smoke.py` | Exact 351 authored Settings/Libraries/Schedule census |
| `tests/webview/test_webview_browser_settings_generated_control_census.py` | 1,145 generated controls, finite domains, source/output hash proof |
| `tests/webview/test_webview_browser_evidence_control_census.py` | 952 authored/generated Completed/Pending/Reports/Network cases |
| `tests/webview/test_webview_browser_root_control_census.py` | 206 authored nodes and 87 normalized generated records / 1,129 raw instances |
| `tests/webview/test_webview_browser_pipeline_log_window_control_census.py` | Three auxiliary Pipeline Log controls and retry/state coverage |
| `tests/webview/test_webview_pipeline_log_window_static.py` | Tauri command permission, exact invocation, and browser fallback regression |
| `apps/desktop/tauri/Test-TauriShell-WebViewUiAutomationProbe.ps1` | Isolated UDF check, 30 keyboard navigation cases, secondary-window probe, bounded cleanup |
| `%TEMP%\MP-settings-libraries-schedule-control-census.json` | Transient exact authored Settings census payload |
| `%TEMP%\MP-generated-settings-census-evidence.json` | Transient generated Settings census and unchanged-file hashes |
| `%TEMP%\mediapipeline-root-control-census-evidence.json` | Transient root authored/generated census payload |
| `ops/release/changes/unreleased/MP-CHANGE-2026-0712-020.json` | Permanent live-boundary incident and invalid-evidence record |

Transient `%TEMP%` files are reproducibility aids, not the sole durable
authority. The tracked overlay and test assertions carry the durable synopsis.

## Validation ledger

The following results are part of the final accepted evidence set:

| Validation | Outcome |
| --- | --- |
| Authored Settings/Libraries/Schedule census | PASS — 351 classified; 285 physical activations; 0 failed/unclassified |
| Generated Settings/Libraries/Schedule census | PASS — 1,145 classified; 953 activated; 0 failed/unclassified |
| Workflow census | PASS — 205 authored + 168 generated + 17 shortcuts; 0 failed/unclassified |
| Evidence-page census | PASS — 952 authored/generated; 881 activated; 0 failed/unclassified |
| Root census | PASS — 206 authored and 87 normalized generated records; 0 failed/unclassified |
| Pipeline Log browser census | PASS — all 3 controls exercised |
| Pipeline Log static regression | PASS — 9 tests |
| Native isolated navigation | PASS — 30/30 Enter/Space cases; isolated UDF verified; clean run cleanup passed |
| Native Pipeline Log content accessibility | BLOCKED — secondary WRY content not exposed to UI Automation |
| Native independent Pipeline Log close | BLOCKED — close request posted, hidden/destroyed state not proven |
| fixed9 timeout containment | PASS — 14 tracked processes stopped; follow-up residue count 0 |

Final reconciliation and regression gates:

| Final validation | Outcome |
| --- | --- |
| Touchpoint ledger generator/check and overlay integrity | PASS — 987 records, 4,180 observations, zero unclassified; 18 focused tests passed |
| Full targeted census re-run after the final overlay | PASS — all 6 browser census modules in 136.44s |
| Broader touchpoint regressions | PASS — 155 tests plus 530 subtests in 54.88s |
| Frozen CSV-rerun lifecycle suite | PASS — 202/202 in 65.797s with all 431 dirty-file SHA-256 hashes unchanged and zero paths added/removed; 202/202 passed again in 77.343s after the read-only evidence dependency extraction |
| Supplemental API, close-readiness, coordinator, audit, spawn, and mutation-boundary suite | PASS — 232 tests plus 1,418 subtests in 15.96s |
| PowerShell rerun recovery and destination checks | PASS — AutoDestination once and Recovery three consecutive times; 0/13 hash drift, zero new residue/processes/mappings |
| PowerShell source-identity and PlanOnly checks | PASS |
| Tauri `CheckOnly`, `cargo fmt --check`, locked `cargo check`, and locked tests | PASS — 48 Rust tests |
| WebView prework gate | PASS — 1,387/1,387 warning budget, zero errors, current maps/contracts/routes/commands/touchpoints, 282 scripts loaded |
| Dependency-boundary enforcement | PASS — 39 existing findings allowlisted; zero unallowlisted findings after extracting shared read-only rerun evidence |
| Generated-summary and navigation checks | PASS — 2,377 source files current, zero orphan summaries, and current project/dependency indexes |
| `git diff --check` | PASS |
| AI guardrail postflight | PASS after final reconciliation |
| Strict change-packet worktree coverage | PASS — 547/547 changed paths covered by unreleased packets; zero uncovered |
| Final dirty/uncovered-path inventory, separating unrelated user changes | PASS — 450 tracked-dirty plus 97 untracked paths; zero uncovered. Paths outside packets 006/007 remain attributed to their existing unreleased packets and were not absorbed into these packets. |

## Change packets

| Packet | Role | Final status |
| --- | --- | --- |
| `MP-CHANGE-2026-0713-006` | Touchpoint ledger, browser/native evidence, regressions, and this report | Complete; all scoped implementation, generated-context, strict-coverage, and postflight gates pass, with native/real-media limits retained |
| `MP-CHANGE-2026-0713-007` | CSV rerun lifecycle/source-recovery remediation exercised by related UI evidence | Complete; Python/WebView, PowerShell, API, close-readiness, dependency-boundary, Tauri, generated-context, strict-coverage, and postflight gates pass |
| `MP-CHANGE-2026-0712-020` | Lifecycle/Tauri contract remediation and permanent incident record | Complete; its four live-system runs are invalid and excluded |

No commit was created.

## Validation not performed and remaining work

- No representative real-media validation was run. The validation-ladder
  real-media worksheet remains required before claiming FFmpeg/media-policy,
  subtitle/OCR, audio, size, or publish correctness.
- Blocked safe/reversible controls were not converted into passes by directly
  calling APIs or manufacturing backend state. Each requires a future
  disposable-root scenario that proves its full effect and supported rollback.
- Native Pipeline Log content accessibility and independent-close behavior
  require a native automation surface or harness capable of observing the
  secondary WebView controls and window destruction.
- The settings/configuration coverage is per-control exhaustive for finite
  domains and boundary/representative for unbounded domains. A full Cartesian
  product was intentionally not run and is not claimed.
- Clean-machine installation/package-open behavior is not established by the
  browser censuses or the debug-shell UI Automation run.

## Final conclusion

This work provides an exact authored-control inventory, zero unclassified
authored touchpoints, reproducible census assertions, deterministic fixes for
two observed control failures, and substantially stronger native isolation and
cleanup checks. It does **not** satisfy the original audit's complete
non-destructive completion criteria because production runtime state was
accessed and modified, operator media was read, safe/full-effect cases remain
blocked, native secondary-window behavior remains partially unobservable, and
representative real-media validation was not performed.

Invalid evidence is disclosed and excluded rather than used to close those
gaps.
