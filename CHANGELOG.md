# Changelog

All notable changes to this project are recorded here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to a date-based release cadence rather than semantic
versioning.

This is the single canonical changelog (ADR-0009). Per-feature
`*_REPORT.md` and `*_FIXES.md` at the repo root are deprecated; if a PR's
intent is worth keeping, it goes here and/or in an ADR.

## [Unreleased]

### Added

- Private-beta productization foundation: Tauri is now NSIS-first with aligned
  calendar-build package metadata, updater plugin scaffolding, CI scripts for
  signed NSIS/updater artifacts and GitHub channel JSON, backend-owned
  productization status/support-export routes, AppData runtime roots for
  desktop logs/journal/update/diagnostics evidence, and beta install/update
  runbooks plus a support issue template.
- Repair/reconcile backend dry-run routes: added token-authenticated
  `effect=none` Local API POST routes for Completed manifest reconciliation,
  Completed sidecar metadata repair, Pending Publish manifest repair, and
  orphan pending-payload reconciliation. The routes return
  `desktop_repair_reconcile_dry_run.v1` evidence with strict request fields,
  suppressed command journaling, no mutation route availability, no WebView
  controls, and no manifest, sidecar, payload, source, scratch, or output file
  writes/moves/deletes.
- Test coverage rationalization audit:
  `Docs/archive/docs-housekeeping/2026-06-24-doc-prune/ai-audits/2026-06-18-test-coverage-rationalization.md`
  classifies the
  live-worktree test/check surface across Python, WebView, PowerShell, smoke
  wrappers, and release gates, flags overlap candidates, records high-risk weak
  coverage, and recommends safe consolidation sequencing without changing tests
  or runtime behavior.
- Smoke wrapper drift and duplicate test-name reports:
  `docs/generated/SMOKE_WRAPPER_MAP.json` maps each `ops/scripts/smoke/Test-*.ps1`
  wrapper to its module/test selector plus docs/release presence, and
  `docs/generated/DUPLICATE_TEST_NAMES.md` reports exact duplicate Python test
  names for future consolidation review without changing test behavior.
- Documentation layout alignment: active onboarding, current-state, checklist,
  desktop notes, queue-source-scan, and state-schema docs now point to the
  promoted `src/mediapipeline`, `apps/desktop`, and `ops/scripts` layout,
  remove missing old AI handoff redirect navigation, and keep package-mode
  promotion closed by the 2026-05-30 operator confirmation.
- Network worker capability handshake: workers now report reachable library
  IDs during claim and heartbeat, the coordinator skips library-tagged jobs
  outside a worker's reported capability set, and the Network WebView shows
  per-worker accessible library evidence.
- Network worker mDNS discovery: added bundled `zeroconf` dependency
  declarations plus backend-owned `/api/network/worker/discover-coordinators`
  discovery, Network WebView discovery list, and one-click staging of the
  discovered coordinator URL into the existing Distributed Settings patch flow.
- Objective quality verification: added disabled-by-default post-encode
  quality checks for lossy encodes, with VMAF/SSIM/PSNR metric selection,
  sampled/full modes, warning/failure thresholds, optional block-for-review
  action, sidecar/completed evidence, and Settings WebView controls.
- Watch-folder autostart foundation: added disabled-by-default watch-folder
  config keys, a desktop watch manager that debounces stable source-root files,
  optional backend-owned Run Once dispatch through the existing launch gate, a
  read-only `/api/watch-folders/status` payload, and Schedule/Settings WebView
  status and controls.
- Dynamic HDR Phase 1 detection and honesty: HDR encode/remux sources now get
  bounded Dolby Vision RPU and HDR10+ metadata probes on the scratch copy.
  Encodes warn and emit `dynamic_hdr_metadata_dropped` events when dynamic HDR
  will be flattened to static HDR10, while immediate-publish sidecars and
  completed manifest rows receive additive `dynamic_hdr` evidence. No routing,
  config, FFmpeg command generation, or preservation behavior changed in this
  phase.
- Dynamic HDR Phase 2 tooling/config foundation: added `DynamicHdrPolicy`
  (`off`, `warn`, `preserve_or_remux`, `preserve_or_review`) with default
  `warn`, optional `DoviToolPath`/`Hdr10PlusToolPath` overrides, nonfatal
  startup resolution for operator-placed `dovi_tool`/`hdr10plus_tool`
  binaries, generated schema/metadata alignment, and resolver/capability unit
  coverage. Preservation command generation and real-media remux verdicts
  remain gated on operator-placed binaries and representative media evidence.
