# Maintenance-tab code sweep — 2026-07-09

## Executive assessment

The Maintenance tab has a narrow, mostly well-contained command surface: two
read/probe workflows, two dry-run workflows, one deployment writer, a
repository-generated-artifact writer, a fixed-folder shell open, and
allowlisted Diagnostics handoffs. The frontend stages intent only; API
contracts reject unknown keys and use strict booleans; the backend serializes
long-running maintenance commands; and the implemented tab controls do not
repair, reconcile, clean up, drain, publish, rename, or alter media.

I found two P2 issues. The default deployment form is internally incompatible
with the release builder (`Verify` on while `Include tests` is off), so its
primary default preview/build path is deterministically rejected. More
importantly for dry-run trust, the completed-manifest backfill dry run creates
and updates a persistent `RunLogs` checkpoint despite the tab saying it will
not rewrite checkpoints. Neither issue reaches source, scratch, output,
pending-publish, queue, or completed-manifest media state.

Scope reviewed: the Maintenance partial and view module, their `app.js`
wiring, all Maintenance API contracts/handlers/facades/services, the release
and completed-backfill entry points, route/ownership/evidence docs, and
named route, static, browser, and smoke tests. `archive-state-journals`,
support export, retention dry run, startup reconciliation, and the
Completed/Pending-Publish repair and reconcile routes were also traced to
verify ownership; they are **not controls in this tab** today.

## Command inventory

| Control | Route | State/media target | Dry-run support | Confirmation | Journal evidence | Rollback/recovery |
|---|---|---|---|---|---|---|
| Refresh Ledger; local filters/search | `GET /api/maintenance/change-ledger?limit=200` | Read-only change packets/changelog hygiene | N/A | None | None (GET) | Reload; no mutation |
| Run Health Check; progress poll | `GET /api/maintenance`; `GET /api/maintenance/progress` | Bounded tool/config/path/process probes; progress held in memory | Read/probe only | None | None (GET) | Re-run; no mutation |
| Per-row Diagnostics handoff | `GET /api/diagnostics/tail`; `POST /api/diagnostics/open` | Backend allowlisted log/evidence target only | N/A | None | Tail: none; Open: normal command-result journal | No file mutation; OS open only |
| Preview Deployment | `POST /api/maintenance/release-dry-run` | Release copy plan; must not create destination, manifest, or zip | The control is dry-run only | None | Normal command-result journal, including normal returned errors | Correct options and re-preview; no release artifact rollback needed |
| Create Deployment | `POST /api/maintenance/release-build` | External deployment folder, `release_manifest.json`, optional adjacent zip; never media roots | Companion preview available but not enforced | Browser confirmation plus strict `confirm_create: true` | Normal command-result journal | Backend only replaces a destination with release/in-progress marker when `force`; partial build leaves in-progress marker for an explicit rerun/replace |
| Run Backfill Dry Run | `POST /api/maintenance/completed-backfill-dry-run` | Reads outsource `*.pipeline.json`; no completed-manifest rewrite; **does write a RunLogs checkpoint** | The control is dry-run only | None | Normal command-result journal | Checkpoint is evidence only; no apply control on this tab |
| Update Atlas | `POST /api/maintenance/dependency-atlas` | `docs/generated/dependency-atlas/` HTML, images, CSV | No | None | Normal command-result journal | Regenerate; only generated tooling artifacts are replaced |
| Open Folder | `POST /api/maintenance/dependency-atlas/open-folder` | Fixed backend-resolved `docs/generated/dependency-atlas/` folder | No | None | Normal command-result journal | No file mutation |

The page does not expose cleanup, retention apply, support export, state-journal
archive, startup reconciliation, completed repair/reconcile, or pending
publish repair/reconcile. The inventory accurately assigns those to no
WebView caller, Launch, Completed, Pending Publish, or Diagnostics as
applicable.

## Workflow traces and boundary assessment

### Read/probe and Diagnostics workflows

`page-maintenance.html` binds ledger, health, and health-row selection;
`maintenanceView.js` calls the three read endpoints and renders backend
guidance. Health progress is polled only while the health request is active;
the UI de-duplicates a refresh and queues one follow-up refresh. The facade
calls `check_environment_health` with an optional progress callback. The
checker probes configured roots, state layout, API surface, process guard,
bundle layout, PowerShell/tools, and subtitle helpers; it does not repair or
install anything.

Health row diagnostics actions are backend-authored recommendations. The
bridge can only request an allowlisted diagnostics tail target or an
allowlisted shell-open target; it accepts no filesystem path from the
Maintenance UI. This is appropriately separated from repair and cleanup.

### Deployment preview and build

`app.js` wires the controls to `maintenanceView.js`, which gathers only the
listed package options. Strict Pydantic contracts reject string/number boolean
substitutes and unknown keys. The facade uses one non-blocking maintenance
lock for preview, build, backfill, atlas, retention, support export, and
state-journal archive. Build additionally requires literal
`confirm_create is True` and checks active work before invoking the backend
release service.

