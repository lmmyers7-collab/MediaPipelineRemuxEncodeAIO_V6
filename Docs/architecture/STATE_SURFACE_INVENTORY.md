# State Surface Inventory

> **Purpose:** Catalogue every **module-scope mutable global** in the codebase, grouped by lifecycle. Eliminates the "where is X set / where is X read / when is X cleared?" friction.
> **Scope:** Globals at module scope only — i.e., `$script:*` in PowerShell modules, `let xxx = …` at IIFE top-level in JS modules, module-level `_CACHE = …` in Python. Local function variables and instance attributes are out of scope.
> **Audience:** Anyone debugging "I changed X and Y broke" or adding new state.

---

## 1. Why this exists

The biggest source of "I touched A and B broke" bugs is unscoped module-level state. Each module scope-global is a *contract* between writer and readers — but PowerShell `$script:*` and JS IIFE `let` give you no language-level visibility into that contract.

This document is the **curated** inventory. It is not auto-generated (per `CODE_MANAGEMENT_CLEANUP_PLAN.md` §5.4 — generation is for *checks*, not docs). Each category below explains the lifecycle pattern and lists examples; a drift test (TBD, per §6) will assert that any **new** module-scope global appears here.

---

## 2. PowerShell — `$script:*` categories

PS1 modules are dot-sourced into the same script scope, so `$script:Foo` written in one module is readable in every other module. This is intentional but creates lots of cross-cutting state. There are four canonical lifecycle patterns.

### 2.1 Config-derived constants (set once at startup, read everywhere)

**Lifecycle:** Set during the config-loading section of `MediaPipeline_chatgpt.ps1` (and the script entrypoints in `Pipeline/*.ps1` like `Invoke-RerunCsv.ps1`, `Get-NamingPreview.ps1`). Read by helpers throughout the pipeline. **Never reassigned at runtime.**

**Representative names** (not exhaustive — every config key has a `$script:*` mirror):

- `$script:LocalBase`, `$script:LocalStateLayout` — state-root paths
- `$script:SourceMovies`, `$script:SourceTV` — source roots
- `$script:PriorityMarkers`, `$script:AggressiveEpisodeParsing`, `$script:ValidExtensions`
- `$script:AudioPassthroughProfile`, `$script:AudioTranscodeCodec`, `$script:AudioTranscodeBitrate`, `$script:AudioDownmixMode`, `$script:AudioMaxChannels`, `$script:AllowNoAudio`
- `$script:PreferredDefaultAudioLanguages`
- `$script:CompatibleAudioCodecs`, `$script:CompatibleVideoCodecs`, `$script:CompatibleContainers`
- `$script:CpuEncodePreset`, `$script:CpuEncodeProcessPriority`
- `$script:QueueOrderingStrategy`, `$script:MixPriorityPhase`
- `$script:TransientFailureRetryLimit`, `$script:RetryBackoffSeconds`
- `$script:ffmpegPath`, `$script:ffprobePath`, `$script:mkvmergePath` — tool paths
- `$script:RerunRobocopyFlags`, `$script:RerunRobocopyTimeoutSeconds`, `$script:RerunNestedPipelineTimeoutSeconds` (Rerun script only)

**Rule:** If you read a config key from `MediaPipelineConfig.psd1`, you also `Set-Variable -Scope Script` for it — either via `Get-ConfigBool` / `Get-ConfigInt` / `Get-ConfigChoice` helpers, or directly. Code consumers always read the `$script:*` variable, never `$config['…']` directly past the loading section.

**Danger level:** Low. These are constants by convention. The risk is a typo'd config key silently returning `$null`; the workstream `CODE_MANAGEMENT_CLEANUP_PLAN.md §3.1` (config-key constants) closes this gap.

### 2.2 Per-pipeline-round caches (invalidated between rounds or per-file)

**Lifecycle:** Set lazily on first read in a round; explicitly invalidated when the underlying state file may have changed.

**Representative names:**

- `$script:CachedFileOverridesManifest` — invalidated by `Merge-FileOverrideIntoActiveOverrides` per file so runtime edits to `file_overrides.json` are picked up.

**Rule:** Anything cached must have an obvious invalidation point. Document it in the module header.

**Danger level:** Medium. A missing invalidation gives stale data without crashing.

