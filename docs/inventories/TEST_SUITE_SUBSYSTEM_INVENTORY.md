# Test Suite Subsystem Inventory

Purpose: map the `tests\python\desktop\` test suite by subsystem so contributors can choose targeted tests for a given change. All counts are approximate; the suite grows over time.

Validation command:

```powershell
Get-ChildItem tests\python\desktop -Filter test_*.py | Measure-Object
```

All-surface rationalization snapshot: `docs/ai-audits/2026-06-18-test-coverage-rationalization.md` classifies the current live-worktree test/check surface across Python, WebView, PowerShell, smoke wrappers, and the release gate. Its 2026-06-18 read-only pass found 378 discovered test/check files and 2,504 Python test definitions. Treat that report as consolidation guidance, not as a replacement for this targeted subsystem inventory.

Generated drift aids: `docs/generated/SMOKE_WRAPPER_MAP.json` maps every `ops/scripts/smoke/Test-*.ps1` wrapper to its underlying module/test selector plus docs/release presence, and `docs/generated/DUPLICATE_TEST_NAMES.md` reports exact duplicate Python test names across `tests/python` and `tests/webview`. Both are review aids; duplicates and wrapper/module pairs are not removal instructions.

Legacy reliability decomposition is owned by `docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.v1.json`, validated against `src/mediapipeline/contracts/schemas/test_suite_subsystem_inventory.v1.schema.json` by:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.check_test_suite_subsystem_inventory --json
```

The map inventories each logical block in `Invoke-LegacyDesktopReliabilityRegressionChecks.ps1`, covers every assertion-bearing line exactly once, records focused replacements or obsolescence evidence, and refuses removal of unclear blocks or unique blocks without passing replacement evidence. It is the machine-readable extension of this inventory, not a competing test catalog.

---

## Oversized Test Migration Plan (2026-07-20)

The audit baseline found 46 Python test files above 1,000 measured lines and 9 above 2,000. Migration boundaries follow tested behavior and operator surfaces; line ranges are not migration units.

| Baseline file | Measured lines | Behavior seams and migration order |
|---|---:|---|
| `test_application_facade_process_launch.py` | 4,165 | Pipeline/audit launch; Network lifecycle and worker provider; local rerun enrollment/recovery; Network rerun launch/claim handoff; launch locks and schedule gates; read-only launch preflight. Network lifecycle and Network rerun are now separate modules; preflight is also independently selectable. Continue with local rerun lifecycle before core pipeline/audit launch. |
| `test_application_facade_web_static.py` | 3,354 | Home/progress rendering; Local API contract and command wiring; Settings/path-picker staging; Queue file-override UI; Diagnostics handoff; headless backend bootstrap/reconciliation. Continue one page or route family at a time. |
| `test_webview_browser_maintenance_reports_smoke.py` | 2,712 | Maintenance commands; report/audit triage; diagnostics-open and clear/archive flows; browser lifecycle harness. Extract backend fixture/server setup before separating Maintenance and Reports journeys. |
| `test_process_rerun_results.py` | 2,352 | Local/current rerun selection; Network projections and reducer timelines; stop/continue recovery actions; correlation degradation; Pending Publish promotion. Split read-model projection from recovery commands, then promotion policy. |
| `test_tauri_shell_scaffold.py` | 2,234 | Shell/bootstrap contract; packaging and CSP; close/single-instance lifecycle; smoke harness wiring. Split static scaffold/package checks from native lifecycle and harness-policy checks. |
| `test_webview_browser_queue_launch_completed_smoke.py` | 2,064 | Backend Queue plan; Launch acceptance/duplicate guard; Run Monitor transitions; Completed/review reload. Keep the end-to-end journey intact, but extract narrowly named queue-plan and synchronized-runner fixtures. |
| `test_network_rerun_claims.py` | 2,059 | Claim/done/release; destination policy; reducer outcomes and retries; source identity/outage recovery; stale-claim reconciliation; handoff probes. Split by state-machine command family, preserving the shared durable batch fixture. |
| `test_file_override_tracks.py` | 1,949 | Route registration; series batch overrides; remux-pilot promotion; folder rules; track probing; effective selection and exact selectors. Split by override scope and keep probe fixtures shared only by track/effective modules. |
| `test_webview_browser_launch_queue_readiness_smoke.py` | 1,848 | Browser startup/readiness; Queue scan and scope reconciliation; Launch policy/timing evidence; sample-validation handoff. Extract server/browser fixture setup, then split Queue readiness from Launch/sample-validation rendering. |

For each tranche, preserve test names and assertion bodies, run the original focused module set before movement, compare discovered counts after movement, and run the generated duplicate-name report before and after. Update this inventory and `docs/testing/TEST_COVERAGE_MATRIX.md` with each new feature-scoped selector.

---

## Running Targeted Tests

All tests use the bundled Python:

```powershell
$py = "apps\desktop\runtime\Python\python.exe"
& $py -m unittest <module.path> -q
```

Run a full subsystem via discovery:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "<pattern>" -q
```

Module-level `def test_*` and `async def test_*` functions are collected by
pytest rather than unittest. The canonical AST-backed inventory discovers them
under `tests/python` and non-browser `tests/webview` files, then runs exactly
those files without duplicating the full unittest suite:

```powershell
& $py -m mediapipeline.tools.dev.pytest_style_tests --collect-only
& $py -m mediapipeline.tools.dev.pytest_style_tests --run
```

Both required CI workflows and `ops/scripts/release/test.ps1 -RequireTests`
invoke the same runner. `requirements/dev.txt` declares pytest, inventory or
parse failures are hard failures, and browser smoke modules remain owned by the
isolated browser matrix.

---

## PowerShell Guard Checks

These focused PowerShell checks sit outside `tests\python\desktop` and guard cross-cutting repo hygiene or pipeline contracts:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-ActiveDocsReferenceChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RepoHygieneChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RuntimeStateHygieneChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-ToolLogLifecycleChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-TransientRetryLifecycleChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PortablePathChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishOwnershipChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishSafetyChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-ContractSchemaChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-AuditCommandSupportChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PathBoundaryGuardChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-ScratchCopyIdentityChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-FailureCodeRegistryChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-DynamicHdrDetectionChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-DynamicHdrToolingChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-EncodeFlagPolicyChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-EncoderCapabilityProbeChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-EncoderRuntimeMatrixChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-NamingSupportChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PipelineQueueEngineChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RunMonitorContractPersistenceChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RunMonitorStateChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-EncodeRuntimeRouteEvidenceChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-ProgressStateTelemetryChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-SubtitleLongWorkHeartbeatChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RerunAutoDestinationChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RerunCooperativeStopChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RerunNestedConfigChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RerunPlanOnlyChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RerunPublicationTransactionChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RerunRecoveryChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-RerunSourceIdentityChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-ReleasePackagePolicyChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Invoke-AdversarialForceKillEncodeChecks.ps1
```

`Invoke-ActiveDocsReferenceChecks.ps1` guards post-reorg active-doc links for moved source-of-truth docs, blocks root-level references to superseded housekeeping report names unless they point at `docs/archive/admin-audits`, and prevents high-level status/checklist docs from embedding absolute local current-handoff paths. Historical archive files and the forensic changelog are intentionally excluded so old evidence can remain unchanged.

`Invoke-RepoHygieneChecks.ps1` guards root generated log/jsonl captures, DesktopApp root API validation captures, rebuildable pytest/Tauri artifacts, and the ignore entries that keep those artifacts out of source review.

`Invoke-RuntimeStateHygieneChecks.ps1` guards legacy runtime state placement: app-root encode-speed history and desktop state files must stay absent, `LocalBase\State\App` and `LocalBase\State\Completed` paths must remain documented/tested, and stale queue/pending-publish filenames must not return to active inventories.

`Invoke-ToolLogLifecycleChecks.ps1` guards native-tool diagnostic state placement and disposition: live captures stay under pipeline-owned `ToolLogs/Active`, successes delete them, failures promote them to failure artifacts, operator stops retain them under `ToolLogs/Interrupted`, orphaned active captures reconcile after a hard stop, and the configurable interrupted-log retention window prunes only expired evidence.

`Invoke-TransientRetryLifecycleChecks.ps1` uses disposable files to prove one old transient marker emits one retry notice, successful existing-output and pending-publish outcomes clear it, failed parking retains it, and the recovery path does not manufacture `ENCODE_UNEXPECTED_EXCEPTION` evidence.

`Invoke-PortablePathChecks.ps1` parses audit/config/profile scripts and blocks local operator path defaults such as `\\LAYNE-SERVER\Video` from returning to active audit or profile templates.

`Invoke-AuditCommandSupportChecks.ps1` runs entirely under a generated
temporary layout and guards bundled `ffprobe` discovery after the audit helper
move. It proves the promoted entrypoint-relative tool path is selected without
scanning operator media or starting a live library audit. The active
`Invoke-ReliabilityRegressionChecks.ps1` wrapper runs it by default.

`Invoke-ContractSchemaChecks.ps1` guards pipeline contract schema presence and representative round-trip payloads for events, process results, queue snapshots, pending-publish manifests, completed-job sidecars, publish results, publish partial paths, and folder-policy topology shapes.

`Invoke-PathBoundaryGuardChecks.ps1` guards path-boundary helper behavior, output capability preflights, full drive/UNC-share ancestor-chain and dangling-reparse rejection, scratch-copy traversal rejection, stale temp cleanup, and audit probe-cache identity for same-path replacement files.