The release service invokes the canonical `ops/scripts/release/build.ps1` and
captures before/after fingerprints for manifest and zip evidence. The script
rejects filesystem roots, profile roots, the source tree, source descendants,
and source ancestors. It refuses `-Force` replacement unless the existing
directory is empty or carries the release/in-progress marker. The UI displays
destination/options, force, personal-config choice, preview-match status, and
the result's stdout/stderr/evidence. A preview mismatch is prominently
recommended against but deliberately not a second backend confirmation gate.

### Completed-manifest backfill dry run

The facade acquires the maintenance lock, bounds the timeout to 30–1800
seconds, passes `dry_run=True`, and returns `writes_manifest: false` together
with scan counts. The PowerShell entrypoint reads sidecars and does not create
the default `State\\Completed` checkpoint in dry-run mode. It does, however,
write any explicitly supplied checkpoint path; the facade always supplies a
timestamped `RunLogs\\completed_manifest_backfill_dry_run_*.json` path. This
is the dry-run disclosure defect recorded below. No apply endpoint is exposed
from Maintenance.

### Dependency atlas

The atlas facade bounds all numeric inputs, holds the maintenance lock, and
calls the bundled/runtime Python generator. The generator uses fixed
workspace-root paths and reports success only if all expected HTML, PNG, SVG,
and CSV artifacts exist. The open action accepts an empty strict payload and
resolves only that fixed output directory. Neither action has a path-escape
input or media/state target.

### Adjacent administrative/repair surfaces

`POST /api/maintenance/retention-dry-run` is backend-only and expressly
suppresses command journaling; it scans only configured runtime allowlist
roots, excludes source/final-output/pending-publish roots, and offers no
mutation route. `POST /api/maintenance/archive-state-journals` is surfaced by
Launch, not this tab; it requires strict `confirm_archive: true`, safe
close-readiness, a maintenance lock, the fixed `pipeline_events.jsonl` name,
state-root containment, and an oversize threshold. Support export is
backend-only and writes a redacted AppData diagnostics export.

Completed and Pending Publish repair/reconcile controls belong to their own
tabs. Their apply routes use strict confirmation, a backend rerun of the dry
run, fingerprint match, idle-pipeline checks, scoped selections, and backups.
No Maintenance control can invoke them. This separation prevents a health-row
or cleanup action from expanding into media repair.

## Findings

### CSW-2026-07-09-MAINTENANCE-001 — P2: Default deployment options are rejected by the release builder

`page-maintenance.html:198-199` initializes **Verify package** as checked and
**Include tests** as unchecked. `maintenanceView.js:1173-1187` forwards that
combination unchanged for both Preview and Create. The canonical builder
rejects it before planning or copying at
`ops/scripts/release/build.ps1:306-307`: verification requires
`-IncludeTests` unless the unexposed `-AllowTestlessVerify` is supplied.

Impact: the form's default Preview Deployment and, after confirmation, default
Create Deployment fail deterministically. This is an operator-facing
readiness/scope-disclosure failure, not a filesystem or media safety escape.
The existing browser smoke renders synthetic result data and does not exercise
the default click/request against the real builder, so it misses the
contradiction.

Recommended handoff: make the defaults valid as a pair (normally check
Include tests whenever Verify is checked), or disable Verify by default; add
client-side dependency messaging/gating and a focused browser/API test for the
default request. Preserve the builder's backend validation as the authority.

### CSW-2026-07-09-MAINTENANCE-002 — P2: “Backfill Dry Run” persists a checkpoint contrary to its UI guardrail

The tab says the action “must not rewrite completed manifests or checkpoints”
at `maintenanceView.js:1516`, while displaying a checkpoint path at line
1527. The facade nevertheless creates a timestamped `RunLogs` checkpoint path
and passes it to the PowerShell process
(`backfill_facade.py:34-40,64-72`; `completed/backfill.py:53-55`).
`Backfill-CompletedManifest.ps1:60-85,147,231-232` atomically writes that
explicit checkpoint throughout the dry run and at completion. The PowerShell
unit test explicitly asserts this write is expected
(`Invoke-CompletedManifestBackfillDryRunChecks.ps1:95-100`).

Impact: no completed manifest, source, scratch, final output, or parked
payload is modified, but a control described as dry-run creates persistent
runtime evidence and its UI says the opposite. This can leave unbounded
timestamped `RunLogs` checkpoints and weakens confidence in dry-run
disclosures. The Local API dry-run smoke checks that the path is passed
(`test_local_api_maintenance_dry_run_contract_smoke.py:177-178`) but does not
assert the resulting state-file write or disclose it as an intended write.

Recommended handoff: choose one contract and make all layers agree. Prefer
not supplying a checkpoint for this read-only dry run; otherwise explicitly
label it “dry-run with evidence checkpoint,” list `RunLogs` as a write target,
and add bounded retention/cleanup ownership plus a fixture assertion for the
created checkpoint. Do not change the completed manifest semantics.

### Severity summary