- Library Route Map planning pack:
  `docs/implementation/library-route-map/` defines a no-plugin, backend-owned
  Libraries tab plan for read-only route maps, selected-file dry-run traces,
  profile comparison, guided editing through existing Library Profile
  Preview/Save controls, and route validation handoff to Launch, Completed,
  Pending Publish, Diagnostics, and Sample Validation evidence.
- Library Profile route/size replication planning:
  `docs/implementation/library-profile-routing-size-replication-plan.md`
  records the investigation and implementation plan for making Libraries mirror
  the current Settings routing/size controls while preserving backend-owned
  LibraryProfiles inheritance, designation filtering, Preview/Save authority,
  and validation boundaries.
- Read-only Metrics workspace:
  `GET /api/metrics` returns `desktop_metrics.v1` from completed manifest,
  pending publish, worker runtime, and final-library evidence. The WebView now
  has a Metrics tab with Overview, Remux vs Encode, Storage, Production, and
  Workers subtabs for route mix, storage saved, data produced, and
  coordinator/worker signals.
- Maintenance Change Ledger:
  `GET /api/maintenance/change-ledger` now returns a read-only
  `desktop_change_ledger.v1` payload built from existing change-control
  packets, generated changelog/index source status, and root changelog
  evidence. Maintenance renders the ledger with status/type/risk/search
  filters, selected change detail, affected Python-script summaries, and
  changelog hygiene guidance without running health probes or mutating files.
- God-file split planning docs under `docs/architecture/god-file-splits/`
  for current high-strain backend, WebView, Tauri, CSS/partial, and
  docs-supporting code split candidates.
- Active naming support unit gate:
  `ops\pipeline\tests\Unit\Invoke-NamingSupportChecks.ps1` now verifies shared
  Plex movie/TV destination planning, forced rename sidecar sanitization and
  evidence, TV identity keys used by the processed-library index, and source
  identity v2 path-independence/sample-byte sensitivity.
- Route policy evidence lockdown:
  `Resolve-MediaRouteBySize` now carries size/bitrate threshold evidence
  through decide-stage results and queue preview rows, with characterization
  coverage for route threshold modes, H.264 shortcut semantics, and missing
  duration bitrate behavior.
- Configurable movie/TV remux-copy bitrate ceilings:
  `MovieRouteMaxVideoBitrateMbps` defaults to `35` Mbps and
  `TVRouteMaxVideoBitrateMbps` defaults to `18` Mbps. Routing now uses
  those saved settings before choosing encode for `bitrate_over_threshold`,
  while folder `RouteMaxVideoBitrateMbps` remains the per-job override.
- Added `RouteThresholdMode` so initial remux-vs-encode routing can use
  current compatibility-advisory behavior, size-only, bitrate-only, or
  size-or-bitrate hard thresholds.
- Phase 2 config cleanup foundation:
  `src/mediapipeline/contracts/config.py` is now the Pydantic v2 config contract,
  `src/mediapipeline/core/config/load.py` owns PSD1 import plus PSD1 serialization helpers,
  `src/mediapipeline/contracts/schemas/config.v1.schema.json` is generated from the contract, and
  `ops/scripts/dev/generate_config_schema.py --check` enforces schema drift.
- Phase 3 stage-boundary foundation:
  `src/mediapipeline/contracts/stages.py` is now the Pydantic v2 source for stage
  request/result contracts, `src/mediapipeline/core/orchestration/runner.py` is the single
  new Python subprocess boundary, `ops/pipeline/engine/entrypoint.ps1` accepts
  `-Stage` plus `-PayloadJson`, and `src/mediapipeline/contracts/schemas/stages.v1.schema.json` is
  generated from the contract. Only the read-only `decide` stage is
  enabled in the PowerShell dispatcher in this additive slice.
- Phase 4 tooling/state foundation:
  `src/mediapipeline/core/storage/db.py` adds a WAL-mode SQLite mirror under the runtime
  state root, `src/mediapipeline/core/observability/logging.py` adds JSON-line logging
  helpers, and `src/mediapipeline/core/validation/boundary.py` validates API/stage boundary
  envelopes through the generated contracts. Existing JSON state files
  and route payloads remain authoritative.