`Invoke-ScratchCopyIdentityChecks.ps1` guards CPA-2026-07-19-003 with isolated tiny synthetic source/scratch roots. Its deterministic matrix covers valid content-bound reuse; same-name/size/timestamp substitution; replacement after discovery; mutation during copy; truncation; stale, missing, malformed, unsupported, and legacy evidence; Windows path aliases/case; scratch-name collision; prior partial work; restart after evidence write; and locked stale scratch. Every row records source SHA-256 before and after. Reuse requires freshly recomputed matching source/scratch SHA-256 evidence under `scratch_source_identity.v2`; uncertainty either re-copies safely or fails closed. The reliability wrapper requires this suite. It does not prove real-media behavior or output quality.

`Invoke-AdversarialForceKillEncodeChecks.ps1` is a runtime adversarial smoke rather than a static guard. It creates generated media in `%TEMP%`, starts the real backend in `-Once`, force-kills a live CPU fallback encode after an `encode_temp*.mkv` artifact exists, then proves the partial was not accepted as completed output/pending publish, the source remains queued, the live FFmpeg capture is not classified as a failure, and the next exclusive startup reconciles that capture from `ToolLogs/Active` to `ToolLogs/Interrupted`.

`Invoke-FailureCodeRegistryChecks.ps1` guards the `FailureCodes.ps1` registry: every classifier return code must be known, every registry row must include family/stage/when-fires/retryability/operator severity/handler/operator-action metadata, representative high-risk metadata rows must stay accurate, broader pipeline outcome/error codes emitted by PowerShell surfaces must be known, and unknown-code metadata lookup must fail closed.

`Invoke-DynamicHdrDetectionChecks.ps1` guards Dynamic HDR source/output detection and verification: Dolby Vision side-data/profile evidence, HDR10+ frame evidence, Dynamic HDR state summaries, unsupported/error paths, and preservation-verification fail-closed behavior.

`Invoke-DynamicHdrToolingChecks.ps1` guards Dynamic HDR tool and capability decisions: helper-tool availability/version reporting, cached x265 capability probing, FFmpeg-native Dolby Vision encoder support detection, relative HDR10+ JSON x265 probe paths, and planner/tooling fallbacks without mutating source media.

`Invoke-EncodeFlagPolicyChecks.ps1` guards encode argument parity and descriptor scaffolding: current HEVC/NVENC and libx265 attempt snapshots remain unchanged, Dynamic HDR CPU plans use FFmpeg-native `-dolbyvision true` plus guarded x265 profile/HDR10+ parameters without passing CLI-only RPU paths through `-x265-params`, dormant descriptor flag shapes fail closed where required, retry classification covers NVENC/QSV/AMF signatures, and descriptor-owned primary/fallback selection plus attempt-plan evidence stays family-consistent without activating new encoder families.

`Invoke-EncoderCapabilityProbeChecks.ps1` guards descriptor-owned encoder capability probe helpers: exact ffmpeg encoder-list matching, missing-ffmpeg failure behavior, list-only probe reporting, one-frame lavfi runtime probing for bundled `libaom-av1`, hardware list-only reporting, and list/runtime cache separation. It does not enable dormant encoder descriptors or replace the future per-encoder runtime matrix.

`Invoke-EncoderRuntimeMatrixChecks.ps1` guards descriptor-owned synthetic SDR/HDR10 runtime topology: it builds descriptor flags before any hardware skip, asserts HDR flag shape for HDR-capable descriptors, runs one-frame lavfi encodes for runtime-available CPU descriptors, verifies ffprobe codec plus 10-bit/BT.2020 output for executed HDR rows, and reports hardware rows as explicit opt-in skips unless `MEDIAPIPELINE_ENCODER_RUNTIME_HARDWARE=1` is set. It does not enable dormant encoder descriptors or replace representative real-media HDR side-data validation.

`Invoke-MultiVideoTopologyChecks.ps1` guards FR-016 preserve-all real-video topology with bundled FFmpeg/ffprobe. It derives a two-real-video sample from the retained Tdarr seed when available, otherwise generated media, then proves remux `-map 0:V` and `New-EncodeFfmpegArgumentList` encode topology preserve the real-video count (`source=2 remux=2 encode=2`). This is targeted topology/runtime evidence; broader Dynamic HDR and hardware-encoder representative real-media validation stay in their own gates.

`Invoke-ConfigKeyRegistryChecks.ps1` guards `ConfigKeys.ps1`: the PowerShell config-key registry must stay in the same order as `ConfigSchema.ps1`, template/live PSD1 files may not contain unknown keys, helper lookups must fail closed, and literal PowerShell `$config[...]`, `$config.ContainsKey(...)`, and `Get-Config*` call sites may not reference unknown config keys. `test_config_keys.py` also guards Python-side Network runtime and settings/media-policy raw registered-key lookups, plus a package-wide registered-key raw-lookup scan across `mediapipeline.desktop`.

`Invoke-PipelineQueueEngineChecks.ps1` guards queue-engine dispatch mode selection and accepted naming evidence: one local worker slot stays serial, multi-slot `local_worker_slots` dispatches through the worker scheduler with the expected script/config/PowerShell context, missing worker context fails closed without falling back to serial dispatch, worker-child result writing remains versioned, production/force-rename filenames and exact evidence-source tokens are bound to Queue-plan and accepted-membership fingerprints, raw/unversioned/tampered names fail closed, and planner or pre-planner naming failures cannot enter accepted membership or inherit a preceding row's route evidence.

`Invoke-RunMonitorContractPersistenceChecks.ps1` directly guards the extracted contract and persistence modules: safe run identity, evidence constructors, immutable membership signatures, payload validation, UTF-8 atomic writes, accepted-seed reads, pointer identity, mutex naming, and terminal-history retention in a disposable state root. `Invoke-RunMonitorStateChecks.ps1` guards immutable accepted Run Once membership, rejection of blank planned-name evidence at the engine seed boundary, exact pre-spawn-seed adoption, run-wide identity and stage correlation, planned/executed/final route separation, all-worker projection, per-track audio/subtitle evidence, wrong/missing track fail-unknown behavior, terminal artifact references, and truthful progress/freshness semantics. `Invoke-EncodeRuntimeRouteEvidenceChecks.ps1` separately proves runtime encode-family/fallback decisions author exact executed-route reason evidence without overwriting terminal proof. The state and route checks remain mandatory children of `Invoke-ReliabilityRegressionChecks.ps1`.

`Invoke-ProgressStateTelemetryChecks.ps1` guards progress-to-monitor translation, including distinct Verification mapping, exact track correlation, nonterminal indeterminate progress, and the rule that compatibility progress or generic route text cannot become stage or executed-route authority.

`Invoke-SubtitleLongWorkHeartbeatChecks.ps1` guards exact run/job/track/stage liveness for long ASS and TX3G conversion, BDPGS/VobSub OCR, and the pre-OCR CPU-slot wait. It proves throttled active-only indeterminate heartbeats, stale-context suppression, explicit native poll propagation, no fabricated numerator/denominator, and a contended named-mutex wait without reading or mutating real media. `Invoke-SubtitleBuilderDecisionChecks.ps1`, `Invoke-VobSubSubtitleChecks.ps1`, and `Invoke-NativeProcessCleanupChecks.ps1` provide the corresponding fake OCR/call-order and wrapper-level integration coverage. The reliability wrapper requires both the focused subtitle heartbeat suite and the native lifecycle/fallback suite, including exact-context, explicit-override, and greater-than-45-second freshness regressions.

`Invoke-NamingSupportChecks.ps1` guards runtime naming and library identity support: shared Plex movie/TV destination planning, forced rename sidecar sanitization/evidence, screenshot-style YIFY/YTS/BONE/GalaxyRG/Judas/SubsPlease/ToonsHub cleanup, TV identity keys used by the processed-library index, and source identity v2 path-independence/sample-byte sensitivity.

`Invoke-RerunSourceIdentityChecks.ps1` guards CSV rerun source identity fallback behavior: when `ffprobe` is unavailable, source identity still emits a deterministic SHA-256 value and changes when source sample bytes change.

`Invoke-RerunCooperativeStopChecks.ps1` guards the CSV rerun wrapper cooperative-stop contract: stop markers live under `State\Rerun\Control`, stale markers are rejected by batch/manifest/CSV/start-time evidence, marker checks happen after chunk manifest writes, and stopped manifests include continuation evidence.

`Invoke-RerunRecoveryChecks.ps1` guards restart-safe CSV rerun recovery: typed initial and mid-copy source loss including native throws and missing landed files, bounded retry/exhaustion, durable pre-copy size/sampled-identity/full-SHA proof of landed scratch after source loss, source-mutating Robocopy `/M`/`/MOV`/`/MOVE` rejection before request artifacts or native invocation, mandatory full-chain trusted-ancestor and reparse-aware scratch containment including proof-unavailable, dangling, junction, and symlink cases, identity-reproved attempt cleanup that preserves unexpected/ambiguous evidence, verified-stage reuse, exactly-once nested launch/correlation/CAS ordering, disjoint terminal counts, and PlanOnly no-write behavior.

`Invoke-RerunNestedConfigChecks.ps1` guards the live nested-pipeline handoff, including creation of both empty `Movies` and `TV` staged source roots before the nested process starts. `Invoke-RerunPlanOnlyChecks.ps1` proves preview/PlanOnly evaluation does not create those runtime scratch roots or other request artifacts.

`Invoke-RerunAutoDestinationChecks.ps1` guards the CSV rerun auto-return contract with a mocked nested pipeline: clean verified outputs replace the existing final target through the confirmed replacement path, outputs with remaining issue evidence are parked in Pending Publish with auto-review evidence, and original source media remains present.