| Severity | Findings |
|---|---|
| P0 | None identified |
| P1 | None identified |
| P2 | `CSW-2026-07-09-MAINTENANCE-001`, `CSW-2026-07-09-MAINTENANCE-002` |
| P3 | None identified |

## No-finding coverage

- No control accepts source, scratch, output, pending-publish, completed
  manifest, or arbitrary file paths for mutation. The only typed destination
  is release packaging, whose canonical script independently rejects unsafe
  source/profile/root relationships and restricts replacement to marked
  release directories.
- The exposed tabs cannot invoke repair/reconcile, pending drain, publish,
  media processing, queue mutation, or source deletion.
- Strict booleans cover all exposed release flags and `confirm_create`;
  backend checks literal `True` again for the build. Unknown command payload
  keys are rejected.
- Release dry-run evidence fingerprints manifest and zip before/after and
  fails a supposedly successful dry run if it created or changed either
  artifact. Build verifies manifest and requested zip existence.
- All long-running tab commands share a backend maintenance lock; UI controls
  are disabled while a tab command is in flight. Release build additionally
  fails closed on detected active work. The lock and active-work gate prevent
  the reviewed controls from racing one another or a live pipeline write.
- Command results, returned errors, and validation failures are journaled by
  the Local API for exposed POSTs (retention is intentionally suppressed).
  The journal is bounded, atomically persisted when configured, and mirrored
  to SQLite best-effort; the UI appends the immediate result and refreshes
  Maintenance whenever the backend returns its refresh hint.
- Atlas generation and folder-open are backend-rooted and path allowlisted;
  diagnostics handoffs use target keys rather than paths.

## Test and contract assessment

Strong coverage exists in:

- `test_api_command_contracts.py` for strict Maintenance booleans and unknown
  key rejection.
- `test_application_facade_maintenance.py` and
  `test_facade_maintenance_command_policy.py` for locks, timeout bounds,
  confirmation, result evidence, atlas fixed-target behavior, and state
  archive close-readiness.
- `test_local_api_maintenance_dry_run_contract_smoke.py` for token protection,
  journal behavior, release/backfill/retention dry-run contracts, and unchanged
  fixture source/output/manifest bytes.
- `Invoke-CompletedManifestBackfillDryRunChecks.ps1` for backfill's explicit
  checkpoint behavior and default-state non-write behavior.
- `test_webview_frontend_mutation_boundary.py`, the Maintenance change-ledger
  browser smoke, and the Maintenance/Reports browser smoke for ownership,
  rendering, and non-accidental command posting.

Gaps relevant to the findings:

- The browser Maintenance/Reports smoke renders result fixtures and explicitly
  forbids the Maintenance POSTs in that scenario. It does not click each
  Maintenance command against a controlled backend or assert the default
  release option dependency.
- The Local API dry-run smoke validates only media/completed-manifest
  preservation; it does not snapshot/assert the `RunLogs` checkpoint write.
- No test asserts the page text, command contract, and PowerShell behavior use
  one coherent definition of “dry run” for checkpoint evidence.

For a fix, use the Validation Ladder's Maintenance route guidance: targeted
unit/contract tests, affected WebView smoke, `Test-LocalApiMaintenanceDryRunContractSmoke.ps1`, and the release self-test for any `build.ps1` change. A release/package change needs the full release self-test; no real-media validation is required unless the change crosses into FFmpeg, subtitle, audio, publish, or source/output movement.

## Coordinator handoff

1. Assign the deployment-default fix to the Maintenance/WebView plus release
   owner. Decide the valid default pair, retain backend enforcement, and add a
   default-form regression test.
2. Assign the backfill dry-run contract decision to the Completed/maintenance
   owner. The lowest-risk resolution is omitting the explicit checkpoint from
   the Maintenance dry run; if evidence checkpoints are retained, amend the
   UI, route inventory, state-target disclosure, and retention lifecycle in
   the same change.
3. Keep repair/reconcile ownership with Completed/Pending Publish and
   state-journal archive ownership with Launch/Diagnostics. Do not move those
   mutation controls into Maintenance merely to address either finding.

## Limits

This was a static, read-only review. I did not invoke Maintenance, cleanup,
repair, reconciliation, archive, release, or mutation routes; I did not run
tests, launch the UI, create a release package, or inspect real media. The
worktree was already heavily dirty with unrelated user changes; this review
did not inspect or alter those changes except where their current on-disk
contents were necessary to trace `app.js`/Launch ownership. No change packet
was created because the request explicitly limited writes to this report.

Reviewed governing documentation: `AGENTS.md`, `docs/DOCS_INDEX.md`,
`docs/CURRENT_PROJECT_STATE.md`, `docs/architecture/ARCHITECTURE.md`,
`docs/architecture/MODULE_MAP.md`, `docs/inventories/API_ROUTE_INVENTORY.md`,
`docs/testing/VALIDATION_LADDER_RUNBOOK.md`, and
`docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`; supporting route ownership,
mutation-matrix, smoke-catalog, and repair/reconcile contract documents were
used for cross-checks.