### 2.3 Per-file processing state (set/cleared in try/finally)

**Lifecycle:** Set at the start of `Invoke-MediaPipelineProcessFile` (in `engine/process/pipeline_processing.ps1`), read by helpers throughout the file's processing, **always cleared in the `finally` block** before the function returns.

**Representative names:**

- `$script:ActiveOverrides` — merged show/folder/file overrides hashtable
- `$script:CurrentJobId`
- `$script:CurrentRoutePlan`
- `$script:CurrentRouteReasonCode`, `$script:CurrentRouteReason`
- `$script:CurrentEncodeAttempts`
- `$script:CurrentSizePolicyResult`

**Rule:** Any new state that's only valid during a single file's processing belongs here. Add to the `finally { … = $null }` block in `engine/process/pipeline_processing.ps1` in the same chunk that introduces it.

**Danger level:** **HIGH.** A leaked `$script:Current*` from one file processing into the next is the worst class of bug — it manifests as "the second file gets the first file's policy." Always pair set with finally-clear in the same commit.

### 2.4 Last-output handoff (set inside helpers, read by orchestrator)

**Lifecycle:** A helper function (e.g., `Build-AudioArgs`) computes a value as a side-effect of its primary job, stashes it on `$script:LastXxx`, and the orchestrator (`Do-Remux`, `Do-Encode`) reads it after the helper returns.

**Representative names:**

- `$script:LastAudioDefaultIndex`, `$script:LastAudioTrackCount`, `$script:LastAudioTranscodeActive`
- `$script:LastAudioDecisionRecords`
- `$script:LastSubtitleDecisionRecords`

**Rule:** Used when a function needs to return *multiple* outputs and PowerShell's "every line is a return value" semantics get in the way. The cleaner alternative (return a hashtable) is preferred for new code; existing `$script:Last*` writes stay for compatibility.

**Danger level:** Medium. The order of "read after helper returns" must hold; if a second helper call overwrites the stash before the orchestrator reads, the orchestrator sees wrong data.

---

## 3. JavaScript — IIFE module-scope state

Every WebView JS module is an IIFE (`(function () { … })();`) with `let` declarations at the top of the closure. Those `let`s are module-scope mutable globals from the module's internal perspective; they are *not* exposed on `window`. There are three universal patterns.

### 3.1 Cached last-loaded payload (`lastXxx*`)

**Lifecycle:** Set inside the module's top-level `renderXxx(payload, rows)` function each time the renderer runs. Read by selection helpers, detail-pane renderers, and cross-page handoffs.

**Representative names** (every page-view module has 2–6 of these):

- `queueView.js` — `lastQueueRows`, `lastQueueExcludedRows`, `lastQueueHiddenSidecarRows`, `lastQueuePayload`, `lastQueueEmptyMessage`
- `completedView.js` — `lastCompletedRows`, `lastCompletedPayload`, `lastCompletedPendingPayload`, `lastCompletedPendingProofRows`, `lastPublishReconciliationPayload`, `lastCompletedRouteAgreementRows`, `lastCompletedEmptyMessage`
- `pendingPublishView.js` — `lastPendingRows`, `lastPendingPayload`, `lastPendingSnapshot`, `lastPendingRecoveryPlanRows`, `lastPendingEmptyMessage`
- `launchView.js` — `lastLaunchRealMediaProofContext`, `lastLaunchBackendPreflightPayloads`, `lastLaunchBackendPreflightRefreshInfo`
- `settingsView.js` — `lastSettings`
- `crossPageContextView.js` — `lastCrossPageContext`
- `diagnosticsView.js` — `lastActiveJobRows`, `lastDiagnosticsLogRows`, `lastDiagnosticsOwnerHandoffRows`
- `diagnosticsStateSummaryView.js` — `lastDiagnosticsStateSummaryRows`, `lastDiagnosticsStateTriageRows`
- `maintenanceView.js` — `lastMaintenance`
- `networkView.js` — `lastNetworkWorkerRows`
- `launchReadinessView.js` — `lastLaunchReadinessPayload`
- `contractView.js` — `lastContractRoutes`, `lastContractPayload`

**Rule:** Always set inside the top-level renderer. Always treat as read-only outside the renderer. If a helper needs to mutate the row list, return a new list — don't mutate `last*`.

