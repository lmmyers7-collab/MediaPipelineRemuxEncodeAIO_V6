# Module Ownership Map

Status: **final ownership review complete**. All active top-level, implementation, generated, metadata, vendor/runtime, test, and audit-evidence domains are assigned an owner role and mutation boundary. Exact per-file owner, layer, worker, dependencies, routes, state, tests, findings, and review status are machine-authoritative in the external `COVERAGE_MATRIX.jsonl`.

## Ownership rules

1. Frontend surfaces display backend truth and stage intent; they do not duplicate backend mutation or media policy.
2. Desktop/API code adapts transport and shell lifecycle; core domains own application policy and mutation decisions.
3. Contracts own shapes and validation, not side effects.
4. PowerShell owns media execution and its filesystem transaction stages; stable entrypoints coordinate but do not become a second policy implementation.
5. Every mutable state surface has one authoritative owner even when mirrors/read models exist.
6. Generated artifacts derive from source/tooling and cannot become authority by being easier to query.
7. Tests and review snapshots are evidence, not production mutation owners.

## Top-level ownership

| Surface | Tracked paths | Primary owner | Mutation authority |
|---|---:|---|---|
| `apps/desktop/webview/static/` | 350 | WebView presentation | Browser-local display/staging only |
| `apps/desktop/tauri/` | 47 | Native shell/bootstrap | Window, child-handle, single-instance, native close lifecycle only |
| `src/mediapipeline/desktop/` | 137 | Local API and desktop adapters | Route adaptation and backend/shell lifecycle coordination |
| `src/mediapipeline/core/` | 521 | Python domain services | Backend policy, state transactions, orchestration, filesystem/process decisions |
| `src/mediapipeline/contracts/` | 40 | Contract/schema layer | Shape validation and generated schema authority |
| `src/mediapipeline/pipeline/` | 8 | Pipeline helper layer | Tool-specific transformation under caller policy |
| `src/mediapipeline/tools/` | 60 | Developer/release/context tooling | Tool-scoped repository/evidence mutation only |
| `ops/pipeline/engine/` | 163 | PowerShell media engine | Scratch/media/state/publish execution within safety boundaries |
| `ops/pipeline/entrypoints/` | tracked under pipeline | Stable engine entrypoints | Argument/startup coordination; delegates domain work |
| `ops/pipeline/config/` | tracked under pipeline | Config projection/templates | Templates/schemas/profiles; local PSD1s remain ignored/operator-owned |
| `ops/scripts/` | 89 | Dev/operator/release wrappers | Bounded by named command; no duplicate engine policy |
| `tests/` | 423 | Verification evidence | Temporary fixture mutation only |
| `docs/` | 2,973 | Documentation/generated evidence | Canonical docs by purpose; generated paths only through generators |
| `ops/release/` | 1,098 | Change/release evidence | Structured packets and release metadata, not runtime policy |

## Python core domain ownership

Counts are Git-tracked files at the audit baseline.

| Domain group | Files | Owns | Mutation/state boundary |
|---|---:|---|---|
| `api/` | 33 | Backend read/command payload composition and result policy | Delegates mutation to domain owners; command contract/journal requirements apply |
| `application/`, `orchestration/` | 6 | Cross-domain application workflows and runner coordination | May coordinate owners; should not duplicate their policies |
| `config/` | 68 | Settings schema/defaults/metadata/store/projection/profiles | JSON authority, locked transactions, PSD1 projection; must stay lower-level |
| `kernel/` | 27 | Low-level DTOs, contracts, config keys, runtime primitives | Shared typed authority; no higher-level policy |
| `paths/` | 9 | Canonical path contracts, identity, fingerprints | Path validation/identity primitives; no UI input trust |
| `shared/` | 4 | Legacy/shared compatibility surfaces | Compatibility only; new broad ownership is forbidden |
| `processes/` | 59 | Launch/preflight/rerun/process plans/close/shutdown evidence | Process lifecycle, exact command plans, leases/jobs; delegates media execution |
| `queue/` | 29 | Discovery, snapshots, priority/hold/claims/rounds | Queue state and launch-plan integrity |
| `schedule/`, `rerun/` | 10 | Scheduled intent and rerun lifecycle | Schedule/rerun state, never silent local launch policy forks |
| `publish/` | 20 | Pending publish contracts, park/drain/repair projections | Manifest-backed deferred placement and transaction evidence |
| `final_library/` | 9 | Promotion/final placement policy | Final-library mutation with exact safety evidence |
| `completed/` | 16 | Completion records, manifests, read models | Completion authority and evidence, not inferred frontend state |
| `storage/`, `files/` | 9 | Atomic storage/file primitives and constants | Reusable low-level file operations within caller authority |
| `network/` | 23 | Coordinator/worker lifecycle, claims, auth/provider policy | Network state, tokens, claims/results/reclaim; role-specific authority |
| `status/` | 24 | Status/run-monitor/close-readiness projections | Backend-authored read models; writes only owner-specific evidence |
| `observability/`, `telemetry/`, `metrics/` | 18 | Events, health, metrics, logs/telemetry projections | Evidence emission/aggregation, not operational mutation authority |
| `diagnostics/` | 23 | Diagnostic/autonomy/repair-read projections | Read/probe and explicit domain-command coordination |
| `rename/` | 28 | Rename preview/apply/undo/filter policy | Exact path/collision/manifest-backed rename transactions |
| `maintenance/` | 19 | Maintenance plans and bounded mutation commands | Strict confirmation, backups, journals, rollback |
| `repair_reconcile/` | 8 | Dry-run fingerprints and exact candidate apply | Metadata/state repair only; never guessed media placement |
| `audit/` | 15 | Library/media audit workflows | Read/probe plus bounded audit artifacts |
| `failures/` | 16 | Failure state, retry projection, resolution journal | Failure identity/status/recovery evidence |
| `decide/` | 10 | Remux/encode/media policy decisions | Pure/typed decision authority; execution remains engine-owned |
| `subtitles/` | 4 | Subtitle policy/contracts/helpers | Preservation/conversion policy; unsafe conversion routes to review |
| `validation/`, `sample_validation/` | 17 | Validation and representative sample plans | Proof/evidence only; no authority to weaken release gates |
| `library/`, `folder_policy/` | 13 | Library/folder identity, summaries, traversal policy | Backend library scope and discovery boundaries |
| `ui/`, `ui_preferences.py` | 3 | Backend-defined presentation preferences/contracts | No frontend-style mutation policy |
| package root | 1 | Namespace | None |