`Invoke-RerunPublicationTransactionChecks.ps1` guards final-library rerun publication as one recoverable media-plus-companion transaction. It covers non-overlap sidecar/SRT/completion parity, same-volume staging, replacement rollback at media/SRT/pipeline-sidecar/completion boundaries, exact hashes, idempotent completion replay, abandoned completion-mutex ownership, and distinct-process recovery after hard termination both before and after completion evidence. All fixtures are generated under the temporary directory; source fixture bytes must remain unchanged. `-RepresentativeMedia` additionally generates distinct source, prior-final, and replacement MKVs with bundled FFmpeg, publishes an external SRT, probes the committed media with bundled ffprobe, and rechecks the source SHA-256.

`Invoke-ReleasePackagePolicyChecks.ps1` guards release packaging policy: rebuildable/vendor/runtime/local-state/personal-config paths remain excluded by default, release hygiene rules stay aligned with the policy manifest, and `Backup-PreOverhaul.ps1` continues to delegate release copy creation to the canonical release builder.

## Python Tooling Guard Checks

These repository-level Python tests sit outside `tests\python\desktop` and guard generated maps, AI pre/postflight tooling, naming/layout rules, change-control metadata, and documentation-reference scanners:

```powershell
& $py -m unittest discover -s tests\python\tooling -p "test_*.py" -q
```

| Test file | What it covers |
|---|---|
| `tests/python/tooling/test_active_doc_references.py` | Active-doc moved-path, removed-shell-wording, absolute handoff-path, archive-exclusion, and required-doc checks |
| `tests/python/tooling/test_ai_guardrail.py` | AI guardrail preflight/postflight plan contents and git-status rename/untracked path parsing |
| `tests/python/tooling/test_audit_checks.py` | Shared audit-check manifest suites for pre-commit, generated-context CI, deep-audit, release self-test, and AI guardrail orchestration |
| `tests/python/tooling/test_change_control.py`, `tests/python/tooling/test_archive_completed_changes.py` | Change-control coverage, completed-packet archival/refusal/idempotence/rollback, archived release-input continuity, version-label validation, and missing-version diagnostics |
| `tests/python/tooling/test_code_context_benchmark.py` | Versioned 48-case retrieval fixture integrity and quality/performance acceptance thresholds |
| `tests/python/tooling/test_code_context_mcp.py` | Read-only MCP path policy, atomic index reload, normalized caches, aggregate-metric privacy, context/lookup/search/read/bundle bounds, live search, SDK stdio contract, client bootstrap preview, dependency isolation, and token ceilings |
| `tests/python/tooling/test_dependency_boundaries.py` | App import-edge collection, module/package cycle detection, hard-boundary violations, allowlist staleness, and current-repo dependency check |
| `tests/python/tooling/test_pytest_style_tests.py` | AST-backed module-level pytest discovery, browser exclusion, fail-closed inventory behavior, dependency declaration, and required CI/release-gate wiring |
| `tests/python/tooling/test_godfile_guard.py` | God-file policy validation, allowlisted thresholds, new/existing oversized file warnings, growth warnings, and git-status rename parsing |
| `tests/python/tooling/test_lifecycle_map.py` | Lifecycle state/transition integrity and generated lifecycle-map rendering |
| `tests/python/tooling/test_lint_naming.py` | Deprecated flat facade/service/payload names, dotted `Pipeline\Modules` files, root status docs, root launcher callers, and rename-destination parsing |
| `tests/python/tooling/test_risky_file_registry.py` | Risky-file registry validation and path classification into validation requirements |
| `tests/python/tooling/test_tauri_updater_channel_pointer.py` | Stable updater-channel release routing, pointer-release policy, versioned installer provenance, exact public-endpoint byte verification, and stale-response refusal |
| `tests/python/tooling/test_tracked_office_documents.py` | Fail-closed Git enumeration and source-intake rejection of Office working documents under `docs/` |
| `tests/python/tooling/test_summary_integrity.py` | Summary freshness orphan detection, summary pruning, and project-index orphan-summary refusal |

---

## Python Integration Media Policy Checks

These integration tests sit outside `tests\python\desktop` and guard dry-run media-policy contracts without processing media:

| Test file | What it covers |
|---|---|
| `tests/python/integration/test_handbrake_remux_regression_matrix.py` | Python planner remux/encode route, stream-action, size-policy, and preset parity fixtures |
| `tests/python/integration/test_ffmpeg_media_policy_regression_matrix.py` | Machine-readable FFmpeg/media-policy matrix completeness, owner/check/rung evidence, Python planner expectations for matrix rows, size-policy contract expectations, and TESTGAP-006 closure gating |

Targeted command:

```powershell
& $py -m unittest tests.python.integration.test_ffmpeg_media_policy_regression_matrix tests.python.integration.test_handbrake_remux_regression_matrix -q
```

The matrix guard is synthetic validation only. It does not replace PowerShell runtime parity, Tdarr sample runs, release gates, or representative real-media validation for FFmpeg, subtitle, audio, publish/drain, or source/scratch/output behavior changes.

---

## Subsystem Index

### Stage Contracts and Dispatcher

Tests for the versioned stage contract, Python runner journal/event handoff, and PowerShell entrypoint dispatch boundary.

| Test file | What it covers |
|---|---|
| `test_stage_contracts.py` | Stage request/result Pydantic contracts, generated schema parity, mutation intent requirements, strict execute confirmations, backend registration, and the invariant that every disabled mutation stage has a machine-readable blocker plus required-validation list while enabled stages have no blocker |
| `test_stage_runner.py` | Python stage runner result parsing, timeout/error classification, command/operation-journal evidence, duplicate replay, low-risk probe/decide helpers, guarded ingest, scratch-only rename, and standalone ASS/SSA subtitle dispatch |
| `test_stage_entrypoint.py` | PowerShell stage entrypoint contract rejection, read-only probe/decide round trips, and guarded ingest dry-run/execute behavior using temporary source files, scratch-boundary checks, evidence files, and source-hash preservation |

Targeted command:

```powershell
& $py -m unittest tests.python.desktop.test_stage_contracts tests.python.desktop.test_stage_runner tests.python.desktop.test_stage_entrypoint -q
```

Coverage gap: temporary ingest/rename/ASS fixtures do not replace representative real-media validation. `transcode`, `audio-mix`, `publish`, and `drain` remain disabled; their registry metadata records the production-policy, manifest-transaction, recovery, and representative-media gates required before any backend registration change.

---

### Config

Tests for config loading, PSD1 parsing, key resolution, profile validation, and save/reload runners.

| Test file | What it covers |
|---|---|
| `test_config_service.py` | General config service behavior |
| `test_service_config_psd1.py` | PSD1 parse, key types, defaults |
| `test_service_config_profiles.py` | Profile loading and merging |
| `test_service_config_value_checks.py` | Value validation rules |
| `test_service_config_validation.py` | Cross-field config validation, path overlap warnings, and BDPGS OCR enabled-without-tool-path warning |
| `test_config_keys.py` | Config-key registry alignment across Python settings schema, network defaults, PowerShell ordered pipeline config keys, Network runtime raw-lookup drift, settings/media-policy raw-lookup drift, and package-wide registered-key lookup drift |
| `ops/pipeline/tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1` | PowerShell config-key registry alignment, PSD1 known-key coverage, and literal PowerShell config-reference drift |
| `test_service_config_path_warnings.py` | Path key warning logic |
| `test_service_config_numeric_policy.py` | Numeric range and policy checks |
| `test_service_config_document_runner.py` | Config document runner, subprocess capture handoff, and Protocol-typed config service boundary |
| `test_service_config_save_runner.py` | Config atomic-save/profile runner and Protocol-typed save service boundary |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*config*.py" -q
```

Coverage gap: live-config write integration test against a real PSD1 file.

---

### Status, Progress, and Telemetry

Tests for pipeline state, progress tracking, event reading, snapshot assembly, and CPU/RAM/GPU sampling.

| Test file | What it covers |
|---|---|
| `test_status_service.py` | General status service |
| `test_service_status_errors.py` | Error state classification |
| `test_service_status_progress.py` | Progress field parsing |
| `test_service_status_active_jobs.py` | ActiveJobs status/read-model projection, including nonterminal `kill_degraded` warning and reconciliation guidance |
| `test_service_status_ffmpeg_progress.py` | FFmpeg progress proof payload parsing, coherent console/progress-block snapshot handling, read-only contract shape, parse-error reporting for active encode/remux evidence without key/value fields, and idle no-fake-row behavior |
| `test_service_status_eta.py` | ETA telemetry payload calculation from worker-progress percent/elapsed evidence, unavailable-reason reporting when ETA cannot be estimated, read-only contract shape, and idle no-fake-row behavior |
| `test_service_status_files.py` | Status file discovery |
| `test_service_status_summary.py` | Summary aggregation |
| `test_service_status_presentation.py` | Presentation formatting |
| `test_service_status_events.py` | Event log reading |
| `test_service_status_summary_sections.py` | Summary section assembly |
| `test_service_status_snapshot_runner.py` | Snapshot runner and Protocol-typed status snapshot service boundary |
| `test_application_facade_snapshot.py` | Application-facade snapshot assembly, active-work summary fields, progress bar presentation for publish/audit/subtitle/copy work, ActiveJobs diagnostics rows, and zero-percent GPU telemetry mapping |
| `test_status_rerun_completion.py` | Backend-manifest CSV rerun completion projection for success, failed, empty, pending-publish, active, and stale-progress contexts |
| `test_webview_csv_rerun_completion.py` | WebView terminal-summary rendering that suppresses stale CSV route-progress in the live status and timeline |
| `test_service_app_schedule.py` | Schedule state service |
| `test_telemetry_service.py` | CPU/RAM/GPU telemetry |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*status*.py" -q
& $py -m unittest tests.python.desktop.test_telemetry_service -q
```

---

### Queue

Tests for queue priority marking, snapshot reading, dry-run planning, preview builder, and dry-run runner.

