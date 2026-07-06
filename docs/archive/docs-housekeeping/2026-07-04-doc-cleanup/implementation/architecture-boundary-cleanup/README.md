# Architecture Boundary Cleanup Planning Pack

Date: 2026-06-28
Status: planning only
GitHub issue: #23
Change packet: MP-CHANGE-2026-0628-014

## Purpose

This planning pack describes how to retire the `NO_CORE_TO_DESKTOP`
architecture-boundary debt without mixing it with CI/runtime cleanup.

The target outcome is a one-way Python backend dependency graph:

```text
mediapipeline.desktop adapters
  -> mediapipeline.core domain services
  -> mediapipeline.contracts / core kernel contracts
```

The problem tracked by #23 is the reverse direction: many
`src/mediapipeline/core/**` modules still import
`mediapipeline.desktop.*` compatibility DTOs, models, API helpers, network
helpers, and subprocess helpers. Most of those imports are currently
allowlisted as known debt, but they keep the core layer coupled to desktop
adapter code.

This pack is subordinate to:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/architecture/dependency_boundary_allowlist.txt`
- `docs/implementation/architecture-boundary-cleanup/EDGE_LEDGER.md`
- `src/mediapipeline/tools/dev/check_dependency_boundaries.py`
- `src/mediapipeline/tools/dev/check_architecture_guardrails.py`

If this pack conflicts with those authority docs or executable source/tests,
stop and update the stale planning text before continuing.

## Non-Goals

- No media-policy changes.
- No FFmpeg, subtitle, audio, publish/drain, rename, source/scratch/output, or
  cleanup behavior changes.
- No Local API route additions, removals, or schema changes unless a focused
  domain slice explicitly requires a compatibility-preserving contract move.
- No WebView/Tauri command-contract changes.
- No broad "fix all imports" refactor in one packet.
- No hand edits under `docs/generated/`.
- No deletion of compatibility shims before downstream imports and tests prove
  the replacement path is stable.
- No weakening of dependency-boundary, architecture-guardrail, generated
  context, package, or release gates to make a slice pass.

## Current Baseline

Baseline commands run from the repository root on 2026-06-28:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.check_architecture_guardrails
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.check_dependency_boundaries
```

Observed results:

| Check | Result | Notes |
|---|---:|---|
| `check_architecture_guardrails` | pass | Creation-candidate count is volatile in a dirty worktree. This is a layout/new-file guard, not the main import-boundary baseline. |
| Internal backend imports | 2,764 | From `check_dependency_boundaries`. |
| Module-level cycles | 1 | `publish.pending_drain_confidence -> publish.pending_results -> publish.pending_rows -> publish.pending_drain_confidence`. |
| Package-level cycles | 2 | `completed <-> subtitles` and `config -> paths -> processes -> rename -> config`. |
| Parse errors | 0 | No Python parse blocker in the scanned core package. |
| Core-to-desktop import edges | 332 | The #23 baseline debt. |
| Hard findings | 352 | Includes core-to-desktop edges plus cycles and other hard rules. |
| Allowlisted hard findings | 350 | Existing debt is intentionally listed in `dependency_boundary_allowlist.txt`. |
| Unallowlisted hard findings | 2 | Both are from the dirty-tree `src/mediapipeline/core/api/commands_path_picker.py` importing desktop path dialogs and DTOs. Treat as moving-worktree evidence, not part of this planning packet. |
| Warning findings | 39 | Mostly shared/barrel import posture; handle opportunistically unless a domain slice touches them. |

Core-to-desktop import edges by source domain:

| Source domain | Edges |
|---|---:|
| `config` | 40 |
| `sample_validation` | 38 |
| `processes` | 33 |
| `audit` | 26 |
| `queue` | 26 |
| `completed` | 19 |
| `publish` | 19 |
| `status` | 18 |
| `maintenance` | 15 |
| `network` | 15 |
| `api` | 14 |
| `rename` | 14 |
| `diagnostics` | 10 |
| `failures` | 9 |
| `metrics` | 7 |
| `telemetry` | 7 |
| `final_library` | 6 |
| `schedule` | 6 |
| `observability` | 3 |
| `paths` | 2 |
| `application` | 1 |
| `folder_policy` | 1 |
| `library` | 1 |
| `orchestration` | 1 |
| `subtitles` | 1 |

Core-to-desktop import edges by target package:

| Target package | Edges | Likely ownership correction |
|---|---:|---|
| `mediapipeline.desktop.application` | 148 | Move shared DTO base/command/workspace/inventory types to core/kernel or contracts; keep desktop exports as adapters. |
| `mediapipeline.desktop.models` | 117 | Move shared records such as `ResolvedPaths`, `QueueRecord`, `CompletedJobRecord`, `Snapshot`, and telemetry/config records to core/domain contracts. |
| `mediapipeline.desktop.subprocess_runner` | 21 | Use `mediapipeline.core.kernel.runtime.subprocess_runner` or a core-owned runner protocol. |
| `mediapipeline.desktop.contracts` | 16 | Move state-file contracts to `mediapipeline.contracts` or the owning core domain. |
| `mediapipeline.desktop.network` | 12 | Split pure network parsing/auth/state contracts into core; leave OS/discovery adapters in desktop. |
| `mediapipeline.desktop.api` | 10 | Move pure route/path validation into core; keep OS dialogs and HTTP adapters in desktop. |
| `mediapipeline.desktop.models_core` | 4 | Replace with the final core/domain contract home. |
| `mediapipeline.desktop.priority_markers` | 4 | Move marker parsing helpers to `core.queue` or `core.kernel` and keep desktop shim imports one-way. |

## Dependency Categories

Classify every edge before moving code. Do not move a symbol until its target
home is decided.

| Category | Current examples | Target rule |
|---|---|---|
| Shared records/models | `ResolvedPaths`, `QueueRecord`, `CompletedJobRecord`, `AuditRecord`, `FailureRecord`, `Snapshot`, `TelemetrySnapshot`, `ConfigPreview`, `ConfigSaveResult` | Put records in the owning core domain contract module or `core.kernel` when multiple domains need them. Desktop imports from the new home. |
| Command/read DTO helpers | `CommandResult`, `json_safe`, preview/workspace DTOs | Put transport-neutral DTO helpers under `core.kernel.dto_*` or `contracts` when they are public JSON contracts. Desktop keeps compatibility exports. |
| Runtime helpers | `run_capture`, `CapturedCommandResult`, `KillTreeCallback` | Core imports only core-owned runtime helpers/protocols. Desktop wrappers may depend on core, not the reverse. |
| Desktop API helpers | path dialogs, queue source path policy | Move pure validation to core. OS dialog interaction stays desktop-owned and is passed into core through an adapter/protocol or handled at the desktop route layer. |
| Network helpers | auth token generation, library root parsing, mDNS, worker probes/state | Keep pure parsing/contract/state helpers in core. Keep mDNS/probe/desktop process integration in desktop adapters behind narrow calls. |
| Sample-validation builders | desktop application sample-validation helpers | Move evidence/readiness/policy shaping that core uses into `core.sample_validation`; keep WebView/API presentation wrappers in desktop. |
| Compatibility shims | `desktop.models*`, `desktop.application.dto*`, `desktop.contracts*` | Keep temporary re-export shims until all inbound core imports are gone; remove only after tests and allowlist reduction prove no users remain. |

## Anti-Rework Rules

- First reduce high-fanout shared targets, then domain-specific imports.
- Do not move the same type twice. Decide its final home before the first code
  move.
- Keep old desktop import paths as compatibility re-exports during a slice when
  external or test callers still depend on them.
- Remove or shrink matching entries in
  `docs/architecture/dependency_boundary_allowlist.txt` in the same slice that
  removes the import.
- Add or update tests before deleting a compatibility export.
- Preserve Local API response shapes, WebView-visible field names, command
  names, confirmation semantics, and operator-facing path display.
- Regenerate summaries and generated maps after source moves.
- Treat any slice touching high-risk behavior from the no-touch register as a
  separate implementation packet with the matching validation ladder.
- Stop a slice if the dependency checker adds new unallowlisted hard findings
  outside that slice.

## Phase Plan

### Phase 0: Baseline And Ownership Ledger

Goal: make the debt mechanically visible and classified before moving code.

Deliverables:

- Capture a fresh `check_dependency_boundaries --format json --report-only`
  baseline and summarize it in
  `docs/implementation/architecture-boundary-cleanup/EDGE_LEDGER.md`.