The current package SCC means some ownership directions are violated or allowlisted as debt. `DEPENDENCY_AND_CYCLE_MAP.md` records all enforced edges and the open `processes -> queue` finding.

## Desktop/API ownership

| Domain | Files | Owns | Boundary |
|---|---:|---|---|
| `desktop/api/` | 32 | HTTP route dispatch, auth/body/static-file transport policy | Validates/adapts then calls application/core; no duplicate mutation policy |
| `desktop/application/` | 23 | Application facade composition and desktop command/read entry | Orchestrates core owners and journal evidence |
| `desktop/network/` | 55 | Desktop-facing network adapters/providers/read models | Core network lifecycle/policy remains authoritative |
| `desktop/contracts/` | 10 | Desktop-facing contract adapters | Shape translation only |
| `desktop/watch/` | 3 | Watch integration | Backend schedule/watch owner determines durable intent |
| Desktop root/bootstrap/models/services/smokes | 14 | Server/bootstrap/singleton/models/composition | Backend process lifetime and transport composition; models are not state authority |

Every Local API route must join to a contract, validator, handler, domain owner, state effect, process/filesystem effect, command evidence, and tests. That exhaustive join lives in worker-14 route artifacts and `ROUTE_COMMAND_FLOW_MAP.md`.

## Contract ownership

`src/mediapipeline/contracts/` has 40 tracked files:

- API route and command inventories/contracts;
- config fields/defaults/coercion/validators/schema extras;
- pipeline stage, plan, lifecycle, runtime-evidence, source-media, subtitle, verification, and decision contracts;
- four generated JSON schemas under `contracts/schemas/`.

Python contract source is authoritative over generated schema output unless a domain-specific document says otherwise. Generators/check modes must prove that mirrors are current. Contracts may reject invalid data; they must not perform hidden mutation.

## PowerShell engine ownership

| Engine domain | Files | Primary responsibility |
|---|---:|---|
| `process/` | 36 | Native process execution, heartbeat, polling, termination, media commands |
| `decide/` | 17 | Stream mapping and remux/encode policy translation |
| `queue/` | 16 | Discovery/plan/round/claim/retry execution |
| `publish/` | 14 | Output placement, Pending Publish manifest/transaction/drain |
| `subtitles/` | 13 | Subtitle extraction, conversion, OCR, preservation, sidecars |
| `config/` | 12 | Runtime projection, keys, profiles, overlays, effective paths |
| `audit/` | 10 | PowerShell audit workflows |
| `shared/` | 9 | Shared outcome/failure registry and engine primitives |
| `probe/` | 6 | Media, stream, duration, HDR probe |
| `naming/` | 5 | Destination naming |
| `paths/` | 5 | Runtime source/scratch/output/final path construction |
| `rerun/` | 5 | CSV/result rerun engine behavior |
| `storage/` | 3 | Atomic storage/move primitives |
| `audio/`, `status/`, `verify/` | 6 | Audio policy execution, status, output verification |
| entrypoint, ingest, library, policy, observability, failures | 6 | Thin coordination/specialized single-owner helpers |

High-risk ownership remains split deliberately:

- Python chooses/authorizes plans and owns operator-facing state policy.
- PowerShell performs media/native-tool stages and filesystem transactions.
- Contracts and manifests bind the handoff.
- Neither layer may silently accept a weaker safety contract than the consumer; `AUDIT-FIND-W15-001` is a current violation of that requirement.

## Frontend and shell ownership

WebView static code owns:

- rendering and accessibility;
- staged form/command inputs;
- request invocation and backend evidence display;
- browser-local navigation/selection state.