| Test file | What it covers |
|---|---|
| `test_service_queue_priority.py` | Priority marker detection and ordering |
| `test_service_queue_snapshot.py` | Snapshot file reading and validation |
| `test_service_queue_dry_run.py` | Dry-run route planning logic |
| `test_service_queue_dry_run_runner.py` | Dry-run runner execution and Protocol-typed queue dry-run service boundary |
| `test_service_queue_preview_builder.py` | Queue preview payload builder and Protocol-typed queue preview service boundary |
| `test_application_facade_queue.py` | Application-facade normal-only queue preview behavior, stale evidence, visible blocked rows versus exclusions, runtime outcome correlation, explicit exclusion of local/Network CSV rerun manifests, compatibility metadata, and backend row-key queue open allowlists |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*queue*.py" -q
```

The browser-backed Queue → Launch → Completed smoke passes two accepted raw release-name rows, one blocked row, and one excluded row through production duplicate/lifecycle guards, exact run/Queue-plan/accepted-membership correlation, folded verified clean names, expanded selection, and persisted Completed/review evidence using a synchronized fake runner. Representative PowerShell/FFmpeg media remains a separate release gate.

---

### Process Launch and Lifecycle

Tests for launch environment setup, launch plans, spawn, kill, readiness checks, cleanup, control flags, and runner coordination.

| Test file | What it covers |
|---|---|
| `test_subprocess_runner.py` | Subprocess runner utilities |
| `test_service_process_active_jobs.py` | ActiveJobs record read/write/reconcile behavior, monotonic `killed`/`kill_degraded` evidence, stale-update suppression, and logger Protocol boundary |
| `test_service_process_control_flags.py` | Pause/stop/rescan flag read/write and logger Protocol boundary |
| `test_service_process_launch_env.py` | PATH setup, bundled tool injection |
| `test_service_process_logs.py` | Log file location and rotation |
| `test_service_process_runtime_artifacts.py` | Runtime artifact management |
| `test_service_process_launch_plans.py` | Launch plan construction |
| `test_service_process_kill.py` | Exact-identity, bounded single-flight process-tree cleanup; verified Windows/POSIX and captured-descendant exit proof; machine-readable killed PID/job-kind/Run ID/command ID evidence; root-exited/child-survived and descendant-enumeration-unverifiable rejection; fail-closed `kill_degraded` evidence for timeout, nonzero, unexpected exception, and root-only fallback; warning logger Protocol boundary |
| `test_service_process_spawn.py` | Process spawn logic |
| `test_service_process_readiness.py` | Pre-launch readiness checks and spawn readiness logger Protocol boundary |
| `test_service_process_launch_cleanup.py` | Post-launch cleanup and warning logger Protocol boundary |
| `test_service_process_launch_runner.py` | Launch runner coordination and Protocol-typed launch service boundary |
| `test_service_process_control_runner.py` | Control flag runner and Protocol-typed control service boundary |
| `test_service_process_runtime_runner.py` | Runtime runner and Protocol-typed runtime cleanup service boundary |
| `test_service_process_active_job_runner.py` | ActiveJobs record management and Protocol-typed ActiveJobs service boundary |
| `test_service_process_spawn_runner.py` | Early exact-process ownership, PID-reuse-safe registration, completion/heartbeat startup and interleaving, idempotent late ownership finalization after proven cleanup, degraded tree retention, rerun terminalization suppression when exit is unproved, and Protocol-typed spawn boundary |
| `test_process_service.py` | General process service |
| `test_facade_process_control_policy.py` | Facade: control policy |
| `test_facade_process_schedule_policy.py` | Facade: schedule policy |
| `test_facade_process_guard_policy.py` | Facade: guard policy |
| `test_facade_process_audit_policy.py` | Facade: audit launch policy |
| `test_facade_process_pipeline_policy.py` | Facade: pipeline launch policy |
| `test_facade_process_rerun_policy.py` | Facade: rerun policy |
| `test_application_facade_process_launch.py` | Core pipeline/audit launch, local rerun enrollment/recovery, process ownership, launch locking, schedule gates, and duplicate guards |
| `test_application_facade_launch_preflight.py` | Read-only pipeline/audit/rerun launch preflight, Queue-plan provenance, path health, schedule/lock blockers, and encoder capability evidence |
| `test_application_facade_network_lifecycle.py` | Network-role launch rejection, coordinator/worker lifecycle commands, provider behavior, strict journal ordering, duplicate guards, concurrency, and redaction |
| `test_application_facade_network_rerun_launch.py` | Network rerun dry-run/start, claim-enabled batch state, claim/done/release handoff, stale fingerprint rejection, and journal-failure cleanup |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*process*.py" -q
& $py -m unittest discover -s tests\python\desktop -p "test_facade_process*.py" -q
& $py -m unittest tests.python.desktop.test_application_facade_network_lifecycle tests.python.desktop.test_application_facade_network_rerun_launch -q
```

Closed coverage gap: `test_application_facade_process_launch.py` now starts one pipeline, reports the first bundle-owned child process as still running, and confirms a second pipeline launch is rejected before the service launcher is called again.

Closed runtime safety gap: `ops\pipeline\tests\Invoke-AdversarialForceKillEncodeChecks.ps1` force-kills a real backend encode process tree and confirms the byte-bearing temp output is not accepted as complete, no completed/pending-publish state is written, the source hash remains unchanged, and the source remains backend-queued after restart planning.

---

### Completed

Tests for completed manifest reading, consistency checks, and backfill.

| Test file | What it covers |
|---|---|
| `test_service_completed_validation_state.py` | Completed validation-state contract from completed rows, including output-presence proof, missing-output blockers, unavailable probe/hash/playback proof, and future complete proof |
| `test_service_completed_manifest.py` | Manifest read and validation |
| `test_service_completed_backfill.py` | Backfill runner logic |
| `test_facade_completed_open_policy.py` | Facade: completed open policy |
| `test_application_facade_completed.py` | Application-facade completed preview manifest/progress evidence, validation-state child payload, size/runtime/missing-output classification, completed-open row-key allowlists, and completed-manifest backfill dry-run behavior |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*completed*.py" -q
```

---

### Rename

Tests for TV and movie name parsing, cleaning-filter configuration, rename planning, discovery, preview/apply parity, undo, WebView contracts, and scratch-stage safety.

| Test file | What it covers |
|---|---|
| `test_service_rename_utils.py` | Shared rename utilities |
| `test_rename_workbench.py` | Rename Workbench DOM/routes, browse mode, filter-case append boundary, checked-row apply scope, and undo command shape |
| `test_application_facade_web_static_rename.py` | Static asset/DOM ownership, cleaning-filter settings hooks, preview/apply/outcome contracts, browse/busy guards, and namespace wiring |
| `test_application_facade_rename.py` | Application-facade rename preview/apply command behavior, confirmation guard, selected-source scope, multi-select handling, and apply-lock guarding |
| `test_application_facade_local_api_rename.py` | Local API browse/preview/filter-case/apply/undo routes, injected path picker, strict confirmations, active-work rejection without mutation, media-root injection, and preview policy |
| `test_api_path_dialogs.py` | Windows rename path-dialog host selection, encoded PowerShell invocation, selected-path payload parsing, missing-host reporting, and process-failure diagnostics |
| `test_rename_service.py` | Service integration, natural ordering, Python/PowerShell preview selection, TV/movie predictions, apply rollback, Unicode paths, sidecar updates, and undo-manifest location |
| `test_rename_bad_case_corpus.py` | Bad-case corpus schema and active TV/movie output expectations, including the SubsPlease `12v2` regression |
| `test_service_rename_movie.py` | Release scrub, rightmost plausible years, numeric and metadata-like title preservation, verified-tail revisions, explicit remove terms, and configurable filter categories |
| `test_service_rename_tv.py` | Revisions, canonical ranges, E001-E999 bounds, bare anime episodes, ordinal seasons/cours, specials, title false positives, and folder/file precedence |
| `test_service_rename_tv_folder.py` | TV folder-level rename handling |
| `test_service_rename_discovery.py` | Source file discovery for rename |
| `test_service_rename_plan_policy.py` | Rename plan policy rules |
| `test_service_rename_planner.py` | Planning orchestration, cleaning-policy propagation, authoritative PowerShell leaf preservation, unsafe leaf/suffix rejection, duplicate targets, canonical range identity, semantic overlap blocking, hierarchy destinations, and path authority |
| `test_service_rename_preview.py` | Production synthetic-preview request/result correlation, policy fingerprints, assumed-extension evidence, and preview generation |
| `test_service_rename_preview_runner.py` | Preview runner, real bundled-PowerShell parity for numeric titles and verified metadata tails, the exact extensionless Edge of Tomorrow regression, and Protocol-typed naming-preview service boundary |
| `test_service_rename_apply.py` | Operation construction, defensive semantic-overlap checks, mutation boundaries, case-only behavior, sidecar collisions/metadata, rollback, and undo-manifest authority |
| `test_service_rename_apply_runner.py` | Temporary-filesystem apply/undo, on-disk media-plus-sidecar reversal, metadata restoration, multi-episode range identity, and unsafe manifest blocking |
| `test_stage_contracts.py` | Rename-stage registration, strict mutation intent/confirmation DTOs, and generated schema |
| `test_stage_runner.py` | Scratch-only rename dry-run/execute, fingerprint and journal binding, source/scratch boundaries, duplicate replay, undo evidence, and rollback |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*rename*.py" -q
& $py -m unittest tests.python.desktop.test_api_path_dialogs -q
& $py -m unittest tests.python.desktop.test_stage_contracts tests.python.desktop.test_stage_runner -q
```

Focused PowerShell coverage is in `ops/pipeline/tests/Unit/Invoke-NamingSupportChecks.ps1` for Python/pipeline naming parity and destination planning, and `ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1` for Queue dry-run parsing and ordering.