- Expand `EDGE_LEDGER.md` into the durable domain-by-domain ownership ledger
  for the 332 core-to-desktop edges. The ledger must use one row per import
  edge or import-statement group, with source module, target module, imported
  symbols, category, final owner, planned phase, required tests, compatibility
  export, allowlist action, and status.
- Assign each imported symbol to one final home:
  `mediapipeline.contracts`, `mediapipeline.core.kernel`,
  `mediapipeline.core.<domain>.contracts`, or a desktop-only adapter.
- Identify compatibility shims that must stay until the last dependent domain
  is migrated.
- Confirm the dirty-tree unallowlisted `commands_path_picker.py` edges are
  handled by their owning packet before using the boundary checker as a clean
  gate.
- Add the no-new-debt ratchet before implementation starts: freeze the current
  `NO_CORE_TO_DESKTOP` baseline, fail new core-to-desktop edges outside the
  active packet, and require ledger coverage for any temporary allowlist
  addition.

Exit criteria:

- Every core-to-desktop edge has a category, final owner, planned phase, and
  targeted test family.
- `EDGE_LEDGER.md` has a row or explicitly approved grouped row for every
  current core-to-desktop import edge.
- The no-new-debt ratchet exists and passes against the frozen baseline.
- `check_dependency_boundaries` has no unexpected unallowlisted finding beyond
  intentionally active work in the current packet.

### Phase 1: Shared DTO And Runtime Foundation

Goal: remove the highest fan-out imports that would otherwise force repeated
domain rewrites.

Candidate moves:

- Move core-used `CommandResult`/DTO-base helpers to a core-owned or
  contracts-owned module.
- Move core-used `ResolvedPaths` and other cross-domain records out of
  `desktop.models*`.
- Move `CapturedCommandResult`, `KillTreeCallback`, and subprocess runner
  helpers to the existing `core.kernel.runtime` surface or protocol contracts.
- Leave compatibility re-exports under the old desktop paths while callers are
  migrated.

Exit criteria:

- New core code imports the new homes only.
- Desktop compatibility imports point inward to core/contracts.
- Dependency allowlist entries for the moved targets are reduced.

### Phase 2: State Row And Domain Record Migration

Goal: move record types into the domains that own their state files and row
shaping.

Suggested order:

1. `paths`: `ResolvedPaths`.
2. `completed`: `CompletedJobRecord`.
3. `queue`: `QueueRecord` and priority marker helpers.
4. `audit`/`failures`: `AuditRecord` and `FailureRecord`.
5. `status`/`telemetry`: `Snapshot`, `TelemetrySnapshot`, active-job and
   progress contracts.
6. `config`: `ConfigPreview`, `ConfigSaveResult`.

Exit criteria:

- Each domain imports its own contracts or approved shared core/kernel
  contracts.
- Desktop model modules are compatibility-only for those migrated types.
- Domain tests pass for each moved record family.

### Phase 3: API Helper Boundary Cleanup

Goal: remove imports from `core.api` into `desktop.api` and desktop DTOs.

Work items:

- Move queue source path validation into a core-owned policy module.
- Keep Windows path-dialog calls desktop-owned; core command handlers should
  consume a selected path value or injected selector rather than import desktop
  dialogs.
- Fix any active path-picker module before closing this phase, because the
  current baseline shows it as the only unallowlisted hard finding.

Exit criteria:

- `core.api.*` has no import from `mediapipeline.desktop.api` or
  `mediapipeline.desktop.application.dto*`.
- API route inventory and contract payload tests still prove the same public
  routes and command names.

### Phase 4: Network Boundary Cleanup

Goal: separate pure network contracts from desktop lifecycle/discovery
adapters.

Work items:

- Move pure source-path map parsing, library-root derivation, token helpers,
  and worker-state DTOs into `core.network` or `contracts`.
- Keep mDNS discovery, worker probe execution, and process integration behind
  desktop adapters or injected protocols.
- Preserve existing backend-owned lifecycle route behavior and strict
  confirmations.

Exit criteria:

- `core.network.*` imports only core/contracts/runtime helpers.
- Network lifecycle/setup tests and command-contract tests pass.

### Phase 5: Sample Validation And Presentation Builders

Goal: move sample-validation evidence/readiness shaping used by core out of
`desktop.application.sample_validation`.

Work items:

- Move transport-neutral evidence builders into `core.sample_validation`.
- Keep desktop presentation wrappers and WebView payload assembly as adapters.
- Preserve sample-validation schemas and append/preview confirmation behavior.