- Phase 4 check entrypoints:
  `ops/scripts/dev/check_python_typing.py` runs the initial app-layer mypy
  scope, `ops/scripts/dev/check_powershell_analysis.ps1` runs engine-only
  PSScriptAnalyzer when installed, and the existing architecture
  guardrail script is wired into the development safety net.
- Phase 5 drift-prevention foundation:
  `src/mediapipeline/tools/lint_naming.py` blocks new flat facade/service/payload
  modules, dotted `Pipeline/Modules` growth, deprecated suffixes, new
  root callers, and new top-level report/checklist Markdown. The new
  `tests/contract/` tree mirrors config/stage contract checks while the
  legacy `tests/python/desktop` entrypoints remain callable.
- Phase 6 legacy-removal completion:
  root launcher shims, flat Python facade/service compatibility paths,
  old command-payload adapters, and `Pipeline/Modules` are no longer active
  surfaces. Guardrails still block reintroduced root `.bat`/`.ps1` launchers,
  new flat `facade_*`/`service_*`/payload modules, and new dotted
  `Pipeline/Modules` files.
- Phase 7 handoff documentation foundation:
  root `README.md` now exists as the operator entry point,
  `docs/DOCS_INDEX.md` points agents to `AGENTS.md` instead of old
  redirect files, and active-doc checks now fail if the canonical
  handoff docs disappear.
- WebView split tooling and generated baselines:
  Node-based scripts now map WebView god-file candidates, check backend-served
  asset order, preserve the public global contract, track DOM-ID review gaps,
  enforce settings route ownership, and hold ESLint warning budgets. The new
  runbook and guardrail docs keep future plain-script splits scoped and
  reversible.
- Domain/UI follow-up coverage for the current V6 surface:
  Rename Workbench static/backend tests, library profile contract tests,
  final-library promotion service/WebView settings tests, and settings-libraries
  static coverage are present in the active test tree.
- Promotion-state documentation refresh:
  `AGENTS.md`, `README.md`, `docs/CURRENT_PROJECT_STATE.md`,
  `docs/OPEN_WORK_CHECKLIST.md`, and `docs/DOCS_INDEX.md` now treat V6
  default-launcher/package-mode promotion as closed by 2026-05-30 operator
  confirmation while preserving media-policy and revalidation safety rules.
- `docs/RealMediaValidationRuns/README.md` records the non-sensitive
  operator-attested representative real-media validation status for
  2026-05-28.
- `ops/scripts/dev/check_active_doc_references.py` adds a Python active-doc
  reference check for moved docs, archived housekeeping references,
  absolute local handoff paths, and removed legacy desktop-shell wording.
- `CHANGELOG.md` (this file) as the single canonical changelog (ADR-0009).
- `docs/architecture/ARCHITECTURE.md` — short, human-maintained
  architecture summary that cites the ADRs and current architecture docs.
- `docs/generated/PIPELINE_MAP.md` — auto-generatable index of the
  nine canonical stages and their payload/result types from
  `src/mediapipeline/contracts/stages.py`.
- `docs/generated/FILE_SUMMARIES.md` — pointer to the `docs/generated/summaries/`
  directory, the per-source-file summary scheme, and the SHA-256 drift
  rule.
- `docs/archive/sessions/SESSION.md` — archived session scope notes from
  the structural cleanup workspace; current startup guidance lives in
  `AGENTS.md`.
- Former `docs/adr/` seeded with `README.md`, `0000-template.md`, and
  ADRs `0001`–`0011`. ADR-0011 (V5 → V6 split) was written from the
  surviving `V6_SPLIT_NOTES.md` at the repo root; the source notes were
  moved to `docs/archive/v6-split-notes-2026-05-20.md` in the same
  change so the validation evidence and live-API proof survive. Current
  durable decision guidance lives in `Docs/architecture/DECISIONS_AND_HISTORY.md`.
- `docs/audits/latest.md` capturing current known issues distilled from
  active architecture and status docs.
- `ops/scripts/ops/release/metadata/Backup-PreOverhaul.ps1` — operator-run script that
  produces a tagged source archive, a release-package copy, and a
  `LocalBase/State/` snapshot under an external `-Destination`, with
  manifest + SHA-256 evidence.
- Branch `pre-overhaul-snapshot` (passive archive) created from stash
  `pre-overhaul-WIP-snapshot-2026-05-28`. Tag `v6-pre-overhaul` is
  unchanged.

### Changed