Remaining limits noted in `docs/inventories/RENAME_SAFETY_TEST_INVENTORY.md`: native dialog display in a real interactive Windows shell and coordinator/worker path-rewrite behavior. Undo-manifest, on-disk media-plus-sidecar, and active-pipeline blocking coverage are closed.

---

### Pending Publish

Tests for manifest parsing, path resolution, manifest row validation, strict manifest proof, drain/repair trust gates, and general service behavior.

| Test file | What it covers |
|---|---|
| `test_service_pending_publish_format.py` | Manifest format and parsing |
| `test_service_pending_publish_paths.py` | Path resolution from manifests |
| `test_service_pending_publish_manifest.py` | Manifest state validation, legacy no-drain visibility, and current-manifest missing proof rejection |
| `test_service_pending_publish_manifest_rows.py` | Per-row manifest validation, legacy non-drainable rows, and unsupported current states |
| `test_pending_publish_service.py` | General pending publish service, parked payload evidence, and legacy scan-visible/do-not-drain behavior |
| `test_process_rerun_results.py` | CSV rerun result promotion into Pending Publish writes a current pending manifest contract and leaves source media untouched; results expose aggregate history, deterministic `current_local`/`current_network` selection, exact-live identity correlation, backend-declared actions, and Network destination-policy evidence |
| `test_application_facade_pending_publish.py` | Application-facade pending-publish preview classification, durable drain-summary evidence, publish reconciliation, final-proof path normalization, same-leaf weak evidence, row-key open allowlists, scan-failure surfacing, and recovery dry-run planning |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*pending_publish*.py" -q
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishOwnershipChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishSafetyChecks.ps1
```

Remaining gaps noted in `docs/inventories/PENDING_PUBLISH_FIXTURE_INVENTORY.md`: recovery-plan action coverage, completed-manifest/drain-summary cross-check depth, and coordinator-mode pending-publish handoff.

PowerShell safety coverage now includes strict root detection and manifest trust cases in `ops\pipeline\tests\Unit\Invoke-PendingPublishSafetyChecks.ps1`: legacy no-drain/no-mutation, forged parked payload and destination rejection, unsafe crash-recovery original refusal, sidecar carry-forward boundary rejection, mixed-slash safe paths, and cleanup refusal outside `PendingServerPush`.

PowerShell ownership coverage includes `ops\pipeline\tests\Unit\Invoke-PendingPublishOwnershipChecks.ps1`, which parses the publish/pending modules and guards the documented parked-output-as-media-plus-sidecars ownership boundary.

---

### Audit and Rerun

Tests for audit record reading, CSV handling, I/O, metadata, and export.

| Test file | What it covers |
|---|---|
| `test_service_audit_rerun_records.py` | Audit record format |
| `test_service_audit_rerun_csv.py` | CSV read/write logic |
| `test_service_audit_rerun_io.py` | Audit I/O operations |
| `test_service_audit_rerun_metadata.py` | Metadata reading and Protocol-typed rerun metadata service boundary |
| `test_service_audit_rerun_export.py` | Export logic and Protocol-typed rerun CSV export service boundary |
| `test_service_failure_markers.py` | Failure marker read/write |
| `test_service_failure_retry_state.py` | Failure retry-state contract from failure rows/markers, including transient next-queue-pass retries and blocked operator/permanent/exhausted rows |
| `test_facade_audit_policy.py` | Facade: audit policy |
| `test_facade_failures_policy.py` | Facade: failures policy and retry-state child payload |
| `test_application_facade_reports.py` | Application-facade read-only failure JSON/marker preview, retry-state payload, and audit CSV preview behavior |
| `test_rerun_lifecycle.py` | Durable local CSV rerun enrollment, strict exit/duplicate proof flags, nonterminal `spawn_transition_ambiguous` duplicate blocking, exact startup ActiveJobs/manifest correlation and path binding, verified premanifest terminalization without replay, stale-transition ordering, lifecycle counts/timeline, and accepted-row retention |
| `test_process_rerun_results.py` | CSV rerun correlation/evidence projection, copied or renamed v2 manifest degradation with recovery actions withheld, exact waiting-child correlation, logical recovery namespace/generation behavior, canonical row-selector idempotence, Network reducer/destination-policy/retry projection, cooperative stop, and rerun promotion |
| `test_rerun_results_network_projection.py` | Focused read-only Network CSV rerun row projection: stable row identities, defensive evidence copies, output-probe states, lifecycle aggregation, retry/destination action payloads, input immutability, and parent import/export compatibility |
| `ops/pipeline/tests/Unit/Invoke-PortablePathChecks.ps1` | PowerShell audit/legacy GUI parser and portable audit-root default guard |
| `ops/pipeline/tests/Unit/Invoke-RerunAutoDestinationChecks.ps1` | PowerShell CSV rerun auto-return behavior for clean confirmed final replacement, remaining-issue Pending Publish review routing, and source preservation |
| `ops/pipeline/tests/Unit/Invoke-RerunCooperativeStopChecks.ps1` | PowerShell CSV rerun cooperative stop marker and stopped-manifest contract guard |
| `ops/pipeline/tests/Unit/Invoke-RerunNestedConfigChecks.ps1` | PowerShell live nested config handoff, including safe creation of both Movies and TV staged roots before nested launch |
| `ops/pipeline/tests/Unit/Invoke-RerunPlanOnlyChecks.ps1` | PowerShell CSV rerun PlanOnly contract, including no runtime scratch/request artifact creation |
| `ops/pipeline/tests/Unit/Invoke-RerunRecoveryChecks.ps1` | PowerShell typed initial/mid-copy source recovery including thrown/missing-landed failures, durable landed-scratch identity proof, source-mutating Robocopy flag rejection, mandatory full-chain/reparse-safe scratch boundaries, ambiguity-preserving attempt cleanup, exact-once restart/correlation/CAS ordering, disjoint outcomes, and PlanOnly no-write guard |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*audit*.py" -q
& $py -m unittest tests.python.desktop.test_service_failure_markers -q
& $py -m unittest tests.python.desktop.test_service_failure_retry_state -q
& $py -m unittest tests.python.desktop.test_rerun_results_network_projection tests.python.desktop.test_process_rerun_results -q
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PortablePathChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-AuditCommandSupportChecks.ps1
```

---

### Settings

Tests for settings validation, patch preview, save, and facade policies.

| Test file | What it covers |
|---|---|
| `test_facade_settings_policy.py` | Facade: settings workspace policy, including read-only encoder capability report evidence from `State\Progress\encoder_capabilities.json` |
| `test_facade_settings_patch_policy.py` | Facade: settings patch/save policy |
| `test_application_facade_settings_workspace.py` | Application-facade Settings workspace redaction, metadata, media-policy readiness, tool-path evidence, and Validate command-result envelope |
| `test_application_facade_settings_patch.py` | Application-facade Settings Preview Patch/Save Patch command behavior, redacted diff fallback logging, risk summaries, save-lock guarding, backup/secret preservation, and no-op same-value handling |
| `test_settings_risk_policy_rules.py` | Settings risk classification plus clean template source-safety defaults |
| `test_facade_maintenance_policy.py` | Facade: maintenance policy |
| `test_facade_maintenance_command_policy.py` | Facade: maintenance command policy |
| `test_application_facade_maintenance.py` | Application-facade Maintenance workspace environment-health rows, Release Package dry-run plan/progress behavior, and maintenance command-lock fail-closed behavior |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test_facade_settings*.py" -q
```

---

### Folder Policy

Tests for folder validation contracts, probing, and I/O.

| Test file | What it covers |
|---|---|
| `test_service_folder_policy_contracts.py` | Folder policy contract rules |
| `test_service_folder_policy_probe.py` | Folder probe logic |
| `test_service_folder_policy_io.py` | Folder I/O helpers |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*folder_policy*.py" -q
```

---

### Paths and Files

Tests for path normalization, layout, state migration, defaults, and resolution runners.