**Danger level:** Low — these are caches with a known refresher.

### 3.2 Selected row keys (`selectedXxxKey` / `selectedXxxRow`)

**Lifecycle:** Set by `selectXxx(item)` event handlers. Read by row renderers (to mark a row as selected) and detail-pane renderers (to render the selected row's detail).

**Representative names:**

- `queueView.js` — `selectedQueueRowKey`, `selectedQueueExcludedRowKey`, `selectedQueueLaunchDecisionKey`
- `completedView.js` — `selectedCompletedRowKey`, `selectedCompletedPendingProofKey`, `selectedCompletedSizeEvidenceKey`, `selectedCompletedAcceptanceKey`, `selectedCompletedRealMediaProofKey`, `selectedCompletedFinalTrustKey`, `selectedCompletedPilotEvidenceKey`, `selectedCompletedRouteAgreementKey`, `selectedPublishReconciliationKey`
- `pendingPublishView.js` — `selectedPendingRowKey`, `selectedPendingRecoveryPlanKey`, `selectedPendingDrainDecisionKey` (managed by `pendingPublishView.confidence.js` via parent state adapter), `selectedPendingPostDrainTrustKey` (managed by `pendingPublishView.confidence.js` via parent state adapter)
- `launchView.js` — eight `selectedLaunch*Key` variables for the eight launch-side selectable panels
- `crossPageContextView.js` — five `selectedSampleValidation*Key` variables
- `diagnosticsView.js`, `diagnosticsStateSummaryView.js`, `contractView.js`, `networkView.js`, `maintenanceView.js` — one or more selection keys each.
- `commandHistory.js` — `selectedCommandKey`, `selectedCommandResolutionKey`
- `launchHistoryView.js` — `selectedLaunchCommandReviewKey`

**Rule:** Selection state is per-module. Cross-page selection handoff uses `crossPageContextView.js`, not direct reads of another module's `selected*Key`.

**Danger level:** Low — losing selection state on a stale render is annoying but not a correctness bug.

### 3.3 Busy / in-flight flags (`xxxInFlight`)

**Lifecycle:** Set to `true` at the start of an async command dispatch; set to `false` in the success/error paths. Read by every callable button's "should I let this through?" guard.

**Representative names:**

- `queueView.js` — `queueOpenInFlight`
- `completedView.js` — `completedOpenInFlight`, `publishReconciliationInFlight`
- `pendingPublishView.js` — `pendingOpenInFlight` (managed by `pendingPublishView.diagnostics.js` via parent state adapter), `pendingRecoveryPlanInFlight` (managed by `pendingPublishView.recovery.js` via parent state adapter)
- `launchView.js` — `launchCommandInFlight`, `controlCommandInFlight`
- `diagnosticsView.js` — `diagnosticsOpenInFlight`
- `diagnosticsTailView.js` — `diagnosticsTailInFlight`
- `maintenanceView.js` — `maintenanceRefreshInFlight`, `maintenanceDryRunInFlight`
- `crossPageContextView.js` — `sampleValidationInFlight`

**Rule:** Every mutation/command dispatcher has an `…InFlight` flag with a `rejectXxxWhileBusy()` guard. The flag is cleared in both success and error paths. If you add a new POST route's frontend dispatcher, add a matching `…InFlight` flag in the same chunk.

**Danger level:** **HIGH** if the clear-on-error path is forgotten — the operator can never retry the action because the flag stays `true`.

### 3.4 Module constants (frozen sets / arrays at IIFE top)

**Lifecycle:** Declared once at module load (e.g., `const QUEUE_STRATEGIES = ["Standard", "FreshestFirst", …];`). Never reassigned.

**Representative names:**

- `queueView.js` — `QUEUE_HIDDEN_SIDECAR_EXTENSIONS`, `QUEUE_FILTER_FIELDS`, `QUEUE_PRIORITY_ROUTE`, `QUEUE_STRATEGY_ROUTE`, `QUEUE_FILE_OVERRIDES_ROUTE`, `QUEUE_STRATEGIES`
- Most modules — route constants of the form `XXX_ROUTE = "/api/xxx/yyy"`

**Rule:** If a string appears in three or more places, lift it to a `const` at the top of the file. Don't promote to a shared module-level constant unless three or more *modules* use it.

**Danger level:** Low — `const` is non-mutable.

### 3.5 Backend-injected bootstrap global (`window.MEDIA_PIPELINE_BOOTSTRAP`)

The only `window.*` global that isn't set by a JS module — the backend HTML template injects it before any module loads. `apiClient.js` reads it at module load. Documented in `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`.

**Rule:** Treat as immutable. Don't write to it from JS.

---

## 4. Python — module-level mutables

Most Python modules in this codebase use immutable module-level constants. Mutable module-level state exists but is rare — and that's by design.

### 4.1 Function-scope caches (preferred)

Most "cache" patterns in the Python services use either:
- a function-local `@lru_cache` decorator, or
- a private `_resolve_paths` function with a fresh `dict` per call

This is the preferred pattern. Adding new mutable module-level state in Python should be a deliberate choice with a justification in the module header.

### 4.2 Module-level mutables that do exist (notable cases)

- `service_telemetry.py` and friends maintain short-lived cached telemetry snapshots — these are caches with a known refresh cadence.
- `application/runtime_outcomes.py` exposes a curated mapping of outcome states; the dict is shared but is treated as immutable (no module mutates it at runtime).

**Rule:** New mutable module-level state in Python requires a module-header comment explaining the lifecycle and why a function-scope cache wouldn't work. The default answer is "use a function-scope cache."

---

## 5. Rust — `static` and `lazy_static`

The Tauri shell currently has minimal global state — `lib.rs` and its sub-modules pass `tauri::Manager` references explicitly.

If any module-level `static` or `lazy_static!` is added in future work, it must be listed here with the same lifecycle/owner/reader documentation as PS1 and JS state.

---

## 6. Drift detection (planned)

Per `CODE_MANAGEMENT_CLEANUP_PLAN.md` §3.3, a future chunk will add a drift test that:

1. Greps for `$script:\w+\s*=` in `Pipeline/**.ps1` and `let \w+\s*=` at IIFE top-level in `ui_web/static/assets/*.js`.
2. Asserts every match is either listed in this document (by category) or matches a known-allowed pattern (config-key mirrors named the same as the config key, etc.).

Until that test lands, this document is curated by hand and **must be updated in the same chunk that introduces a new module-scope global.**

---

## 7. Anti-patterns

These are the ways state-management causes bugs in this codebase.

1. **Forgetting to clear `$script:Current*` in the finally block.** Leaks state from one file's processing into the next. Easy to write the test for; hard to debug if missed.
2. **Setting an `InFlight` flag and not clearing it on error.** Leaves the operator unable to retry the command.
3. **Reading `last*` outside the renderer.** Tempting when "the renderer just ran"; brittle when the renderer hasn't run yet (first load, error state). Always pass the payload as a parameter; only the renderer reads `last*` to populate fallback arguments.
4. **Cross-module reading of another module's `selected*Key`.** Use `crossPageContextView.js` for cross-page handoff.
5. **Storing mutable state in `window.*` directly (outside a module's IIFE).** The IIFE closure is the boundary; bypassing it makes the state untraceable.
6. **Hashtable mutation through a "read" function.** If `Get-FileOverrideAudioSettings` returned the live override hashtable and a caller mutated it, the override would change for every subsequent reader. The current code returns the live ref but contract is read-only. If a getter could ever be misused this way, return a copy or a frozen view.

---

## 8. When you add new state

Checklist for adding a new `$script:Xxx`, `let lastXxx`, or `let selectedXxxKey`:

1. **Identify the category** (§2.1–§2.4 or §3.1–§3.5). Document it in the module header.
2. **Decide the lifecycle.** Set when? Read by whom? Cleared when?
3. **Add a row to this document** under the matching category.
4. **For `$script:Current*` — add the `$null` clear to `engine/process/pipeline_processing.ps1`'s `finally` block in the same chunk.**
5. **For `…InFlight` flags — add the clear-on-error path in the same chunk.**
6. **For `last*` — set it inside the top-level renderer only.**
7. **Update `DOC_TOUCH_LOG.md`** with this file in the touched-inventories column.

If you can't categorise the new state into an existing pattern, you might be introducing a new lifecycle. Propose it in a `Docs/proposals/*.md` first.