- Architecture/operator documentation now resolves moved doc paths under
  `docs/architecture/` and `docs/operator/`, removes active references to
  deleted `Pipeline\Modules` compatibility surfaces, records the enabled
  read-only `probe` and `decide` stage dispatcher state, and labels the
  stale 2026-05-28 audit snapshot as historical.
- Change-control release preview tooling now validates release version labels
  before they are used as ops/release/metadata/archive folder names, includes completed
  `*-dev` placeholder packets in concrete-version dry-run manifests, and keeps
  the change-control runbook on the bundled Python command path.
- Network validation inventory references now point to the active
  `test_application_facade_network.py` and
  `test_webview_network_read_only_boundary.py` coverage instead of the
  removed `test_network_view_source_policy.py` filename.
- API evidence/mutation and no-touch documentation now reflects the promoted
  V6 state: the Tauri/WebView2 lifecycle boundary no longer describes open
  promotion gates as pending, V5 is explicitly protected as the rollback
  workspace, design-only Network and repair/reconcile contracts identify the
  current V6 surface, and `Pipeline\Modules` is documented as a removed legacy
  surface that must not be recreated.
- Settings and Library Profiles documentation now reflects the completed
  settings/library rewrite: backend field metadata is canonical for labels,
  help text, options, defaults, advanced/display taxonomy, and override
  eligibility; the WebView remains staging/display only; persisted V6 keys and
  override groups stay stable; HandBrake-style sections are display metadata
  only; `library_effective_settings` remains library-only;
  `runtime_effective_settings`, where present, is diagnostic-only; promotion
  rules are generated from normalized `LibraryProfiles` before legacy
  `FinalLibraryPromotionRules` fallback; and legacy compatibility shapes such
  as `SourceMovies`, `SourceTV`, `Outsource`, `editor_overrides`, and
  `media_overrides` remain supported.
- Library Profiles override controls no longer render per-field
  taxonomy/strictness chips. Backend metadata remains available for parity
  and row data attributes, while inherited/default versus explicit override
  state is shown with simple text color across all library override subtabs.
- `V6_SPLIT_NOTES.md` moved from repo root to
  `docs/archive/v6-split-notes-2026-05-20.md` (git history preserved
  via `git mv`). ADR-0011 is the durable architectural summary.