| Test file | What it covers |
|---|---|
| `test_service_paths.py` | General path service |
| `test_service_path_layout.py` | Path layout resolution |
| `test_service_path_state_migration.py` | Legacy state migration and Protocol-typed app-state migration service boundary |
| `test_service_path_defaults.py` | Default path computation |
| `test_service_path_host_runner.py` | Host path runner and Protocol-typed PowerShell host service boundary |
| `test_service_path_resolution_runner.py` | Path resolution runner and Protocol-typed resolved-path service boundary |
| `test_service_file_open_plan.py` | File open plan construction |
| `test_service_file_open.py` | File open service |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*path*.py" -q
```

---

### Network Mode

Tests for coordinator/worker state, persistence, auth, source policy, mDNS, local IP detection, and WebView network boundary rules.

| Test file | What it covers |
|---|---|
| `test_network_security.py` | Network auth/token handling, coordinator request caps, worker identity validation, URL validation, registry ownership rejection, bounded worker HTTP reads, and log sanitization |
| `test_network_workflow.py` | Workflow enhancement regressions for local claim/release resilience, heartbeat and done/release HTTP outcomes, queue-removal scheduling, coordinator hardening, cluster-log formatting, retry hints, and worker wait policy |
| `test_network_worker_runtime.py` | Worker runtime and resilience coverage for diagnostics bounds, daemon-thread failures, source path mapping, status callbacks, cluster-log posting, poll-loop handoff, heartbeat failures, malformed claims, reclaimed jobs, and claim handoff diagnostics |
| `test_network_coordinator_helpers.py` | Coordinator URL/share-block helpers, coordinator/worker auth probes, coordinator HTTP helper validation, coordinator policy coercion, encode-config snapshot delegation, and prior-failure policy |
| `test_network_coordinator_http.py` | Bounded HTTP JSON helpers, coordinator JSON response and OPTIONS handling, coordinator request-body and identifier rejection, heartbeat/done registry failures, `/api/log` sanitization, and HTTP error previews |
| `test_network_protocol_runtime.py` | Protocol non-finite validation, in-flight registry runtime snapshot sanitization, reclaimed heartbeat handling, worker claim-record handoff, done-request builders, and worker poll policy |
| `test_network_firewall.py` | Firewall rule parsing, add-rule command construction, bounded `netsh` subprocess checks, nonzero/admin warning messages, and firewall output surfacing |
| `test_network_worker_state.py` | Worker-state atomic writes, job identity and pending done-report round trips, save-failure operator visibility, non-finite JSON rejection, temporary cleanup diagnostics, and guarded cleanup context |
| `test_network_inflight_registry.py` | In-flight registry persistence, concurrent save safety, registry save-failure diagnostics, non-finite value sanitization, config JSON rejection, and malformed row loading |
| `test_network_crash_recovery.py` | Worker crash recovery, pending done-report retry, bounded failure diagnostics, malformed worker-state handling, cluster-log failure handling, and accepted-report cleanup failures |
| `test_network_done_release.py` | Worker done/release reporting, pending done-report save failure handling, accepted-report cleanup, bounded diagnostics, unstartable-claim release reporting, and `DoneRequest` terminal fields |
| `test_network_rerun_claims.py` | Network CSV rerun row claim/release/done reduction, exact claim ownership, stale-reclaim ordering, killable source probes, typed outage retry/exhaustion, identity-safe reconnect, idempotent manual retry, worker handoff isolation, and coordinator-owned destination-policy outcomes |
| `test_network_coordinator_startup.py` | Coordinator startup behavior |
| `test_network_coordinator_source_policy.py` | Coordinator source policy and path handling |
| `test_network_worker_source_policy.py` | Worker source policy, path handling, and worker poll interval handoff through the named config key plus shared policy helper |
| `test_network_local_ip.py` | Local IP selection helpers |
| `test_network_mdns.py` | mDNS registration/discovery helpers |
| `test_application_facade_network.py` | Application-facade read-only Network worker-state metadata, progress bars, backend-authored heartbeat age, state-file evidence, and lifecycle-control absence |
| `test_webview_network_read_only_boundary.py` | Rendered Workers page network boundary, diagnostics buttons, backend-owned lifecycle buttons, disabled future controls, lifecycle contract display reference, and route-effect checks |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
& $py -m unittest tests.python.desktop.test_api_contract_payload tests.python.desktop.test_application_facade_network tests.webview.test_webview_network_read_only_boundary -q
```

---

### Local API and Contracts

Tests for API route payloads, command payloads, handler dispatch, command journal, static file serving, HTTP helpers, and backend bootstrap.