Exit criteria:

- `core.sample_validation.*` has no desktop application imports.
- Sample-validation preview/append and browser no-mutation tests pass.

### Phase 6: Remaining Domain Slices

Goal: finish lower-count domains without broad refactors.

Candidate groups:

- `maintenance`, `diagnostics`, `metrics`, `final_library`, `schedule`,
  `observability`, `library`, `orchestration`, `subtitles`, `folder_policy`,
  and remaining `publish`/`rename` adapters.

Exit criteria for each group:

- Removed imports are paired with allowlist reductions.
- Targeted domain tests pass.
- No new public WebView/API contracts are introduced.

### Phase 7: Enforcement Tightening

Goal: make `NO_CORE_TO_DESKTOP` a clean gate instead of allowlisted debt.

Status: complete as of `MP-CHANGE-2026-0629-030`. Strict
`check_dependency_boundaries` reports zero `NO_CORE_TO_DESKTOP` imports, the
allowlist has no entries for that rule, and the checker now rejects future
`NO_CORE_TO_DESKTOP` allowlist lines.

Work items:

- Completed: reduce `dependency_boundary_allowlist.txt` until no
  `NO_CORE_TO_DESKTOP` entries remain.
- Completed: decide whether adjacent hard findings, including the existing package/module
  cycles, should remain separate issues or be handled as follow-up boundary
  work. They remain separate non-#23 allowlisted maintenance debt.
- Completed: remove any temporary Phase 0 baseline allowances that are no longer needed
  after the final core-to-desktop allowlist entry is gone.

Exit criteria:

- `check_dependency_boundaries` passes without core-to-desktop allowlist debt.
- `check_architecture_guardrails` still passes.
- Generated summaries/project index are fresh when source/tooling changes.

## Validation Ladder

Every implementation slice should use the smallest safe rung that matches the
touched behavior.

Baseline checks:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.check_dependency_boundaries
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.check_architecture_guardrails
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --check
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.generate_project_index --check
```

Add targeted tests by touched domain:

| Slice | Minimum targeted validation |
|---|---|
| DTO/contract moves | public API import tests, contract payload tests, affected domain unit tests |
| API helper moves | route inventory, API contract payload, command-boundary/static tests |
| Status/telemetry | snapshot/health/telemetry tests and Local API read-route tests |
| Queue/completed/audit/failures | affected facade/service tests and WebView static tests if response payloads are visible |
| Network | network lifecycle/setup route tests, contract payload tests, WebView network boundary tests |
| Sample validation | sample-validation preview/append tests and browser no-mutation smoke where touched |
| Release/package helper moves | release self-test or package verify only if runtime/package layout changes |

Real-media validation is not required for pure import-boundary, DTO-placement,
or compatibility-shim moves. It becomes required if a slice changes FFmpeg/media
policy, subtitle/audio routing, publish/drain behavior, source/scratch/output
movement, cleanup, rename apply, or pending-publish mutation behavior.

## First Implementation Candidate

The first code slice should be small and high-signal:

1. Stabilize the current dirty-tree unallowlisted path-picker imports or wait
   for that owning packet to land.
2. Complete the `CommandResult`/`json_safe` symbol inventory across every
   source domain in `EDGE_LEDGER.md`; do not assume those helpers are
   API-local.
3. Move `CommandResult` and `json_safe` to a core-owned DTO helper while
   keeping desktop compatibility re-exports.
4. Add compatibility proof that the old desktop import paths and the new
   core/contracts paths resolve consistently during the transition.
5. Update only the imports covered by the slice and remove or shrink the
   matching allowlist lines.
6. Run dependency-boundary, architecture-guardrail, API contract payload,
   compatibility-import, and targeted command-handler tests.

This is a good first slice because it exercises the intended pattern without
moving media policy, state files, WebView behavior, or runtime packaging.

## Stop Conditions

- A refactor would require changing route names, WebView command names, strict
  confirmation fields, or response schemas outside the current slice.
- A domain slice touches high-risk media/publish/rename/source movement
  behavior without a separate validation plan.
- `check_dependency_boundaries` reports new unallowlisted hard findings outside
  the slice.
- Compatibility shims would need to be removed before downstream callers are
  migrated.
- Generated context or public contract baselines drift without a matching
  regeneration command.