- Root launchers relocated under `scripts/`, and the one-release root shim
  phase is now complete. The old root `.bat`/`.ps1` launcher paths are removed
  from the active workspace; `AGENTS.md §6`, `README.md`, and active checklist
  docs point to the canonical `scripts\` paths.
- Phase 1 generated-context checks are now enforceable:
  `ops/scripts/dev/generate_project_index.py --check` verifies
  `docs/generated/PROJECT_INDEX.md` and
  `docs/generated/DEPENDENCY_GRAPH.md`,
  `ops/scripts/dev/generate_pipeline_map.py --check` verifies
  `docs/generated/PIPELINE_MAP.md`, and `refresh_summaries.py --check`
  covers the active canonical script and source paths.
- `.pre-commit-config.yaml` now runs summary, project-index, and
  pipeline-map drift hooks plus the Phase 2 config schema drift hook, and
  `.github/workflows/phase1-drift.yml` runs the same generated-artifact
  checks in CI.
- `.pre-commit-config.yaml` and `.github/workflows/phase1-drift.yml` now
  run `ops/scripts/dev/generate_stage_schema.py --check` for Phase 3 stage
  schema drift.
- Command journal entries, stage runner events, queue dry-run snapshots,
  and completed-job manifest reads now dual-write to the Phase 4 SQLite
  mirror when a runtime state root is available. Reads continue to use
  the existing JSON/state files.
- `.pre-commit-config.yaml` and `.github/workflows/phase1-drift.yml` now
  include Phase 4 architecture guardrails, app-layer typing checks, and
  engine-only PowerShell analysis. CI installs PSScriptAnalyzer before
  enforcing the PowerShell check; local runs skip that check when the
  analyzer module is absent.
- `.pre-commit-config.yaml` and `.github/workflows/phase1-drift.yml` now
  include Phase 5 naming lint and active-doc reference checks.
- Phase 7 handoff docs now treat representative real-media validation as
  closed by operator attestation and Phase 6 local legacy burn-down as
  complete. Default-launcher/package-mode promotion is now closed by
  2026-05-30 operator confirmation, while future media-behavior changes still
  require revalidation.
- `docs/generated/PIPELINE_MAP.md` is generated from
  `src/mediapipeline/contracts/stages.py` instead of hand-synced. The stale summary baseline
  was refreshed from the current source tree; `docs/generated/PROJECT_INDEX.md`
  now indexes 604 source files.

  | Old root path                                                     | New canonical path                                       |
  | ----------------------------------------------------------------- | -------------------------------------------------------- |
  | `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`                   | `ops/scripts/release/build.ps1`                              |
  | `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`                    | `ops/scripts/release/test.ps1`                               |
  | `Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1`              | `ops/scripts/dev/verify-env.ps1`                                 |
  | `Verify-MediaPipelineRemuxEncodeAIO-Environment.bat`              | `ops/scripts/dev/verify-env.bat`                                 |
  | `Run-MediaPipelineRemuxEncodeAIO.bat`                             | `ops/scripts/dev/run.bat`                                    |
  | `Setup-MediaPipelineRemuxEncodeAIO.bat`                           | `ops/scripts/dev/setup.bat`                                  |
  | `Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat`                  | `ops/scripts/dev/start-local-api.bat`                        |
  | `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat`              | `ops/scripts/dev/start-tauri-preview.bat`                    |
  | `Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat`             | `ops/scripts/dev/start-api-and-browser.bat`                  |
  | `New-RealMediaValidationWorksheet.ps1`                            | `ops/scripts/operator/New-RealMediaValidationWorksheet.ps1`  |

  `$PSScriptRoot` resolution in the four moved `.ps1` files was patched
  to step up from their new subfolders so they continue to anchor on the
  repo root. `%~dp0`-relative paths in the moved `.bat` files were
  patched to step up from their new subfolders.
  `ops/scripts/ops/release/metadata/Backup-PreOverhaul.ps1`
  calls `ops/scripts/release/build.ps1` through the canonical script layout.
  Release build verification and release self-test layout checks now use the
  canonical `scripts\` paths without requiring root shims.

  `docs/CURRENT_PROJECT_STATE.md` and `docs/OPEN_WORK_CHECKLIST.md` were
  updated for the canonical launcher and worksheet paths.

  Default-launcher/package-mode promotion is closed by 2026-05-30 operator
  confirmation; the local shim removal gate is also closed.

### Fixed

- Audited operator workflows now keep Maintenance progress polling, Queue
  strategy refresh, and Rename command gating inside their injected module
  contracts; primary navigation activates consistently from Enter and Space;
  Settings builders use display-unit constraints, reset owned patch keys,
  preserve explicit-empty list intent, and guide Library edits to their exact
  controls; release builds default to verified, test-inclusive packages while
  leaving the optional Tauri binary opt-in.
- Settings Preview/Save now rejects non-canonical casing for known persisted
  config keys, and settings/launch BDPGS OCR display fallbacks now match the
  contract default of disabled when `ConvertBdpgsToSrt` is missing.
- Python JSON-line logging now preserves required envelope fields when
  structured context uses colliding keys, while repeated
  `configure_json_logging` calls reuse the same stream handler instead of
  duplicating evidence lines.
- FFmpeg progress proof now treats each console line or native progress block
  as a coherent evidence snapshot. A newer partial block no longer inherits
  older `fps`, `time`, `speed`, or timestamp fields from a previous block.
- CSV rerun source identity now keeps emitting a deterministic
  `source_identity_v2` from source size plus sample hash when bundled
  `ffprobe` is unavailable, instead of silently dropping identity evidence
  down to size/mtime-only checks. Added a focused PowerShell unit gate for
  the missing-ffprobe fallback.
- Failure marker clear results now report `writes_failure_markers` only when a
  marker actually moved, so blocked clear attempts do not look like active
  marker-folder writes. Reports failure/audit row keys now use locale-invariant
  lowercasing for stable row selection.
- Completed open commands now resolve row keys against the same full completed
  history window used by `/api/completed?limit=all`, so backend-selected open
  actions work for older visible history rows instead of only the latest 500
  manifest entries.
- Final-library promotion now removes a newly revealed destination file if the
  final verification pass fails after the staged copy was promoted into place,
  preventing unverified files from remaining in the final library when there
  was no prior destination to restore. Settings guidance now matches the
  staged-copy/restore flow for destructive overwrite.
- Pending-publish manifest contracts and schema now document the VobSub
  subtitle evidence fields and `media_type`/`source_mtime_utc` metadata that
  the PowerShell pending park transaction already writes, keeping Python
  parsing, JSON schema checks, and the state-file reference aligned.
- Completed-manifest evidence references now consistently use the active
  `State\Completed\completed_jobs.jsonl` path in operator triage guidance,
  publish sidecar comments, service documentation, and WebView command
  evidence fixtures.
- Launch active-policy boundary fallback rows now classify staged VobSub
  drop-without-OCR settings the same way as TX3G and BDPGS: blocked when
  drop is enabled without conversion and review when VobSub OCR is disabled.
- Pending-publish sidecar drain now restores an existing SRT sidecar from its
  backup if the replacement sidecar copy fails after touching the destination,
  matching the immediate-publish rollback path.
- Audio transcode bitrate validation now rejects zero-valued tokens such as
  `0k` across the Python config contract, desktop settings validation,
  PowerShell schema checks, and runtime audio fallback handling.
- Python route decisions no longer fall back to ffprobe stream/container
  bitrate when duration-derived bitrate evidence is unavailable. Missing or
  zero duration now leaves the direct-copy bitrate gate inactive and records
  missing bitrate metadata, matching the PowerShell decide stage contract.
- `Invoke-MkvmergeWithProgress` now treats mkvmerge exit `1` as a warning
  success in tool evidence and progress updates, matching the remux caller's
  existing non-fatal mkvmerge warning policy.
- Output path preflight no longer creates a missing optional server output
  root while checking path capability. Missing final roots are left for the
  existing publish/pending-publish parking flow, while paths outside the
  configured output root now fail preflight with boundary evidence.
- Rename apply now requires literal JSON boolean `true` for both
  `confirm_apply` and the outside-configured-roots confirmation. Truthy
  strings such as `"false"` no longer satisfy filesystem-mutation guards,
  and facade/Local API regression tests verify no rename occurs.

### Notes

- ADR-0001 and ADR-0002 are the load-bearing decisions for the
  re-fold of Python facades/services and PowerShell modules.
- ADR-0003, ADR-0005 are `proposed`; their implementations are Phase 3/4
  work.
- ADR-0007 is `deferred`; vanilla JS continues to be the WebView default.
- ADR-0010 and ADR-0011 are `historical`; they record the monolith-split
  campaign and the V5 → V6 split so the source documents
  (`MONOLITH_SPLIT_PLAN.md`, archived `v6-split-notes-2026-05-20.md`)
  are no longer load-bearing.

## [2026-05-28] — Phase 0 / Phase 1 scaffolding (prior commits)

### Added

- Initial architecture planning material was added for the now-complete
  structural cleanup.
- `AGENTS.md` — canonical AI entry point, superseding
  `AI_AGENT_START_HERE.md`, `AI_DIRECTIVE.md`, `AI_HANDOFF.md`.
- `app/` Python skeleton with empty domain dirs; `app/contracts/`
  populated with `config.py` (mirrors PSD1) and `stages.py` (nine
  canonical stages, payload + result per stage,
  `STAGE_SCHEMA_VERSION = "v1"`).
- `ops/scripts/dev/refresh_summaries.py` — Python + PowerShell summary
  generator with SHA-256 drift detection.
- `ops/scripts/dev/generate_project_index.py` — renders
  `docs/generated/PROJECT_INDEX.md` and
  `docs/generated/DEPENDENCY_GRAPH.md` from summaries.
- `docs/generated/summaries/` — 540 per-source-file summaries (~2.0 MB total versus
  ~30 MB of source).
- `docs/generated/PROJECT_INDEX.md`, `docs/generated/DEPENDENCY_GRAPH.md`.
- Tag `v6-pre-overhaul` on commit `8d6d9f6` as the deep rollback
  target.

### Changed

- `AI_AGENT_START_HERE.md`, `AI_DIRECTIVE.md` reduced to redirect stubs
  pointing at `AGENTS.md`.

### Removed

- Root noise: per-feature `*_REPORT.md`, `*_FIXES.md`,
  `DOCS_HOUSEKEEPING_CHECKLIST.md`, and the doc-cleanup-in-progress
  workspace files.

### Notes

- Commit `77b8b4c`'s message references "ADRs 0001 and 0002 anchor the
  direction"; that commit did not actually land ADR files. The ADRs
  are landed in the current `Unreleased` section.

## [2026-04-20] — Initial V6 baseline

- First V6 baseline (`da13cd2`). See `docs/CURRENT_PROJECT_STATE.md` and
  `docs/architecture/` for the inherited shape.

---

[Unreleased]: about:blank
[2026-05-28]: about:blank
[2026-04-20]: about:blank