| Test file | What it covers |
|---|---|
| `test_api_read_payloads_policy.py` | Read route payload shapes |
| `test_api_command_results_policy.py` | Command route result payload handling |
| `test_api_contract_payload.py` | Route contract payload, auth/effect classification, effectful POST command-result history contract, Network lifecycle design-only dry-run/rollback/source-policy/exposure contracts, repair/reconcile design-only dry-run/rollback/source-policy/exposure contracts, CSV rerun auto-return defaults, and strict rerun control/continue command contracts |
| `test_api_command_journal_policy.py` | Command journal recording policy |
| `test_api_handler_policy.py` | Handler dispatch policy |
| `test_api_static_files_policy.py` | Static file serving policy, WebView include expansion for shell/Home/Telemetry/Queue/Completed/Pending/Rename/Launch/Reports/Schedule/Maintenance/Workers/Diagnostics/Settings partials, rendered bootstrap replacement, and unsafe include rejection |
| `test_api_path_dialogs.py` | Windows path-dialog helper behavior for Rename browse host resolution, command invocation, JSON payload parsing, and failure diagnostics |
| `test_api_http_helpers.py` | HTTP helper utilities |
| `test_backend_bootstrap.py` | Backend startup and token bootstrap |
| `test_application_facade_core_contracts.py` | Command-result serialization, runtime outcome normalization/indexing, command journal bounded persistence and strict JSON cleanup, Local API HTTP helper guards, static bootstrap/asset helper behavior, and route-map coverage against the documented contract |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test_api*.py" -q
& $py -m unittest tests.python.desktop.test_backend_bootstrap -q
```

---

### Desktop Controllers

Tests for historical legacy desktop-shell controller boundaries, controller-owned UI state, status server helpers, queue/report/dashboard rendering, worker job reporting, process lifecycle orchestration, and controller failure logging.

| Test file | What it covers |
|---|---|
| `test_controllers_pipeline.py` | Pause/stop/rescan flag command-surface handling and sleep-second parsing |
| `test_controllers_notification.py` | Background completion/failure notification dispatch, test toast delivery, Windows notification failure logging, and focus-check failure logging |
| `test_controllers_telemetry.py` | Telemetry dashboard non-finite CPU/GPU/RAM display sanitization and ffmpeg GPU-note rendering |
| `test_controllers_status_presentation.py` | Topbar chip/window title/taskbar/command-bar updates, audit current-file formatting, and taskbar progress failure logging |
| `test_controllers_home.py` | Home dashboard idle-state rendering, pending-publish summary/timing, pending payload stat failure logging, and live queue overview/selection |
| `test_controllers_diagnostics.py` | Historical diagnostics log-search reset failure logging and current-match reset failure logging under the removed legacy desktop-shell shim |
| `test_controllers_process_lifecycle.py` | Completed pipeline/audit handle synchronization, shutdown cleanup failure logging, pipeline/audit launch prep, schedule-window launch state, and kill-and-quit cleanup |
| `test_controllers_worker_jobs.py` | Worker completion event matching, fail-closed completion reports, malformed event skipping, dispatcher completion reporting, single-file launch failure handling, start UI failure handling, and worker abort/reclaim kill coverage |
| `test_controllers_network.py` | Coordinator status notice rendering, coordinator notice failure logging, coordinator button update failure logging, dispatcher error/shutdown failure logging, and worker status post failure logging |
| `test_controllers_navigation.py` | View routing/refresh/sidebar behavior, Network tab lifecycle failure logging, sidebar badge rendering, shortcut overlay guards, global shortcut bindings, filter trace/sort-heading/detail-copy wiring, and detail-copy failure logging |
| `test_application_facade_queue.py` | Queue preview snapshot-read behavior, normal-only row ownership, CSV rerun exclusion even when the normal queue is empty, compatibility metadata, stale evidence, blocked-vs-excluded rows, runtime outcome correlation, and row-key open allowlists |
| `test_controllers_feedback.py` | Action-status toast display, previous-toast cancellation, auto-dismiss scheduling, toast dismissal, recent-action recording, and recent-action text propagation |
| `test_controllers_worker_board.py` | Live worker-board snapshot row rendering, stale-row cleanup logging, snapshot failure fail-closed behavior, missing-worker-id logging, and per-row render failure isolation |
| `test_controllers_audit.py` | Audit report filtering/detail rendering, duplicate index behavior, multi-selection summaries, quick-view filters, context menu behavior, CSV apply/report metadata handling, creation-time failure logging, selected-row copy/open/priority actions, and selected/filtered CSV export |
| `test_controllers_failure.py` | Failure report filtering/detail/trend rendering, filter reset behavior, JSON/marker/clear-result application, selected-source open/copy/priority/audit-match actions, context menu behavior, and selected-failure re-run prioritization |
| `test_application_facade_completed.py` / `test_application_facade_web_static_completed.py` | Completed manifest policy/facade projection and backend-served Completed WebView static rendering coverage |
| `test_controllers_settings.py` | Settings profile save/load, list/path helper behavior, dirty-state and structured-control toggles, structured-control failure logging, unsaved-start prompt handling, config form validation/preview, missing saved-config diff logging, and save-in-place reload behavior |
| `test_controllers_file_actions.py` | Resolved log/local-base/report/config open handoffs, latest failure/audit CSV lookups, loaded audit CSV handoff, and empty path warning behavior |
| `test_controllers_maintenance.py` | Progress-file skeleton reset, resolved progress-path updates, reset action/status recording, confirmation dialogs, environment-health background dispatch, and environment-health result formatting |
| `test_controllers_folder_policy.py` | Folder-policy validation result status text, action-status text, command history action recording, success info dialog, and error/warning detail dialog formatting |
| `test_controllers_release.py` | Release package success status/action handling, manifest and zip path storage, manifest summary output formatting, and timeout output without success action recording |
| `test_rerun_csv_preview.py`, `test_rerun_lifecycle.py`, `test_application_facade_process_launch.py`, `test_application_facade_web_static_queue.py`, `test_application_facade_web_static_launch.py`, `test_process_rerun_results.py` | Typed CSV rerun preview, durable enrollment and strict child-exit proof, spawn-transition ambiguity, exact manifest/path/live-process correlation, deterministic current-batch selection, normal-queue separation, backend-only action rendering, blank Run Once normal-queue scope, and result promotion |
| `test_controllers_work_guard.py` | Work-guard active progress detection, stop-request handling, and related-process block messaging |
| `test_controllers_app_state.py` | App-state controller persistence, widget failure logging, refresh-state snapshot/autoload, polling completed-manifest refresh, and apply-snapshot-to-UI behavior |
| `test_controllers_status_server.py` | Status-server path redaction, shutdown-failure logging, pause-flag read-failure logging, and non-finite telemetry JSON safety |
| `test_controllers.py` | Controller helper import-boundary regression coverage for split helper modules |

Targeted command:

```powershell
& $py -m unittest tests.python.desktop.test_application_facade_queue tests.python.desktop.test_application_facade_completed tests.python.desktop.test_application_facade_web_static_completed tests.python.desktop.test_rerun_csv_preview tests.python.desktop.test_application_facade_process_launch tests.python.desktop.test_application_facade_launch_preflight tests.python.desktop.test_application_facade_web_static tests.python.desktop.test_process_rerun_results -q
```

---

### Facade and Schedule

General facade policy and desktop shell bootstrap tests not covered by subsystem-specific groups.

| Test file | What it covers |
|---|---|
| `test_app_bootstrap.py` | Historical app bootstrap state/controller setup and static legacy launcher fallback contract |
| `test_application_facade.py` | Shared fixture/helper module for split application-facade tests; intentionally owns no direct tests |
| `test_application_public_api.py` | Application facade/DTO public API boundary: package-level exports, per-module literal `__all__` declarations, export uniqueness/completeness, and declared export importability |
| `test_phase4_storage_observability.py` | Phase 4 storage, command-journal, boundary-validation, SQLite mirror, and JSON-line logging contracts, including required-field preservation and duplicate-handler prevention |
| `test_application_facade_close_readiness.py` | Application-facade close-readiness fail-closed behavior for active/unknown runtime state, fresh progress, progress read failures, ActiveJobs, schedule-stop watcher, and related-process inspection failures |
| `test_application_facade_completed.py` | Application-facade completed/output preview evidence, validation-state child payload, size/runtime/missing-output classification, completed-open row-key allowlists, and completed-manifest backfill dry-run behavior |
| `test_application_facade_core_contracts.py` | Application-facade core contract helpers: command-result serialization, runtime outcome normalization, command journal bounds, strict JSON guards, Local API HTTP helper guards, static bootstrap/asset helpers, and route-map coverage |
| `test_application_facade_diagnostics.py` | Application-facade diagnostics allowlists, read-only state-summary artifact evidence, blocked BDPGS OCR path surfacing, and diagnostics path lookup failure logging |
| `test_application_facade_local_api_http.py` | Local API HTTP/auth/public-token boundaries, contract route metadata, strict JSON response failure handling, snapshot telemetry DTO exposure, launch preflight nested readiness DTO exposure, and route effect metadata |
| `test_application_facade_local_api_diagnostics.py` | Local API diagnostics tail and state-summary allowlist route handling |
| `test_application_facade_local_api_network.py` | Local API Network lifecycle dry-run payload and command-journal suppression |
| `test_application_facade_local_api_repair.py` | Local API repair/reconcile dry-run schema, blocked preconditions, and command-journal suppression |
| `test_application_facade_local_api_settings.py` | Local API settings reload failure logging |
| `test_application_facade_local_api_lifecycle.py` | Local API close-readiness and backend shutdown safe/unsafe/force-cleanup/logging behavior |
| `test_application_facade_local_api_process_commands.py` | Local API process command auth, invalid-payload rejection, command-journal exception persistence, and scheduled continuous start watcher behavior |
| `test_application_facade_local_api_queue.py` | Local API queue state routes, priority/strategy/file override contracts, source scope, and command journaling |
| `test_application_facade_local_api_rename.py` | Local API rename browse, clean-filename preview, filter settings, apply/undo confirmation, active-work blocking, and root authority |
| `test_application_facade_local_api_workflow.py` | Local API completed/failure/audit/pending-publish workflow payloads plus maintenance, schedule, settings browse/save/reload, pipeline browse, diagnostics open, and command-history workflow contracts |
| `test_application_facade_maintenance.py` | Application-facade Maintenance workspace environment-health rows, toolchain evidence/progress rows, Release Package dry-run plan/progress behavior, and maintenance command-lock fail-closed behavior |
| `test_application_facade_network.py` | Application-facade Network worker-state metadata, progress bars, backend-authored heartbeat age, state-file evidence, and lifecycle-control absence for `/api/network/workers` |
| `test_application_facade_pending_publish.py` | Application-facade pending-publish preview classification, durable drain-summary evidence, publish reconciliation, row-key open allowlists, scan-failure surfacing, and backend-authored recovery dry-run planning |
| `test_application_facade_process_control.py` | Application-facade pipeline control flag contract, exact killed pipeline PID/Run ID gating for Force Stop Run Monitor takeover, no-process and unrelated audit/rerun non-terminalization, invalid action rejection, and control-lock fail-closed behavior |
| `test_application_facade_process_launch.py` | Application-facade pipeline/audit/rerun launch handoff, durable rerun enrollment, copied-manifest identity handling, strict failed-before-manifest generation supersession, verified-versus-ambiguous post-spawn cleanup, duplicate pipeline rejection, launch-lock fail-closed behavior, schedule handling, and accepted Backend Queue run identity |
| `test_application_facade_launch_preflight.py` | Read-only pipeline/audit/rerun launch readiness, current Queue-plan provenance/name/content-digest gates, path-health timeouts, encoder-capability evidence, UNC audit paths, and schedule/lock blockers |
| `test_application_facade_network_lifecycle.py` | Network-role launch rejection, coordinator/worker lifecycle provider behavior, strict journal ordering, duplicate/concurrency guards, and redaction |
| `test_application_facade_network_rerun_launch.py` | Network rerun dry-run/start, claim-enabled batch state, claim/done/release handoff, stale fingerprint rejection, and journal-failure cleanup |
| `test_application_facade_queue.py` | Application-facade normal-only queue preview behavior, stale evidence, blocked-vs-excluded rows, runtime outcome correlation, explicit CSV rerun exclusion and compatibility metadata, and row-key open allowlists |
| `test_application_facade_rename.py` | Application-facade rename preview/apply command behavior, selected-source scoping, multiple-selection handling, undo-manifest cleanup in temp fixtures, and apply-lock guarding |
| `test_application_facade_reports.py` | Application-facade Reports behavior for failure JSON, failure markers, lifecycle journal transitions, marker-clear confirmation handoff, evidence archive, and audit CSV rows |
| `test_application_facade_schedule.py` | Application-facade Schedule workspace rendering, backend watcher evidence, preview/save confirmation, app-state preservation, and invalid-time rejection |
| `test_application_facade_settings_patch.py` | Application-facade Settings Preview Patch/Save Patch behavior, risk summaries, redacted diff fallback, save-lock guard, backup/secret preservation, and no-op same-value handling |
| `test_application_facade_settings_workspace.py` | Application-facade Settings workspace redaction, path/field metadata, validation warning surfacing, backend media-policy readiness evidence, tool-path evidence, and Validate command-result envelope coverage |
| `test_application_facade_snapshot.py` | Application-facade snapshot assembly, active-work summary fields, progress bar shaping, active-job diagnostics rows, pending-publish copy byte progress, and zero-percent GPU telemetry presence |
| `test_application_facade_web_static.py` | Backend-served WebView/Tauri static integration, route references, command allowlists, Dashboard command-surface ownership, active-work summary mapping for Home Live Run / Run Progress / Next 5 Videos, evidence/read-only panel guardrails, canonical rendered page H1 titles, Settings BDPGS OCR path builder/no-path-picker guard, Settings subtitle keyword list builder wiring, Completed validation-state checklist/proof copy, table selection/accessibility helpers, diagnostics handoff, state-aware Launch command controls, emergency topbar Force Stop posture, UI tooltip/error/telemetry guards, page-scoped IDs, and headless backend bootstrap payload coverage |
| `test_facade_schedule_policy.py` | Facade: schedule policy |
| `test_facade_status_policy.py` | Facade: status policy |
| `test_facade_diagnostics_open_policy.py` | Facade: diagnostics open policy |

---

### Release / Packaging

Tests for release plan construction, result validation, change-control metadata, and the release self-test gate.

| Test file | What it covers |
|---|---|
| `test_service_release_plan.py` | Release plan logic |
| `test_service_release_result.py` | Release result validation |
| `tests/python/tooling/test_change_control.py`, `tests/python/tooling/test_archive_completed_changes.py` | Change-control release-manifest preview behavior, completed-packet archival and rollback, safe version labels, and missing-version diagnostics |
| `ops/scripts/ops/release/metadata/test.ps1` | Bundle layout, release-manifest hygiene, WebView include/asset checks, API browser token posture, parser/syntax checks, desktop unit discovery, environment verifier, Tauri prereqs, and current regression wrapper execution |

Targeted command:

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test*release*.py" -q
& $py -m unittest tests.tooling.test_change_control -q
.\ops\scripts\release\test.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

---

### Tauri Shell and WebView (Non-Browser)

Static and scaffold tests for Tauri shell setup and WebView JS assets.

| Test file | What it covers |
|---|---|
| `test_tauri_shell_scaffold.py` | Tauri shell file layout, backend launch/bootstrap/contract/WebView asset gates, close-readiness shutdown boundary, backend lifecycle monitor wiring, per-user Windows single-instance guard, read-only WebView lifecycle bridge/banner, production-surface audit script presence, no direct pipeline/FFmpeg launch, no `Invoke-Expression` in wrappers, PS7 syntax |
| `test_webview_css_design_tokens.py` | WebView CSS design-token discipline, token/theme/layout/component/page/control/layout-manager/queue import split, layout-manager drag-hint selector ownership, focus/status-chip styling, and workflow-table/status-chip static wiring |
| `test_webview_inventory_docs.py` | Rendered DOM ID inventory drift, WebView global export inventory/manifest drift, and `window.mediaPipeline*` namespace object JSDoc boundary coverage |
| `test_webview_navigation_static.py` | WebView rendered HTML/JS asset structure, nav links, DOM ID uniqueness |
| `test_webview_frontend_mutation_boundary.py` | WebView `apiPost` call ownership, documented POST route usage, shell-open selector payloads, confirmation payloads, centralized fetch, no direct frontend filesystem/process/Tauri APIs except the event-only `tauriLifecycleBridge.js` and exact no-argument `open_pipeline_log_window` invocation in `pipelineLogWindowBridge.js`, read-only bridge assertions, frontend media-policy risk helpers labelled advisory-only, and repair/reconcile command-route exposure blocked while `/api/contract` remains design-only with dry-run/rollback/source-policy/exposure fields |
| `test_webview_rerun_lifecycle_contract.py` | Local and Network CSV rerun accepted-versus-started labels, terminal pre-manifest rendering, backend-authored retry timeline/counts/actions, strict confirmation fields, request IDs, allowlisted routes, and no redundant safe-retry prompt |
| `test_webview_handbrake_settings_ui.py` | Settings tab grouping, builder metadata alignment, backend-owned save/preview boundaries, video/detail builder coverage, and read-only encoder capability report evidence annotations |
| `test_webview_network_read_only_boundary.py` | Rendered WebView Workers page network boundary, diagnostics buttons, backend-owned lifecycle controls, disabled future controls, lifecycle contract display reference, and `/api/network/workers` plus Network lifecycle routes |

Targeted command:

```powershell
$py = "apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.test_tauri_shell_scaffold -q
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_inventory_docs -q
& $py -m unittest tests.webview.test_webview_navigation_static -q
& $py -m unittest tests.webview.test_webview_frontend_mutation_boundary -q
powershell -NoProfile -ExecutionPolicy Bypass -File apps\desktop\tauri\Test-TauriShell-ProductionSurface.ps1
```

---

### WebView Browser-Backed Smokes

Browser-backed smoke tests live under `tests\webview\`. They require Chrome or
Edge; canonical wrappers fail a prerequisite skip by default. Use
`-AllowSkippedTests` only for a declared diagnostic run.

| Test file | What it covers |
|---|---|
| `test_webview_browser_high_risk_smoke.py` | Blocked Queue, broken Completed, do-not-drain Pending rows under real browser |
| `test_webview_browser_schedule_smoke.py` | Schedule Editor preview/save routing, command-history ownership, Launch timing trust after refresh |
| `test_webview_browser_lifecycle_smoke.py` | Backend lifecycle and Close Readiness; watcher-armed shutdown blocked; safe shutdown via backend-owned route only |
| `test_webview_browser_lifecycle_reconciliation_smoke.py` | Temporary-state abnormal-exit reconciliation using production lease/recovery APIs: live helper PID blocks recovery, stale fingerprints fail closed, exact evidence applies once, archived journal survives reload, and close-readiness becomes safe; no real pipeline child or media processing |
| `test_webview_browser_diagnostics_handoff_smoke.py` | Table clicks, filter guardrails, diagnostics bridge/tail/open, owner-row navigation |
| `test_webview_browser_pending_drain_guard_smoke.py` | Publish Button Guard refresh, blocked drain does not POST |
| `test_webview_browser_completed_pending_proof_smoke.py` | Completed-to-Pending proof board, Completed Manifest correlation |
| `test_webview_browser_large_table_smoke.py` | 260-row render-cap disclosure, filter warnings, hidden selected-row detail, no mutation posts |
| `test_webview_browser_maintenance_change_ledger_smoke.py` | Maintenance Change Ledger summary/table/detail/hygiene, filters, empty state, and read-only GET usage |
| `test_webview_browser_maintenance_reports_smoke.py` | Maintenance health/dry-run result rendering, Reports triage, tab placement, retry-state display, marker-clear payload guard |
| `test_webview_browser_sample_validation_smoke.py` | Home sample-validation pilot/readiness/reconciliation, worksheet detail, preview-only backend route |
| `test_webview_browser_home_live_state_smoke.py` | Home Daily-Driver, Operator Readiness, active work, command history, live progress evidence, page-switch viewport reset |
| `test_webview_browser_launch_queue_readiness_smoke.py` | Launch/Queue/Schedule readiness, Queue CSV Rerun tab visibility, scope reconciliation, sample proof handoff, no POSTs |
| `test_webview_browser_queue_launch_completed_smoke.py` | Passing standard Backend Queue Run Once journey through two distinct raw release-name sources, verified clean planned names, exact accepted membership/Queue-plan/content fingerprints/run identity, folded filename preview and opened selection, starting/scanning, all-worker handoff, terminal Completed/review evidence, clean-name announcements, exact proof focus, reload persistence, fresh idle, safe close-readiness, unchanged source hashes, and suppression of a recent unrelated-run `job_completed` event; no FFmpeg or PowerShell pipeline child is used |
| `test_webview_browser_run_monitor_smoke.py` | Deterministic Current Work state matrix, backend-planned rename filenames with raw source identity retained as secondary accessible evidence, first-20 filename preview, complete selectable expansion, planned/executed/final route separation, all-worker identity, per-track evidence, stale/partial suppression, exact dynamic focus and fold-state retention across same-run refresh plus safe disclosure-focus reset on different-run replacement, explicit terminal owner/next-action guidance, parked/Stop After Current announcements, keyboard behavior, responsive stacked labels, viewport-equivalent zoom reflow, and computed AA contrast in both themes; actual browser zoom and screen-reader checks remain manual |
| `test_webview_browser_layout_manager_smoke.py` | Layout Editor drawer coverage across page tabs, subtabs, and generated subsections with no mutation posts |
| `test_webview_browser_library_profiles_save_smoke.py` | Isolated temporary Library Profile add/save, strict backend review confirmation, digest, and reload persistence |
| `test_webview_browser_metrics_degraded_state.py` | Focused browser rendering for degraded/partial metrics state; intentionally has no canonical wrapper |
| `test_webview_browser_prose_box_audit.py` | Screenshot-backed visible prose/status/diagnostic-box audit across primary pages and subtabs |
| `test_webview_browser_queue_file_overrides_smoke.py` | File Settings drawer, dirty-state guards, intercepted save/clear payloads, series previews, and failure tone |
| `test_webview_browser_rename_smoke.py` | Rename row click, Apply Readiness, duplicate-target blocking does not call apply |
| `test_webview_browser_network_smoke.py` | Read-only Network worker visibility and filter guardrails |
| `test_webview_browser_telemetry_smoke.py` | Idle NVENC at 0%, GPU detail rows, CPU/RAM-only fallback |
| `test_webview_browser_visual_clutter_screenshots.py` | Desktop/mobile screenshot and overflow/clutter evidence |
| `test_webview_browser_settings_builder_flush_smoke.py` | Focused builder flush/staging timing coverage; intentionally has no canonical wrapper |
| `test_webview_browser_settings_field_matrix_smoke.py` | Backend-metadata-derived field coverage across all ten Settings panes, builder stage/reset semantics, Library overrides, and one isolated temp-config save/reload; no production settings or media mutation |
| `test_webview_browser_settings_launch_smoke.py` | Staged settings patch handoff, Settings-to-Launch intent, save-patch not called |

Run all via:

```powershell
& $py -m unittest discover -s tests\webview -p "test_webview_browser_*.py" -q
```

Use `ops/scripts/smoke/` wrappers for the operator-friendly path: `.\ops/scripts/smoke\Test-WebViewBrowser*.ps1`.
There are 34 browser Python modules in this inventory and 25 canonical browser
wrappers; the 9 direct-only browser Python modules are identified by the
generated smoke-wrapper map.

---

### WebView Non-Browser Smokes

Node.js-backed smoke tests that evaluate WebView JS with mocked DOM state.

| Test file | What it covers |
|---|---|
| `test_webview_command_evidence_smoke.py` | Shared command owner/issue evidence across all page histories |
| `test_webview_row_detail_smoke.py` | Queue, Completed, Pending selected-row detail rendering, including Completed validation-state proof-gap copy |
| `test_webview_rename_readiness_smoke.py` | Apply Readiness for ready and blocked duplicate-target scopes |
| `test_webview_real_media_smoke.py` | Fixture-backed backend API + WebView asset agreement for one TV sample |

Run via `ops/scripts/smoke/` wrappers: `.\ops/scripts/smoke\Test-WebViewCommandEvidenceSmoke.ps1`, `.\ops/scripts/smoke\Test-WebViewRowDetailSmoke.ps1`, etc.

---

### Python Stage Dispatcher Mutation Tests

| Test file | What it covers |
|---|---|
| `tests/python/core/subtitles/test_stage_subtitle_convert.py` | Standalone scratch ASS/SSA dry-run and SRT execute, strict confirmation, trusted path/source boundaries, content-bound fingerprint, command/operation journals, duplicate replay, input hash preservation, no-overwrite behavior, review routing, PowerShell-independent output, and rollback after terminal-evidence failure |

This is temporary standalone-subtitle fixture coverage. It does not cover real
TX3G extraction, BDPGS OCR, embedded streams, language routing, container
mutation, or production PowerShell integration.

---

## Known Coverage Gaps

| Area | Gap | Priority |
|---|---|---|
| Rename | Real native dialog display and network path-rewrite behavior | Medium |
| Pending Publish | Recovery-plan action coverage, completed-manifest/drain-summary cross-check depth, and coordinator-mode pending-publish handoff | Medium |
| Process lifecycle | Real pipeline-child orphan recovery and native Tauri close/reopen UX; temporary-state browser reconciliation now covers a live helper PID, stale evidence, exactly-once recovery, reload, and safe close-readiness | Medium |
| Real-media routing | No automated test covers FFmpeg encode/remux correctness on real files | High (needs real-media playbook) |
| Subtitle conversion | Scratch ASS/SSA conversion has representative text-fixture coverage; no automated test converts a real embedded ASS, TX3G, or BDPGS stream through production policy | High (needs real-media playbook) |

Coverage gaps are tracked as documentation observations. They do not require immediate code changes.

---

## See Also

- Rename safety inventory: `docs/inventories/RENAME_SAFETY_TEST_INVENTORY.md`
- Pending publish fixture inventory: `docs/inventories/PENDING_PUBLISH_FIXTURE_INVENTORY.md`
- Validation ladder: `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- Browser smoke runbook: `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
