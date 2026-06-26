# Dead Code Audit - 2026-06-17

Change packet: `MP-CHANGE-2026-0617-007`

Scope: report-only static audit. No source, config, test, script, schema, WebView, Tauri, media-policy, queue, pending-publish, FFmpeg, subtitle, audio, or generated-contract behavior was changed.

## 1. Executive summary

This audit found no safe "delete immediately" candidate in high-risk media, publish, queue, or settings behavior. The strongest low-risk cleanup candidates are isolated definition-only helpers in dev tooling and WebView static JavaScript. Several public-looking Python contract classes and PowerShell functions also have no static references, but they need runtime verification because this project uses dynamic command routing, PowerShell dot-sourcing, local API route maps, compatibility imports, and WebView globals.

Primary findings:

| Area | Result |
| --- | --- |
| Python | 7 definition-only symbols were identified as probably dead or needing runtime verification. Contract payload classes and queue helpers should not be removed until route-schema and external import checks pass. |
| WebView JavaScript | 7 definition-only helpers were identified. Most look like local leftovers after the static asset split or newer queue rendering code. |
| PowerShell | 10 definition-only functions were identified. Several are dangerous to remove because they sit near path policy, queue final-state writes, process execution, subtitles, or publish sidecars. |
| API routes | Subtitle QA and Tdarr Matrix routes have no obvious WebView route caller evidence, but they are documented contracts and tested. Treat as backend-only or needs runtime verification, not confirmed dead. |
| Config/settings | No confirmed unused key was found in the template/profile key scan. `WorkerConfigOverrides` is a backend-disabled compatibility setting, not dead. |
| Docs/tests/scripts | Active docs and tests still contain intentional removed-root-launcher guardrails, plus some stale forensic examples and dated architecture references. These are documentation-cleanup candidates, not behavior cleanup. |
| Compatibility shims | Desktop compatibility modules are superseded by core/kernel modules in design intent, but they remain heavily imported by core code and are not removable yet. |

Recommended cleanup order:

1. Clarify stale docs and route inventories first.
2. Remove or inline low-risk WebView/dev-tool helpers only after targeted static checks.
3. Retire Python public helper/classes only after route contract and import compatibility checks.
4. Defer PowerShell media/path/publish helpers until release-gate and real-media validation can cover the behavior.
5. Do not remove compatibility shims until the dependency-boundary allowlist is reduced and core imports no longer depend on `mediapipeline.desktop.*`.

## 2. Methodology and search terms