It does not own config save, queue mutation, rename/repair apply, pending drain, network lifecycle, process shutdown, or media policy. Strict confirmations must be literal backend-validated booleans, not frontend convention.

Tauri owns:

- native window and WebView2 composition;
- backend child startup/monitor/shutdown;
- bootstrap URL/token handoff;
- single-instance and native close integration;
- packaged resource/sidecar location.

Backend close-readiness and cleanup truth remain backend-owned. Rust/native shell must propagate indeterminate child-exit evidence rather than infer success.

## Tooling, docs, generated, and evidence ownership

| Surface | Owner | Rule |
|---|---|---|
| `src/mediapipeline/tools/dev/` | Development/context/guardrail tooling | May inspect/generate declared artifacts; fail closed on proof gaps |
| `src/mediapipeline/tools/change_control/` | Change packet tooling | Structured packet validation; never absorbs unrelated dirty files |
| `ops/scripts/dev/` | Development launch/check wrappers | Canonical entry wrappers; preserve exit codes |
| `ops/scripts/operator/` | Operator helpers | Explicitly named bounded operator workflow |
| `ops/scripts/release/` | Release/package gates | Package inclusion/exclusion/signing/publication evidence |
| `docs/generated/` | Generator-owned navigation | Never hand-edit unless explicitly marked human-maintained |
| `docs/inventories/` | Active inventory contracts | Must have owner/generator/check or explicit maintenance rule |
| `docs/reviews/` | Evidence snapshots | Not active instruction unless current authority/user reopens it |
| `docs/archive/` | Historical evidence | Inventory/reference check only; never current authority by accident |
| `ops/release/changes/` | Per-change evidence | Touched paths, risk, validation, rollback, status |

## Tests and fixtures

`tests/` has 423 tracked paths: 327 Python, 74 WebView, 20 fixtures, and two support/root files. PowerShell tests live under `ops/pipeline/tests/` and Tauri test wrappers live with the shell/scripts.

Tests own no production policy. They are evidence that must be reviewed for assertion quality, skips, over-mocking, negative paths, state isolation, and parity with their names. `TEST_AND_VALIDATION_MAP.md` records gate ownership and current workflow omissions.

## Known ownership ambiguities/debt

- `core.processes` directly consumes queue-owned freshness policy (`AUDIT-FIND-DEP-001`).
- Eight config-to-rename/process higher-level edges are explicit allowlisted debt.
- 43 barrel `__init__` re-exports need intentional API versus stale shim reconciliation.
- Legacy config extras are preserved and materialized into runtime scope despite docs calling them inert (`SETTINGS-002`).
- Shared failure/outcome codes have namespace-dependent metadata ownership (`W15-003`).
- Generated context is stale under concurrent source edits (`COV-001`).
- Route inventory is currently drifting with unrelated `/api/queue/priority-export` edits; worker-14 retains baseline and provisional live snapshots.
- Completed W03 review found queue compatibility helpers that still mutate source names/timestamps (`W03-003`), crossing the default source-immutability ownership boundary.
- Process lifecycle authority is not consistently bound to launch identity: cwd plus a reused PID can authorize kill-tree mutation, while durable leases use PID liveness alone (`W03-001`, `W03-002`).
- Several queue/status/schedule readers collapse failed or corrupt authority into ordinary complete/healthy/empty/default state (`W03-004`, `W03-006`, `W03-007`, `W03-009`, `W03-013`, `W03-014`, `W03-015`), allowing projections or partial writers to overrule the actual uncertainty.
- Media policy is split without enforced semantic parity: Python ignores `AllowNoAudio=false` and `convert_preferred`, while Python/PowerShell disagree on first-video versus all-video mapping (`W05-003`, `W05-004`, `W05-010`).
- The ASS helper owns a filesystem commit but does not enforce source/output/summary role separation (`W05-001`), and scratch subtitle commit ownership is not held through the final replacement (`W05-009`).
- Tauri child ownership is process-local rather than recoverable across hard shell death, while harness cleanup can claim a backend that appeared after its baseline (`W09-002`, `W09-009`).
- Packaged-runtime ownership is unresolved: the NSIS archive lacks the backend/WebView/runtime layout and startup can select ambient Python plus inherited import roots (`W09-001`, `W09-003`).
- The Rust startup route contract is manually duplicated and already omits both priority-export routes (`W09-013`); updater ownership is scaffolding without a lifecycle owner (`W09-007`).

## Per-file proof and final reconciliation

For every tracked path, `COVERAGE_MATRIX.jsonl` must carry exactly one:

- owner domain and architectural layer;
- category and applicable generated/vendor/archive/binary/runtime flags;
- incoming/outgoing dependencies and relevant routes/commands/state/config/process/artifacts;
- relevant tests and findings/errors;
- current hash-bound review status and independent-review state.

Final ownership checks require zero unknown/default owners for achieved rows, no unsupported duplicate authority, and exact consistency with the route, state, process, config, failure, dependency, security, and test maps. Those checks are enforced by the external 6,499-path freeze. Ownership ambiguities listed above remain finding-backed product debt rather than unreviewed scope.
