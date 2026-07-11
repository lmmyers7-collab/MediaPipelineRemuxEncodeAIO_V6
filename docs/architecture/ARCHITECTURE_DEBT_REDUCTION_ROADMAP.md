# Architecture Debt Reduction Roadmap

Status: active roadmap (2026-07-11). This is a finite delivery plan, not a
claim that the program is complete. Each numbered slice requires its own
change packet; do not combine slices merely to improve aggregate counts.

## Operating direction

The intended dependency direction is:

```text
contracts / kernel value objects / pure domain helpers
  <- core domain services and policies
  <- desktop adapters and Local API
  <- WebView and Tauri presentation
```

`contracts` must not import core behaviour. Core must not import desktop. A
low-level helper belongs beside its established owner (for example,
`core.network` for network protocol policy), not in a new generic shared,
common, or facade namespace. The WebView remains a renderer and intent
stager; backend and PowerShell retain all media, filesystem, process, and
strict-confirmation authority.

Every dependency slice must reduce either allowlisted hard findings or the
package SCC membership, introduce none, and update the allowlist only after
the checker proves the removed edge is gone. Each direction change records its
owner, rationale, rollback, characterization tests, and checker delta in that
slice's change packet.

## Reproducible 2026-07-11 baseline

Run from repository root with the bundled runtime:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.check_dependency_boundaries --format json --report-only
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.check_godfiles --all --strict --json
```

The dependency result has 3,065 internal imports, zero module cycles, one
package SCC, 39 hard findings, all 39 specifically allowlisted, zero
unallowlisted findings, zero unused allowlist entries, and 39 warnings. The
SCC contains 13 packages:

`audit`, `completed`, `config`, `final_library`, `network`, `observability`,
`processes`, `publish`, `queue`, `rename`, `status`, `subtitles`, and
`telemetry` (all below `mediapipeline.core`).

The SCC entry packages are `api`, `application`, `diagnostics`, `library`,
`maintenance`, `metrics`, `orchestration`, `repair_reconcile`, and
`sample_validation`. Their 15 incoming package edges carry 142 imports; the
largest are `api -> queue` (53), `orchestration -> config` (20), `api ->
config` (12), and `api -> rename` (11). These are entry points for callers,
not permission to couple the owning domains further.

### Allowlisted hard-edge inventory

The following is the complete baseline. `A -> B` means A imports B. The
source of truth is still
`docs/architecture/dependency_boundary_allowlist.txt`; this table is a dated
snapshot for measuring reduction.

| Rule | Edge(s) |
| --- | --- |
| package cycle | `config -> processes`; `processes -> config` |
| config upward | `config.metadata_parts.advanced_fields -> rename.constants`; `config.metadata_parts.advanced_fields -> rename.movie`; `config.metadata_parts.advanced_fields -> rename.tv`; `config.settings_facade -> processes.path_evidence`; `config.settings_patch_candidate_facade -> rename.policy` |
| package cycle | `audit -> completed`; `audit -> processes`; `completed -> observability`; `completed -> publish`; `config -> network`; `config -> rename`; `final_library -> completed`; `final_library -> config`; `network -> config`; `network -> processes`; `observability -> telemetry`; `processes -> audit`; `processes -> completed`; `processes -> final_library`; `processes -> network`; `processes -> status`; `publish -> completed`; `queue -> config`; `queue -> observability`; `queue -> status`; `queue -> subtitles`; `rename -> queue`; `status -> observability`; `status -> processes`; `status -> rename`; `status -> telemetry`; `telemetry -> config` |
| package cycle | `completed -> subtitles`; `subtitles -> completed` |

The current checker records repeated AST-level evidence for a few config
imports, but the inventory deliberately lists each allowlist key exactly once.

### File-size baseline

The all-source guard reports 319 findings (176 warning, 143 maximum errors).
Excluding `tests/**` and `ops/pipeline/tests/**`, production code has 211
findings: 115 warnings and 96 files above their maximum. Default ceilings are
500/900 lines; Python and PowerShell production ceilings are 450/800; WebView
is 500/900. `app.js` and `settingsView.js` have temporary, documented 1,500 /
4,600 ceilings and are still warnings, not proof that their split campaigns
completed.

The 96 production maximum findings are distributed as WebView 34, core 31,
PowerShell engine 13, desktop 6, contracts 3, entrypoints 3, tooling 4,
pipeline 1, and release 1. Initial prioritization is based on mixed ownership
and active defects rather than raw line count: `core.network.facade.py`
(2,084), `pendingPublishView.js` (1,818), `scheduleView.js` (1,796),
`telemetryView.js` (1,064), `core.completed.policy.py` (1,622), and the
network desktop/runtime pair. The full machine-readable baseline is generated
by the second command above; do not hand-maintain a copy.

### Duplicate inventory

These pairs are byte-identical and have competing owners today:

| Canonical owner to establish | Duplicate pair |
| --- | --- |
| core network protocol policy | `core/network/auth.py` and `desktop/network/auth.py` |
| core network path-map policy | `core/network/path_map.py` and `desktop/network/path_map.py` |
| core network library-root policy | `core/network/library_roots.py` and `desktop/network/library_roots.py` |
| core network failure vocabulary | `core/network/failure_reasons.py` and `desktop/network/failure_reasons.py` |
| core strict network JSON policy | `core/network/json_policy.py` and `desktop/network/json_policy.py` |

Near duplicates are `protocol.py`, `registry.py`, and `worker_state.py` in the
same two packages. The desktop forms contain adapter-only additions, so their
shared pure portion must be characterized and imported from core while the
desktop-only lifecycle, HTTP, threading, and state adaptation remain desktop.

Additional duplication candidates are the atomic/JSON helpers in core audit,
config, failures, folder policy, processes, queue, rename, and schedule;
PowerShell entrypoint `Write-JsonAtomic` functions; `Audit-MediaLibrary.ps1`
and engine naming season/Specials parsing; and audit-entrypoint versus engine
audio ranking. No helper moves until its precise atomic replacement, encoding,
path-boundary, and error-message contract is characterized.

### UI and test baseline

Static partials contain 15 top-level pages, 531 panels, 425 buttons, 277
inputs, 87 selects, 28 textareas, and 58 explicit `tabindex` attributes.
Affected pages currently have:

| Page | Panels | Native controls | Explicit tabindex/interactive role |
| --- | ---: | ---: | ---: |
| Pending Publish | 47 | 23 | 2 / 2 |
| Schedule | 14 | 6 | 4 / 4 |
| Telemetry | 10 | 0 | 0 / 0 |

Schedule adds its 336 time-cell controls at runtime; therefore the browser
measurement, not this static count, is the acceptance metric. Existing seams
include `test_webview_schedule_smoke.py`,
`test_webview_browser_schedule_smoke.py`,
`test_webview_browser_telemetry_smoke.py`,
`test_webview_browser_pending_drain_guard_smoke.py`,
`test_application_facade_web_static_pending_publish.py`, pending-publish
service/manifest/path tests, `test_network_*.py`, `test_service_rename_tv.py`,
and PowerShell naming/audio checks. Each implementation slice must add the
missing characterization test before moving production behaviour.

The current Pending partial has a `role=button tabindex=0` container around
native buttons and a second clickable live-state chip. Schedule uses a
sequential 336-control grid. Telemetry has a canvas history without a complete
text equivalent. These are the accessibility targets; they do not authorize a
change to schedule persistence, drain authority, or telemetry backend schema
unless a later bounded slice demonstrates that it is required.

### Documentation reality check

The old architecture-boundary and god-file completion plans are archived
evidence, not current status. The current checker contradicts any wording that
implies cleanup has finished: 39 allowlisted hard findings, one 13-package SCC,
and 96 production maximum-size files remain. A documentation slice must correct
the canonical current-state/checklist/architecture wording after each completed
slice; it must not revive archived plans or edit generated files by hand.

## Ordered execution slices

1. **Contract/config/rename seam.** Characterize metadata defaults and patch
   validation; move only rename-independent values and pure TV-name inputs to
   the low owner. Target the five config-upward allowlist keys. Roll back by
   restoring the former import and allowlist key in the same packet.
2. **Config/process/network seam.** Extract a narrowly named path-evidence
   value object or read-model at its actual low-level owner, then remove the
   config/process package pair and at least one network/config direction. No
   desktop import is permitted. Validate settings, process launch, and network
   tests plus checker deltas.
3. **Completed/publish/subtitles seam.** Separate completed read evidence from
   publish action policy and subtitle QA. This must remove at least one of
   `completed <-> publish` or `completed <-> subtitles`; any PowerShell
   pending-publish transaction change is out of scope and requires the
   no-touch gate plus real-media validation.
4. **Network duplication consolidation.** Add characterization tests, make the
   five exact pure modules core-owned, then convert desktop copies to permitted
   imports/thin adapters. Do protocol/registry/worker-state only as later
   sub-slices. Preserve JSON strictness, atomic replacement, auth and
   path-boundary behaviour.
5. **TV/audio/audit helper consolidation.** Characterize season-zero/Specials
   and audio-rank edge cases before making the canonical engine helper callable
   by audit. Do not touch FFmpeg/audio policy; this slice is parsing/ranking
   consistency only.
6. **God-file wave A.** Split `core.network.facade.py` by pure contracts,
   registry orchestration, and desktop-facing adapter boundary, together with
   focused tests. It must reduce a max finding and not add a cycle.
7. **Task-page wave B.** Split Pending Publish, Schedule, and Telemetry only at
   rendering/model/interaction boundaries needed by their accessibility work;
   preserve public exports and add no pass-through-only files.
8. **Pending Publish UX/accessibility.** Make action containers noninteractive,
   retain explicit row-selection controls, put secondary evidence behind the
   existing Advanced disclosure, and measure control/tab/task deltas. Do not
   change drain semantics, strict confirmations, or backend authority.
9. **Schedule accessibility.** Replace sequential cells with a roving-focus
   grid/range editor that documents arrow keys, selection state, and screen
   reader instructions while submitting the identical backend grid contract.
10. **Telemetry accessibility and density.** Add a bounded text summary
    (range, min, average, max, latest, trend) and accessible expandable table;
    retain canvas as supplementary evidence. Then update canonical status and
    checklist with actual residual debt and refresh inventories/summaries.

Slices 1 -> 3 are serial SCC reduction. Slice 4 may begin after slice 2's
direction contract stabilizes. Slice 5 is independent after its
characterization work. Slices 7 -> 10 are serial because they share WebView
assets and metrics; slice 6 can proceed independently of the UX work. Every
slice reruns targeted tests, dependency checker, changed-file god-file check,
relevant static/browser/accessibility tests, WebView prework/script-order
checks where applicable, summary refresh, inventories, guardrail postflight,
and strict change-packet validation.

## Plan mutation protocol

Split a slice if it touches a no-touch boundary, does not lower its stated
metric, or needs a new behavioural product decision. Insert the new slice with
its own baseline and change packet; do not silently reclassify a failed slice
as complete. The program is complete only when the final checker and size/UI
measurements satisfy explicitly approved residual targets—not when this roadmap
exists.