Required startup reads were completed in order:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`

Generated summaries were checked before source reads where available, including summaries for the Python, WebView, and PowerShell files named in this report. Full source snippets were opened only for high-priority summaries or to verify specific symbols.

Static methods used:

- `rg --files` inventory by extension and domain.
- Tokenized Python definition scan for functions/classes with one active-code token occurrence.
- Tokenized WebView JavaScript function scan with follow-up exact `rg` checks to filter IIFE and named-function-expression false positives.
- PowerShell `function` definition scan with exact symbol searches across active `ops`, `src`, `apps`, and `tests`.
- API route literal search across WebView static assets, Local API contracts, route maps, tests, and inventories.
- Config key extraction from `ops/pipeline/config/MediaPipeline_config_template.psd1` and `ops/pipeline/config/profiles/Default.psd1`, followed by active-code reference counts.
- Launcher-reference audit excluding `docs/archive/**` and generated summaries.
- Clean TODO/FIXME/HACK scan excluding runtime/vendor/target/generated-summary trees.

Representative search terms:

```powershell
rg -n "Start-MediaPipelineRemuxEncodeAIO|Run-MediaPipelineRemuxEncodeAIO|Setup-MediaPipelineRemuxEncodeAIO|Verify-MediaPipelineRemuxEncodeAIO|Build-MediaPipelineRemuxEncodeAIO|Test-MediaPipelineRemuxEncodeAIO|New-RealMediaValidationWorksheet\.ps1" -g "!docs/archive/**" -g "!docs/generated/summaries/**"
rg -n "TODO|FIXME|HACK" src apps ops tests docs -g "!docs/archive/**" -g "!docs/generated/summaries/**" -g "!apps/desktop/runtime/**" -g "!apps/desktop/tauri/src-tauri/target/**" -g "!ops/pipeline/runtime/**" -g "!ops/pipeline/tools/**"
rg -n "mediapipeline\.desktop\.(models|models_core|models_media_paths|config_keys|subprocess_runner|contracts|application\.dto)" src tests apps ops docs -g "!docs/archive/**" -g "!docs/generated/summaries/**"
rg -n "/api/queue/file-overrides/(folder-preview|folder-rule)|/api/subtitle-qa/(summary|item|preview)|/api/diagnostics/tdarr-matrix/runs" apps/desktop/webview/static src tests docs -g "!docs/archive/**" -g "!docs/generated/summaries/**"
```

Classification definitions used:

- Confirmed dead: no references and no dynamic entrypoint evidence found.
- Probably dead: only definition or archive/doc references, with no observed active caller.
- Duplicate/superseded: a newer implementation exists and is referenced.
- Dangerous to remove: low references but the symbol sits near high-risk or dynamically invoked behavior.
- Needs runtime verification: static search cannot distinguish unused from dynamic/external/operator usage.

## 3. Dead-code inventory

No high-risk media-path candidate is classified as confirmed dead. The items below are static candidates that should enter a staged cleanup queue.

### Python candidates

| Path | Symbol/key/route/script | Classification | Search evidence | Why it appears dead | Removal risk | Safe verification step | Suggested removal order |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `src/mediapipeline/tools/dev/scan_archive_doc_candidates.py` | `_line_references_target` | Probably dead | Token scan found a single active-code occurrence at the definition; no active `rg` caller found. | The tool also has broader reference-index helpers; this private helper appears stranded. | Low. Dev tooling only, no runtime media path. | Run exact `rg "_line_references_target" src tests apps ops docs -g "!docs/archive/**"` and the archive-doc scanner tests or smoke command. | 1 |
| `src/mediapipeline/tools/dev/scan_archive_doc_candidates.py` | `collect_inbound_references` | Probably dead | `rg --fixed-strings "collect_inbound_references" src tests apps ops -g "*.py"` found only `def collect_inbound_references(`. | It delegates to `collect_reference_index`, which appears to be the active implementation. | Low. Dev tooling only. | Verify no CLI/import entrypoint exposes it, then run archive-doc candidate tooling. | 1 |
| `src/mediapipeline/desktop/network/auth.py` | `make_auth_header` | Probably dead | Exact active Python search found only `def make_auth_header(token: str) -> dict[str, str]:`. | Network auth call sites appear to use other token/signature helpers. | Medium. Network worker clients or external scripts may import it. | Run network coordinator/worker tests and import-graph check for `mediapipeline.desktop.network.auth`. | 3 |
| `src/mediapipeline/contracts/api_commands.py` | `QueuePriorityItemPayload` | Probably dead | Exact search found only the class definition. `QueuePriorityCommandPayload.items` is typed as `Any`, not this class. | Looks like an unused typed item model left behind after payload validation was generalized. | Medium. Contract/schema consumers may import it directly. | Regenerate/inspect API schemas and run `tests/python/desktop/test_api_contract_payload.py`. | 3 |
| `src/mediapipeline/contracts/api_commands.py` | `NetworkLifecycleCommandPayload` | Probably dead | Exact search found only the class definition. Specific network lifecycle route payloads are defined separately. | Looks like a generic base payload that was superseded by route-specific payload classes. | Medium. Contract modules may be externally imported. | Run contract route tests and search generated schemas for the class name. | 3 |
| `src/mediapipeline/core/queue/priority_manifest.py` | `list_high_paths` | Probably dead | Exact search found only `def list_high_paths(`. | Current API payload construction appears to use manifest serialization rather than exposing raw high-priority paths through this helper. | Medium. Queue priority behavior is operator-facing. | Run queue priority tests and inspect any CLI/import entrypoints. | 3 |
| `src/mediapipeline/core/queue/priority_manifest.py` | `list_hold_paths` | Probably dead | Exact search found only `def list_hold_paths(`. | Same pattern as `list_high_paths`; likely leftover convenience accessor. | Medium. Queue hold behavior is operator-facing. | Run queue priority/hold tests and inspect persisted manifest readers. | 3 |

### WebView JavaScript candidates

| Path | Symbol/key/route/script | Classification | Search evidence | Why it appears dead | Removal risk | Safe verification step | Suggested removal order |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `apps/desktop/webview/static/assets/app/layoutManager.js` | `_clearPanelHolding(panel)` | Probably dead | Exact `rg "_clearPanelHolding"` found only the definition around line 295. | `_setPanelHolding(panel, false)` remains available and callers do not use the wrapper. | Low. Local UI helper only. | Run WebView static checks and navigation smoke for panel visibility. | 2 |
| `apps/desktop/webview/static/assets/app/lifecycle.js` | `showCompletedOutputTab(tabId)` | Probably dead | Exact search found only the definition around line 763. | Completed tab activation is handled by newer navigation/state helpers. | Medium. Could be called from inline event handlers if not literal-searched. | Browser smoke completed-page tab actions and exact DOM attribute search for `showCompletedOutputTab`. | 2 |
| `apps/desktop/webview/static/assets/networkView.js` | `networkSourceKeysFromRow(row)` | Probably dead | Exact search found only the definition around line 536. | Network table rendering appears to use other row/source helpers. | Low to medium. Network view is operator-facing but helper is local. | Run network WebView smoke and network read-only boundary tests. | 2 |
| `apps/desktop/webview/static/assets/pendingPublishView.js` | `pendingRecoveryFallbackRows` | Probably dead | Exact name search found the fallback-row function assignment; adjacent fallback line/render helpers are referenced. | The row fallback path appears to have been replaced by fallback-line rendering. | Medium. Pending publish is high-risk, but this is UI fallback display only. | Run pending-publish view tests/smokes with missing recovery evidence payloads. | 2 |
| `apps/desktop/webview/static/assets/queueView.js` | `queueTableElement()` | Probably dead | Exact search found only the definition around line 781. | Queue table access appears to use newer table/render modules. | Medium. Queue view is central operator surface. | Run queue WebView static tests and queue table smoke. | 2 |
| `apps/desktop/webview/static/assets/queueView.js` | `queuePriorityBadgeLabel(level)` | Duplicate/superseded | Exact search found only the definition around line 1596; active priority badge rendering exists in `apps/desktop/webview/static/assets/queue/table.js`. | Newer queue table code renders effective priority badges directly. | Medium. Queue priority labels affect operator clarity. | Run queue priority UI tests and compare rendered high/hold badge labels. | 2 |
| `apps/desktop/webview/static/assets/settings/policyImpact.js` | `settingsPatchHasCandidatePercentKeys(entries)` | Probably dead | Exact search found only the definition around line 97. | Settings policy impact logic appears to compute candidate percent impact without this helper. | Medium. Settings save/preview behavior is release-sensitive. | Run settings patch candidate tests and settings WebView smoke. | 3 |

### PowerShell candidates

| Path | Symbol/key/route/script | Classification | Search evidence | Why it appears dead | Removal risk | Safe verification step | Suggested removal order |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ops/scripts/dev/verify-env.ps1` | `Test-IsBundledPythonPath` | Probably dead | PowerShell function scan found definition-only usage. | The verify-env script appears to resolve/validate Python through other checks. | Low. Dev environment validation only. | Run `.\ops\scripts\dev\verify-env.ps1` before and after removal. | 1 |
| `ops/pipeline/engine/shared/media_constants.ps1` | `Get-MediaSubtitleCodecWebVttName` | Probably dead | Function scan found only the definition around line 144. | Other subtitle codec constants are used, but WebVTT name helper has no caller. | Medium. Subtitle naming can affect stream handling. | Run subtitle unit tests and search generated script bundles if any. | 4 |
| `ops/pipeline/engine/shared/versioning.ps1` | `Get-MediaPipelineVersionInfo` | Needs runtime verification | Function scan found only the definition around line 39. | Public aggregate helper may have been kept for operators or release scripts. | Medium. Public PowerShell function surface may be imported externally. | Run release build/test scripts and grep packaged scripts. | 4 |
| `ops/pipeline/engine/shared/native.ps1` | `Get-CompletedTaskTextWithBoundedDrain` | Dangerous to remove | Function scan found only the definition around line 84. | May be older async process drain helper superseded by other native process helpers. | High. Native process draining can affect FFmpeg/helper output handling. | Run native/process unit tests and long-output subprocess smoke. | 5 |
| `ops/pipeline/engine/shared/path_helpers.ps1` | `Test-MediaPipelinePathHasReparsePoint` | Needs runtime verification | Function scan found only the definition around line 176. | Neighboring reparse-attribute helpers appear active; this may be an older wrapper. | High. Path safety and reparse points are source/output safety boundaries. | Run path safety tests and no-touch boundary checks. | 5 |
| `ops/pipeline/engine/paths/effective_settings.ps1` | `Resolve-MediaPipelineLibraryEffectiveSettingsForPath` | Dangerous to remove | Function scan found definition-only usage. | Public-looking path/settings helper may be called dynamically or by operators. | High. Library-profile path settings affect source/scratch/output behavior. | Run settings/profile/path tests and a representative dry-run with library profiles. | 5 |
| `ops/pipeline/engine/process/pipeline_plan_executor.ps1` | `Invoke-PipelinePlanExecutorDryRun` | Dangerous to remove | Function scan found definition-only usage around line 601. | Dry-run functions are often operator or smoke entrypoints without static callers. | High. Pipeline planning touches FFmpeg/remux/encode decisions. | Run plan executor unit tests and dry-run smoke through canonical entrypoints. | 5 |
| `ops/pipeline/engine/queue/worker_mutex.ps1` | `Invoke-MediaPipelineFinalStateWrite` | Dangerous to remove | Function scan found definition-only usage around line 72. | Final-state lock wrapper may be reserved for serialized queue/worker writes. | High. Queue/final-state writes are release-critical. | Run queue worker mutex tests and concurrent final-state write smoke. | 5 |
| `ops/pipeline/engine/subtitles/tx3g.ps1` | `Publish-Tx3gSrtSidecars` | Duplicate/superseded, dangerous to remove | Function scan found no caller; `Publish-Tx3gSrtSidecarsFromPlan` is called from publish completion and tested. | Direct helper appears superseded by plan-based publish sidecar flow. | High. Subtitle sidecar carry-forward and publish behavior are high-risk. | Run TX3G subtitle tests, publish sidecar tests, release gate, and real-media validation. | 5 |
| `ops/pipeline/engine/process/dynamic_hdr.ps1` | `Resolve-DynamicHdrPolicy` | Duplicate/superseded | Function scan found no caller; active code uses `Resolve-MediaPipelineDynamicHdrPolicy` from `ops/pipeline/engine/config/choice_registry.ps1`. | Local process helper duplicates the config choice registry. | Medium to high. Dynamic HDR policy affects encode planning. | Run config schema tests and dynamic HDR process planning tests. | 4 |

### API route usage candidates

| Path | Symbol/key/route/script | Classification | Search evidence | Why it appears dead | Removal risk | Safe verification step | Suggested removal order |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `src/mediapipeline/desktop/api/routes_read.py`, `src/mediapipeline/core/api/commands_subtitle_qa.py`, `src/mediapipeline/contracts/api_commands.py` | `GET /api/subtitle-qa/summary`, `GET /api/subtitle-qa/item`, `POST /api/subtitle-qa/preview` | Needs runtime verification | Route inventories list read routes with caller mode `none`; `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md` explicitly says `POST /api/subtitle-qa/preview` has no WebView caller. | WebView appears to consume embedded subtitle QA evidence in queue/completed payloads instead of calling these routes. | Medium. Routes are documented contracts and tested; external tools may use them. | Start Local API, capture route access during Queue/Completed subtitle QA flows, and run `tests/python/desktop/test_subtitle_qa_feature.py`. | 4 |
| `src/mediapipeline/desktop/api/routes_read.py`, `src/mediapipeline/desktop/api/read_payloads_status.py` | `GET /api/diagnostics/tdarr-matrix/runs` | Needs runtime verification | API inventory marks caller mode `none`; search found contracts/tests/docs but no WebView static literal route caller. | Looks like a backend diagnostics contract or future Diagnostics UI route. | Medium. Diagnostics route is non-mutating but operator-visible. | Run diagnostics UI smoke and route access logging. | 4 |
| `apps/desktop/webview/static/partials/page-network.html`, `apps/desktop/webview/static/assets/networkView.js` | `data-network-future-control` actions: drain, disable-new-work, pause, abort-current, reclaim-job, quarantine-worker | Needs runtime verification | Static HTML includes disabled future controls; `networkView.js` text says controls remain disabled until backend routes exist; tests assert they are disabled. | UI actions are intentionally unreachable placeholders. | Low if removed visually, high if backend policy changes are attempted. | Product decision first: either remove placeholders or implement backend routes and boundary tests. | 2 for UI removal, 5 for backend enablement |

## 4. Duplicate/superseded implementation inventory

| Path | Symbol/key/route/script | Classification | Search evidence | Why it appears dead or superseded | Removal risk | Safe verification step | Suggested removal order |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ops/pipeline/engine/process/dynamic_hdr.ps1` | `Get-DynamicHdrPolicyNames`, `Get-DynamicHdrPolicyDefault`, `Resolve-DynamicHdrPolicy` | Duplicate/superseded | Active code references `ops/pipeline/engine/config/choice_registry.ps1` functions `Get-MediaPipelineDynamicHdrPolicyNames` and `Resolve-MediaPipelineDynamicHdrPolicy`; runtime config uses the registry helper. | Policy choice validation appears centralized in the config choice registry. | Medium to high. Encode policy. | Remove only after dynamic HDR config/runtime tests confirm no dot-sourced caller. | 4 |
| `ops/pipeline/engine/subtitles/tx3g.ps1` | `Publish-Tx3gSrtSidecars` | Duplicate/superseded, dangerous to remove | `Publish-Tx3gSrtSidecarsFromPlan` is referenced by publish completion and tests; direct helper has no static caller. | Plan-based sidecar publication appears to be the current flow. | High. Subtitle sidecars and publish safety. | Real-media TX3G subtitle validation plus publish sidecar tests. | 5 |
| `apps/desktop/webview/static/assets/queueView.js` and `apps/desktop/webview/static/assets/queue/table.js` | `queuePriorityBadgeLabel` vs queue/table priority rendering | Duplicate/superseded | `queuePriorityBadgeLabel` definition-only; `queue/table.js` has active effective-priority badge rendering helpers. | Queue rendering moved into split queue table asset. | Medium. Operator priority display. | WebView queue static tests and visual smoke for priority badges. | 2 |
| `src/mediapipeline/desktop/config_keys.py`, `src/mediapipeline/desktop/models*.py`, `src/mediapipeline/desktop/subprocess_runner.py`, `src/mediapipeline/desktop/contracts/**`, `src/mediapipeline/desktop/application/dto*.py` | Desktop compatibility shims | Duplicate/superseded but still live | Project index labels many as compatibility shims; direct import search shows heavy active imports from `src/mediapipeline/core/**` and dependency-boundary allowlist entries. | Newer ownership belongs under `src/mediapipeline/core/kernel` and core domains, but imports have not been fully migrated. | High. Removing now breaks core imports and contracts. | First reduce `docs/architecture/dependency_boundary_allowlist.txt`, then run full Python test suite and package import smoke. | 5 |
| `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md` and WebView static assets | File override folder routes | Needs runtime verification | Inventories name `queue/fileOverrides.drawer.js` as owner for `/api/queue/file-overrides/folder-preview` and `/api/queue/file-overrides/folder-rule`; route literal search over `apps/desktop/webview/static` did not find those route strings. | Possible inventory drift, generated/static indirection, or stale tests/docs. | Medium. File override folder rules write queue state. | Run folder override drawer smoke and route logging; update inventory if route is no longer UI-called. | 3 |

## 5. Stale config/settings inventory

| Path | Symbol/key/route/script | Classification | Search evidence | Why it appears stale | Removal risk | Safe verification step | Suggested removal order |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ops/pipeline/config/MediaPipeline_config_template.psd1`, `ops/pipeline/config/profiles/Default.psd1` | 147 scanned template/profile keys | No confirmed dead key | Key extraction/reference scan found no key with zero or near-zero active references. | Static evidence does not support deleting config keys in this pass. | High if changed casually. Settings drive media policy and paths. | Run config schema/defaults tests before any future key removal. | Not a removal candidate |
| `apps/desktop/webview/static/partials/page-network.html`, `apps/desktop/webview/static/assets/networkView.js`, network tests/docs | `WorkerConfigOverrides` | Probably stale compatibility setting | UI text labels it "backend-disabled"; tests assert `WorkerConfigOverrides` is disabled by backend policy; docs call it compatibility-only/backend-disabled. | Persisted/displayed compatibility surface remains, but backend policy does not consume it for behavior. | High. Network worker policy and settings persistence. | Decide whether to remove the UI setting or formally deprecate it; run network coordinator/worker tests. | 3 |
| `docs/OPEN_WORK_CHECKLIST.md` and config compatibility surfaces | `OutsourcePath`, `ServerOut`, `OutputRoot` legacy sample-validation aliases | Dangerous to remove | Checklist documents compatibility alias work; broad search shows `ServerOut` also appears as active path/output terminology. | Some aliases may be compatibility-only, but names overlap with active runtime concepts. | High. Output roots and publish path safety. | Build a key-specific alias map before removal; run sample-validation and config compatibility tests. | 5 |
| WebView settings persistence | Settings persisted but never read | No confirmed finding | Static scan did not prove a persisted setting that is never read. | Several settings use dynamic key access and JSON patch handling, so simple string counts are insufficient. | High if guessed. Settings persistence is release-sensitive. | Instrument settings load/save/patch flows and compare LocalBase settings keys to runtime access logs. | Not a removal candidate |

## 6. Stale docs/tests/scripts inventory

| Path | Symbol/key/route/script | Classification | Search evidence | Why it appears stale | Removal risk | Safe verification step | Suggested removal order |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `docs/REMEDIATION_CHANGELOG.md` | Removed root launcher command examples | Probably dead/stale docs | Launcher search found many old root launcher examples in this forensic doc. | Current canonical launchers live under `ops/scripts/**`; root launchers were removed by 2026-05-30 confirmation. | Low for docs cleanup, medium if history is altered without preserving context. | Add an explicit historical-note banner or move examples to archive if not already treated as forensic. | 1 |
| `tests/python/desktop/test_tauri_shell_scaffold.py` | Negative assertions for removed root launchers | Probably stale tests, but intentional guardrail | Tests assert old root launcher names do not exist or are not referenced. | They cover removed behavior rather than active behavior, but protect against regression to root launchers. | Low to medium. Removing tests weakens legacy-surface guardrails. | Replace with a consolidated legacy-removal readiness test before deleting individual assertions. | 2 |
| `src/mediapipeline/tools/dev/check_legacy_removal_readiness.py`, `src/mediapipeline/core/telemetry/health.py` | Removed root launcher scanners/health absent-file checks | Dangerous to remove | Active code intentionally lists removed root launcher names as forbidden/absent paths. | Looks stale by name search, but it enforces current no-root-launcher policy. | Medium. Removing can allow legacy launcher drift. | Keep until another guardrail covers root launcher absence. | 4 |
| `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md` | `src\mediapipeline\desktop\config_keys.py` reference | Probably stale docs | Doc says key constants live in `desktop/config_keys.py`; current layout and project index point to core/kernel ownership with desktop compatibility shims. | Architecture guidance points at a compatibility shim rather than the canonical module. | Low. Docs only. | Update doc to name canonical key owner and note compatibility shim status. | 1 |
| `docs/CURRENT_PROJECT_STATE.md` | Dated `app/...` architecture paths in 2026-05-28 history bullets | Probably stale docs | Current layout is `src/mediapipeline/**`; dated history still names old `app/contracts/stages.py`, `app/orchestration/runner.py`, `app/observability/`, `app/validation/`. | Historical bullets can confuse onboarding if read as current path guidance. | Low. Preserve history while clarifying current path names. | Add "historical path names" wording or cross-reference the current project index. | 1 |
| `docs/inventories/API_ROUTE_INVENTORY.md`, `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`, `tests/python/desktop/test_application_facade_web_static.py` | File override folder route caller evidence | Needs runtime verification | Tests/docs expect folder route ownership; route literal search did not find WebView static route strings. | Could be stale inventory, generated indirection, or dynamically assembled route strings. | Medium. Folder override rules mutate queue state. | Run WebView drawer smoke and Local API route logging before changing docs/tests. | 3 |
| `ops/release/metadata/RELEASE_MANIFEST.json`, old change packets | Archived stale-doc TODO audit references | Probably stale metadata, not active TODO | Clean TODO/FIXME/HACK scan found active hits only in release metadata/old packets pointing to archived stale-doc audit names. | These are historical manifest references, not live TODO blocks. | Low. Release metadata may be immutable history. | Leave unless release metadata pruning policy exists. | Not a removal candidate |
| `docs/reviews/function-module-audit-2026-06-11/**` | Old audit inventories and route findings | Archive/review material; dangerous to treat as active | Searches found stale route and function data in review inventories. | Review artifacts are evidence snapshots and should not drive current implementation without re-verification. | Low if archived; medium if active docs link to them as current. | Mark review directory as historical or ensure active docs do not treat it as authoritative. | 1 |

## 7. Removal risk ranking

| Rank | Candidate group | Risk | Rationale |
| --- | --- | --- | --- |
| 1 | Stale docs clarifications in `docs/REMEDIATION_CHANGELOG.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, and historical path wording | Low | Documentation-only cleanup; no behavior surface if history is preserved. |
| 2 | Low-risk WebView helper removals such as `_clearPanelHolding`, `networkSourceKeysFromRow`, and `settingsPatchHasCandidatePercentKeys` | Low to medium | Static helpers appear definition-only, but WebView globals and DOM event indirection require smoke coverage. |
| 3 | Dev-tool helper removals in `scan_archive_doc_candidates.py` and `verify-env.ps1` | Low | Non-runtime developer tooling; still verify script entrypoints. |
| 4 | Python public contract/helper removals such as `QueuePriorityItemPayload`, `NetworkLifecycleCommandPayload`, `make_auth_header`, `list_high_paths`, `list_hold_paths` | Medium | No static callers, but public import and route-schema compatibility can matter. |
| 5 | Backend-only or no-WebView-caller API routes | Medium | Routes are tested/documented and may be used by external tools or future UI surfaces. |
| 6 | Compatibility shims under `src/mediapipeline/desktop/**` | High | They are superseded by design, but currently live through many core imports and boundary allowlist entries. |
| 7 | PowerShell path/process/queue/publish/subtitle helpers | High | Dot-sourcing and operator entrypoints are hard to prove statically; several touch release-critical behavior. |
| 8 | Config/settings aliases and backend-disabled network settings | High | Settings affect source/output safety, network worker policy, queue behavior, and persisted operator state. |

## 8. Safe cleanup roadmap

1. Documentation pass:
   - Clarify stale root-launcher examples in `docs/REMEDIATION_CHANGELOG.md` as historical.
   - Update `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md` to point at canonical config key ownership instead of the desktop compatibility shim.
   - Clarify historical `app/...` path references in `docs/CURRENT_PROJECT_STATE.md`.

2. Inventory and route proof pass:
   - Add a route-caller evidence column or timestamp to `docs/inventories/API_ROUTE_INVENTORY.md`.
   - Verify whether file override folder routes are called by WebView static code, generated route helpers, or not at all.
   - Confirm subtitle QA and Tdarr Matrix routes are intentionally backend-only if they remain without WebView callers.

3. Low-risk UI/helper cleanup:
   - Remove one WebView helper at a time.
   - Run targeted WebView static tests and the relevant smoke wrapper after each small group.
   - Prefer deleting wrappers that only call an existing helper, such as `_clearPanelHolding`, before queue/pending-publish helpers.

4. Python public-surface cleanup:
   - Remove or deprecate dev-tool helpers first.
   - For contract payload classes, regenerate schema artifacts or prove schemas do not include the class.
   - For queue priority helpers, prove no CLI/operator import and run queue priority tests.

5. Dependency-boundary migration:
   - Migrate core imports away from `mediapipeline.desktop.models`, `mediapipeline.desktop.application.dto*`, and `mediapipeline.desktop.subprocess_runner`.
   - Shrink `docs/architecture/dependency_boundary_allowlist.txt`.
   - Remove compatibility shims only after import graph shows no internal dependency.

6. High-risk PowerShell cleanup:
   - Start with non-media dev helpers.
   - Defer path, queue final-state, native process, dynamic HDR, and TX3G publish helpers until a release-gate window.
   - For subtitle/publish/process helpers, require representative real-media validation.

7. Settings/config cleanup:
   - Build a persisted LocalBase settings key inventory from real operator state.
   - Compare saved keys with backend read/access logs.
   - Deprecate before removal when external scripts or old LocalBase states may carry the key.

## 9. Validation recommendations

Minimum validation before any future cleanup:

- Exact reference check:
  - `rg --fixed-strings "<symbol>" src apps ops tests docs -g "!docs/archive/**" -g "!docs/generated/summaries/**"`
- Python:
  - `.\apps\desktop\runtime\Python\python.exe -m pytest tests/python/desktop/test_api_contract_payload.py`
  - Targeted queue priority, network auth, and dev-tool tests for touched modules.
- WebView:
  - Existing WebView static smoke/tests for queue, completed, network, pending publish, and settings.
  - Browser smoke for any DOM-visible action after helper cleanup.
- PowerShell:
  - Unit tests for affected `ops/pipeline/engine/**` domains.
  - Canonical script entrypoints under `ops/scripts/**`, not removed root launcher paths.
- API routes:
  - Start Local API with `apps/desktop` as app root.
  - Capture route access logs while exercising Queue, Completed, Diagnostics, and file override drawers.
- Media/publish/subtitle/audio/path changes:
  - Release gate plus representative real-media validation, per `AGENTS.md`.
- Change control:
  - `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage`

## 10. Appendix of searches/files reviewed

Required project files reviewed:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`

Generated summaries reviewed before source checks:

- `docs/generated/summaries/src/mediapipeline/tools/dev/scan_archive_doc_candidates.py.md`
- `docs/generated/summaries/src/mediapipeline/desktop/network/auth.py.md`
- `docs/generated/summaries/src/mediapipeline/contracts/api_commands.py.md`
- `docs/generated/summaries/src/mediapipeline/core/queue/priority_manifest.py.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/app/layoutManager.js.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/app/lifecycle.js.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/networkView.js.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/pendingPublishView.js.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/queueView.js.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/settings/policyImpact.js.md`
- `docs/generated/summaries/ops/pipeline/engine/process/dynamic_hdr.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/subtitles/tx3g.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/shared/native.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/process/pipeline_plan_executor.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/queue/worker_mutex.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/shared/media_constants.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/shared/path_helpers.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/shared/versioning.ps1.md`

Full source snippets reviewed for candidate verification:

- `src/mediapipeline/tools/dev/scan_archive_doc_candidates.py`
- `src/mediapipeline/desktop/network/auth.py`
- `src/mediapipeline/contracts/api_commands.py`
- `src/mediapipeline/core/queue/priority_manifest.py`
- `apps/desktop/webview/static/assets/app/layoutManager.js`
- `apps/desktop/webview/static/assets/app/lifecycle.js`
- `apps/desktop/webview/static/assets/networkView.js`
- `apps/desktop/webview/static/assets/pendingPublishView.js`
- `apps/desktop/webview/static/assets/queueView.js`
- `apps/desktop/webview/static/assets/settings/policyImpact.js`
- `ops/pipeline/engine/process/dynamic_hdr.ps1`
- `ops/pipeline/engine/subtitles/tx3g.ps1`
- `ops/pipeline/engine/shared/native.ps1`
- `ops/pipeline/engine/process/pipeline_plan_executor.ps1`
- `ops/pipeline/engine/queue/worker_mutex.ps1`
- `ops/pipeline/engine/shared/media_constants.ps1`
- `ops/pipeline/engine/shared/path_helpers.ps1`
- `ops/pipeline/engine/shared/versioning.ps1`
- `ops/scripts/dev/verify-env.ps1`

Key static search outputs summarized:

- Python definition-only candidates:
  - `_line_references_target`
  - `collect_inbound_references`
  - `make_auth_header`
  - `QueuePriorityItemPayload`
  - `NetworkLifecycleCommandPayload`
  - `list_high_paths`
  - `list_hold_paths`
- WebView definition-only candidates:
  - `_clearPanelHolding`
  - `showCompletedOutputTab`
  - `networkSourceKeysFromRow`
  - `pendingRecoveryFallbackRows`
  - `queueTableElement`
  - `queuePriorityBadgeLabel`
  - `settingsPatchHasCandidatePercentKeys`
- PowerShell definition-only candidates:
  - `Resolve-MediaPipelineLibraryEffectiveSettingsForPath`
  - `Resolve-DynamicHdrPolicy`
  - `Invoke-PipelinePlanExecutorDryRun`
  - `Invoke-MediaPipelineFinalStateWrite`
  - `Get-MediaSubtitleCodecWebVttName`
  - `Get-CompletedTaskTextWithBoundedDrain`
  - `Test-MediaPipelinePathHasReparsePoint`
  - `Get-MediaPipelineVersionInfo`
  - `Publish-Tx3gSrtSidecars`
  - `Test-IsBundledPythonPath`

Limitations:

- This was a static audit, not a runtime trace.
- No Local API server, Tauri shell, browser automation, queue worker, FFmpeg, subtitle conversion, publish/drain, or real-media workflow was run.
- Dynamic PowerShell dot-sourcing, JavaScript globals, route dispatch tables, and external/operator scripts can make static "unused" evidence incomplete.
- The worktree had many pre-existing modified/untracked files and in-progress audit packets before this report was written; unrelated dirty files were not inspected or absorbed.
- Generated summaries and `docs/generated/PROJECT_INDEX.md` may reflect other in-progress local work.
