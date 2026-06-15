# Worker Review: worker-08-webview-pages

## Scope

Worker ID: `worker-08-webview-pages`

Assigned scope: WebView page modules and page partials for Queue, Launch, Completed, Pending Publish, Rename, Settings, Diagnostics, Network, Telemetry, Schedule, Reports, Maintenance, and page-specific JS/CSS/partials.

Focus areas reviewed:

- Page-level ownership boundaries and backend-owned mutation handoff.
- Unsafe or under-confirmed `POST` exposure from page modules.
- Misleading evidence/readiness UI and stale backend assumptions.
- Selected-row, checked-row, filtered-row, and all-row scope behavior.
- Settings staging/save drift across builder controls and raw patch JSON.
- Browser/static smoke coverage gaps for the reviewed risks.

Repository safety boundaries from `AGENTS.md` were applied: no code was fixed, no source or media/runtime state was mutated, no commits were made, and this worker wrote only this report plus its change packet.

## Coverage Ledger

Coverage status: partial exhaustive coverage. All assigned files had summary-first review and static risk scans. Targeted source review covered the page modules and symbols most likely to own mutation, command scope, or readiness evidence. A full line-by-line audit of all 119 assigned files was not completed in this worker pass.

Required first reads completed:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`

Summary-first rule:

- Checked generated summaries for all 119 W08-assigned files before opening source.
- All assigned files had summary files.
- The WebView summaries were mostly `Purpose: (unparsed)`, so source was opened for high-risk paths and matched symbols.

Static scans completed across assigned files:

- `apiPost`, `apiGet`, direct `fetch`, command routes, mutation verbs, and confirmation gates.
- `window.confirm` usage and cancel paths on mutation-capable controls.
- Selected-row, checked-row, filtered-row, all-loaded, and all-applicable scope text.
- Settings patch/save builders, dirty state, invalid builder handling, and backend save routes.
- Browser/static test references for the identified risks.

Targeted source opened for detailed review:

- Queue: `queueView.js`, `queue/table.js`, `queue/selection.js`, `queue/openActions.js`, `queue/fileOverrides.routePreview.js`, `page-queue.html`.
- Launch: `launchView.js`, `launch/commandButtons.js`, `launch/startRequest.js`, `launch/scopeControls.js`, `launch/risk/riskRows.js`, `page-launch.html`.
- Completed: `completed/promotionCommands.js`, `completed/openActions.js`, completed evidence/review helpers, `page-completed.html`.
- Pending Publish: `pendingPublishView.js`, `pendingPublishView.drain.js`, `pendingPublishView.confidence.js`, `pendingPublishView.recovery.js`, `pendingPublishView.diagnostics.js`, `page-pending.html`.
- Rename: `renameView.js`, `rename/preview.js`, `rename/applyReadiness.js`, `rename/applyResult.js`, `styles.rename.css`, `page-rename.html`.
- Settings: `settingsView.js`, `settings/patchReview.js`, all `settingsView.builders.*.js`, `settingsLibraries.js`, `settingsWizard.js`, `settingsMetadata.js`, `page-settings.html`, `page-network.html`.
- Diagnostics, Reports, Schedule, Maintenance, Network, Telemetry: main page modules and partials, with command-route and readiness-focused inspection.

## Findings Summary

| ID | Severity | Area | Title |
|---|---|---|---|
| W08-001 | High | Rename | Batch safety text says no checked rows apply only the selected detail row, but Apply submits all applicable preview rows. |
| W08-002 | High | Settings | Invalid dirty Settings builder input does not abort Preview/Save, so stale raw JSON can still be submitted. |
| W08-003 | Medium | Queue | Priority manifest Clear All posts immediately without confirmation. |
| W08-004 | Medium | Launch | Audit/Rerun start buttons gate readiness through the Pipeline form request instead of their own requests. |

Severity counts: High 2, Medium 2, Low 0.

## Detailed Findings

### W08-001 - Rename batch safety text contradicts actual Apply scope

Severity: High

Files:

- `apps/desktop/webview/static/assets/rename/preview.js`
- `apps/desktop/webview/static/assets/renameView.js`
- `apps/desktop/webview/static/assets/rename/applyReadiness.js`
- `apps/desktop/webview/static/partials/page-rename.html`

Symbol/section: `renameBatchSafetyLines`, `getRenameApplyScopeRows`, `applyRenameWorkbench`, Rename Apply panel.

Evidence:

- `rename/preview.js:166` renders active batch safety text saying checked rows are submitted, but if none are checked, Apply uses only the selected detail row.
- `renameView.js:529` defines `getRenameApplyScopeRows()`.
- `renameView.js:534` returns source text `all applicable preview rows` when no rows are checked.
- `renameView.js:1732` uses `getRenameApplyScopeRows().rows` for `renameApplicablePreviewRows()`.
- `renameView.js:1735` defines `applyRenameWorkbench()`.
- `renameView.js:1770` sets `request.selected_sources` from all rows returned by the apply scope.
- `renameView.js:1771` sets `request.confirm_apply = true`.
- `renameView.js:1841`-`1842` wires `#rename-apply-button` to `applyRenameWorkbench()`.
- `rename/applyReadiness.js:155` correctly describes the submitted scope as backend `selected_sources`.
- Existing browser/static smoke asserts the correct readiness text in `tests/webview/test_webview_browser_rename_smoke.py:342` and `tests/webview/test_webview_rename_readiness_smoke.py:221`, but the stale batch-safety copy in `rename/preview.js:166` remains untested.

Impact:

An operator can select one detail row, see the Batch Safety panel say that no checked rows means only the selected detail row will be applied, then click Apply and submit every applicable preview row. The confirmation dialog shows the row count, but this is a filesystem rename surface and the page-level safety evidence is materially wrong.

Fix direction:

Make the Batch Safety copy match `getRenameApplyScopeRows()`: checked rows narrow the scope; if no rows are checked, Apply submits all applicable safe preview rows. Alternatively, change the implementation to selected-detail-row scope, but the UI, readiness panel, button label, and backend payload must agree.

Validation:

- Add a static assertion for `renameBatchSafetyLines()` so it cannot claim selected-detail-only scope when code uses all applicable rows.
- Extend the Rename browser smoke to assert the Batch Safety panel, the Apply Readiness panel, the button label, and the `selected_sources` payload agree for both unchecked/all-applicable and checked-row scopes.

### W08-002 - Invalid dirty Settings builder input does not abort Preview/Save

Severity: High

Files:

- `apps/desktop/webview/static/assets/settingsView.js`
- `apps/desktop/webview/static/assets/settings/patchReview.js`
- `apps/desktop/webview/static/assets/settingsView.builders.audio.js`
- `apps/desktop/webview/static/assets/settingsView.builders.file_safety.js`
- `apps/desktop/webview/static/assets/settingsView.builders.network.js`
- `apps/desktop/webview/static/assets/settingsView.builders.pending.js`
- `apps/desktop/webview/static/assets/settingsView.builders.queue.js`
- `apps/desktop/webview/static/assets/settingsView.builders.runtime.js`
- `apps/desktop/webview/static/assets/settingsView.builders.subtitle.js`
- `apps/desktop/webview/static/assets/settingsView.builders.video.js`

Symbol/section: `flushDirtySettingsBuilders`, `previewSettingsPatch`, `saveSettingsPatch`, builder apply functions.

Evidence:

- `settingsView.js:1243` defines `flushDirtySettingsBuilders()`.
- `settingsView.js:1248`-`1256` attempts to merge each dirty builder before preview/save.
- `settingsView.js:1260`-`1265` calls each apply function in a `try` block and increments `flushed`; caught errors are swallowed.
- `settingsView.js:1300`-`1302` calls `flushDirtySettingsBuilders()` before Preview and then reads `settings-patch-json`.
- `settingsView.js:1346` posts `/api/settings/preview-patch`.
- `settingsView.js:1416`-`1418` calls `flushDirtySettingsBuilders()` before Save and then reads `settings-patch-json`.
- `settingsView.js:1540` posts `/api/settings/save-patch` with `confirm_save: true`.
- `settingsView.builders.network.js:102` defines `applyNetworkSettingsBuilderToPatch()`.
- `settingsView.builders.network.js:106`-`111` catches invalid builder input, sets `settings-patch-status` to `Builder invalid`, and returns without throwing.
- The same `Builder invalid` then `return` pattern is present in `settings/patchReview.js:1273`, `settingsView.builders.audio.js:95`, `settingsView.builders.file_safety.js:94`, `settingsView.builders.pending.js:92`, `settingsView.builders.queue.js:76`, `settingsView.builders.runtime.js:88`, `settingsView.builders.subtitle.js:113`, and `settingsView.builders.video.js:249`.
- `settings/patchReview.js:1491`-`1492` binds the Preview and Save buttons to the `settingsView.js` event handlers.

Impact:

If a dirty builder contains invalid local input, the builder reports `Builder invalid` but Preview/Save continues using whatever raw JSON was already in `settings-patch-json`. That can produce a false `No changes` result over invalid visible edits, or worse, submit a stale/unrelated staged patch while the operator believes the current builder edits are being validated. The affected builders include file-safety paths, network worker path maps, queue/runtime/pending behavior, and subtitle/audio/video policy surfaces.

Fix direction:

Make builder apply failures fail closed. A minimal fix is to have every builder apply function return a structured success/failure result or throw on invalid input, and have `flushDirtySettingsBuilders()` return `{ ok: false, failedBuilders: [...] }` when any dirty builder fails. `previewSettingsPatch()` and `saveSettingsPatch()` should abort before reading or posting raw JSON when dirty builder flush fails.

Validation:

- Add a WebView/static test that sets invalid `settings-network-path-map`, marks the Network builder dirty, clicks Preview, and asserts no `/api/settings/preview-patch` is posted.
- Add a Save variant asserting no `/api/settings/save-patch` is posted when any dirty builder fails.
- Cover at least one numeric builder and one JSON/text builder, then add static coverage that all builder invalid paths propagate failure instead of returning silently.

### W08-003 - Queue priority Clear All posts immediately without confirmation

Severity: Medium

Files:

- `apps/desktop/webview/static/assets/queueView.js`
- `apps/desktop/webview/static/partials/page-queue.html`

Symbol/section: `clearQueuePriorityManifest`, Priority toolbar.

Evidence:

- `page-queue.html:73` renders `#queue-priority-clear-all-btn` with title `Reset all manifest entries to Normal (clear entire manifest)`.
- `queueView.js:1563`-`1567` contains a `window.confirm` helper for loaded Movie/TV bulk promotion, not for Clear All.
- `queueView.js:1591` defines `clearQueuePriorityManifest()`.
- `queueView.js:1594` immediately posts `apiPost("/api/queue/priority", { clear_all: true })`.
- `queueView.js:1947` wires `#queue-priority-clear-all-btn` directly to `clearQueuePriorityManifest`.
- Existing tests assert the route and refresh behavior in `tests/python/desktop/test_application_facade_web_static.py:1778`-`1800`, but do not require a confirmation or cancel/no-post path.

Impact:

A single click can clear the entire queue priority manifest. That does not directly mutate media files, but it can remove Hold entries and priority overrides that influence future Launch behavior. Queue mutation is backend-owned and should have a higher-friction operator boundary for all-manifest changes.

Fix direction:

Add an explicit confirmation before posting `clear_all: true`. The confirmation should include the loaded priority/hold count if available and state that future Launch ordering/eligibility can change. Consider requiring a backend `confirm_clear_all: true` command payload as well.

Validation:

- Add a browser/static smoke where canceling Clear All posts nothing.
- Add a confirmation-accepted smoke that posts exactly one `/api/queue/priority` request with `clear_all: true`.
- Extend static tests to require the confirmation text and cancel behavior.

### W08-004 - Audit/Rerun start buttons gate readiness through Pipeline request state

Severity: Medium

Files:

- `apps/desktop/webview/static/assets/launch/commandButtons.js`

Symbol/section: `launchButtonGate`, Audit and CSV Rerun button readiness.

Evidence:

- `launch/commandButtons.js:87` defines `launchButtonGate(id)`.
- `launch/commandButtons.js:110`-`116` builds the Audit request with `collectAuditStartRequest()` and uses it for `launchTargetGate("audit", request, ...)`.
- `launch/commandButtons.js:117` then calls `launchStartDecisionGate(collectPipelineStartRequest())`.
- `launch/commandButtons.js:120`-`126` builds the CSV Rerun request with `collectRerunStartRequest()` and uses it for `launchTargetGate("rerun", request, ...)`.
- `launch/commandButtons.js:127` then calls `launchStartDecisionGate(collectPipelineStartRequest())`.
- `launch/risk/riskRows.js:27` and `launch/risk/riskRows.js:45` normalize backend risk rows using the supplied request mode/context, so passing Pipeline request state can change the decision rows and operator guidance.
- Existing static coverage only asserts the function and gate names exist in `tests/python/desktop/test_application_facade_web_static.py:1086`-`1088`. Browser readiness smoke covers generic blocked backend preflight text, not isolation from Pipeline form state.

Impact:

Audit and CSV Rerun button disabled state and disabled reasons can be derived from unrelated Pipeline Processor form values. This can block or explain Audit/Rerun controls with stale Pipeline-mode evidence even after their own backend preflight payloads match. The backend start routes still re-check submitted commands, so this is a misleading readiness/control risk rather than direct mutation.

Fix direction:

Give Audit and Rerun their own start-decision request context, or make `launchStartDecisionGate` explicitly target-neutral for non-pipeline commands. The target gate already receives the right request; the decision gate should not call `collectPipelineStartRequest()` for Audit/Rerun.

Validation:

- Add a focused test where Pipeline form state is blocked or stale while Audit/Rerun preflight payloads are ready, and assert Audit/Rerun controls do not inherit Pipeline-only disabled reasons.
- Extend browser readiness smoke to inspect button disabled reasons for Audit and Rerun independently from Pipeline Processor form changes.

## Test Coverage Gaps

- Rename tests already cover Apply Readiness text and `selected_sources` behavior, but do not cover the Batch Safety text rendered by `renameBatchSafetyLines()`.
- Settings browser smoke covers valid Preview/Save and Save cancellation, but no test found for invalid dirty builder input preventing Preview/Save posts.
- Queue priority Clear All has backend/static route coverage, but no test found for confirmation, cancellation, or no-post behavior.
- Launch button readiness tests assert gate existence and some backend-preflight blocked text, but no test found proving Audit/Rerun gates are isolated from Pipeline Processor form state.
- No runtime/browser smoke was executed during this review-only worker pass.

## Boundary Risks

- Rename is a filesystem mutation surface. The backend apply route is still used, but W08-001 shows page-level safety copy can misstate the mutation scope before submission.
- Settings Save writes active PSD1 configuration through the backend. W08-002 shows dirty builder validation can be bypassed by stale raw JSON when the WebView continues after local builder failure.
- Queue priority overrides affect future backend Launch ordering and Hold eligibility. W08-003 shows the all-manifest reset lacks a page-level confirmation boundary.
- Launch Audit/Rerun controls post through backend routes and retain confirmation in `launchView.js`, but W08-004 shows readiness gating can be based on stale Pipeline form context.
- Completed final-library promotion, Pending Publish drain/recovery, Schedule save, Reports failure/audit commands, Diagnostics Tdarr matrix actions, Maintenance release build, Network controls, and Telemetry controls did not show direct browser filesystem mutation in the inspected WebView snippets. Mutation-capable actions observed there route through backend APIs with confirmation or dry-run/evidence wording where expected.

## Files Reviewed With No Findings

No findings were recorded for the following assigned files after summary-first review, static command/scope scan, and targeted source inspection where relevant:

- `apps/desktop/webview/static/assets/commandHistory/diagnostics.js`
- `apps/desktop/webview/static/assets/completed/evidence/acceptance.js`
- `apps/desktop/webview/static/assets/completed/evidence/commands.js`
- `apps/desktop/webview/static/assets/completed/evidence/filterScope.js`
- `apps/desktop/webview/static/assets/completed/evidence/routeAgreement.js`
- `apps/desktop/webview/static/assets/completed/filters.js`
- `apps/desktop/webview/static/assets/completed/openActions.js`
- `apps/desktop/webview/static/assets/completed/promotionCommands.js`
- `apps/desktop/webview/static/assets/completed/review/healthSignals.js`
- `apps/desktop/webview/static/assets/completed/review/integrity.js`
- `apps/desktop/webview/static/assets/completed/review/investigationFilters.js`
- `apps/desktop/webview/static/assets/completed/review/reviewRows.js`
- `apps/desktop/webview/static/assets/completed/review/sizeReview.js`
- `apps/desktop/webview/static/assets/completed/selection.js`
- `apps/desktop/webview/static/assets/completed/statusBoards.js`
- `apps/desktop/webview/static/assets/completed/table.js`
- `apps/desktop/webview/static/assets/completedView.diagnostics.js`
- `apps/desktop/webview/static/assets/completedView.evidence.js`
- `apps/desktop/webview/static/assets/completedView.js`
- `apps/desktop/webview/static/assets/completedView.proof.js`
- `apps/desktop/webview/static/assets/completedView.review.js`
- `apps/desktop/webview/static/assets/contractView.js`
- `apps/desktop/webview/static/assets/crossPageContextView.conflict.js`
- `apps/desktop/webview/static/assets/crossPageContextView.js`
- `apps/desktop/webview/static/assets/crossPageContextView.sample.js`
- `apps/desktop/webview/static/assets/crossPageContextView.sampleValidation.js`
- `apps/desktop/webview/static/assets/crossPageContextView.sampleValidation.records.js`
- `apps/desktop/webview/static/assets/crossPageContextView.sampleValidation.runbook.js`
- `apps/desktop/webview/static/assets/crossPageContextView.sampleValidation.worksheet.js`
- `apps/desktop/webview/static/assets/crossPageContextView.settings.js`
- `apps/desktop/webview/static/assets/diagnosticsBridge.js`
- `apps/desktop/webview/static/assets/diagnosticsStateSummaryView.js`
- `apps/desktop/webview/static/assets/diagnosticsTailView.js`
- `apps/desktop/webview/static/assets/diagnosticsView.activejobs.js`
- `apps/desktop/webview/static/assets/diagnosticsView.investigation.js`
- `apps/desktop/webview/static/assets/diagnosticsView.js`
- `apps/desktop/webview/static/assets/diagnosticsView.log.js`
- `apps/desktop/webview/static/assets/launch/controllerState.js`
- `apps/desktop/webview/static/assets/launch/risk/mediaPolicyValues.js`
- `apps/desktop/webview/static/assets/launch/risk/policyBoundary.js`
- `apps/desktop/webview/static/assets/launch/risk/policyPatch.js`
- `apps/desktop/webview/static/assets/launch/risk/riskRows.js`
- `apps/desktop/webview/static/assets/launch/risk/settingsAccess.js`
- `apps/desktop/webview/static/assets/launch/scopeControls.js`
- `apps/desktop/webview/static/assets/launch/startRequest.js`
- `apps/desktop/webview/static/assets/launch/statusRender.js`
- `apps/desktop/webview/static/assets/launchHistoryView.js`
- `apps/desktop/webview/static/assets/launchReadinessView.js`
- `apps/desktop/webview/static/assets/launchView.js`
- `apps/desktop/webview/static/assets/launchView.preflight.js`
- `apps/desktop/webview/static/assets/launchView.realmedia.js`
- `apps/desktop/webview/static/assets/launchView.risk.js`
- `apps/desktop/webview/static/assets/launchView.scope.js`
- `apps/desktop/webview/static/assets/maintenanceView.js`
- `apps/desktop/webview/static/assets/networkView.js`
- `apps/desktop/webview/static/assets/pendingPublish/details.js`
- `apps/desktop/webview/static/assets/pendingPublish/filters.js`
- `apps/desktop/webview/static/assets/pendingPublish/summary.js`
- `apps/desktop/webview/static/assets/pendingPublishView.confidence.js`
- `apps/desktop/webview/static/assets/pendingPublishView.diagnostics.js`
- `apps/desktop/webview/static/assets/pendingPublishView.drain.js`
- `apps/desktop/webview/static/assets/pendingPublishView.js`
- `apps/desktop/webview/static/assets/pendingPublishView.recovery.js`
- `apps/desktop/webview/static/assets/queue/fileOverrides.drawer.js`
- `apps/desktop/webview/static/assets/queue/fileOverrides.routePreview.js`
- `apps/desktop/webview/static/assets/queue/openActions.js`
- `apps/desktop/webview/static/assets/queue/selection.js`
- `apps/desktop/webview/static/assets/queue/table.js`
- `apps/desktop/webview/static/assets/queueView.detail.js`
- `apps/desktop/webview/static/assets/queueView.launch.js`
- `apps/desktop/webview/static/assets/queueView.review.js`
- `apps/desktop/webview/static/assets/queueView.summary.js`
- `apps/desktop/webview/static/assets/rename/applyReadiness.js`
- `apps/desktop/webview/static/assets/rename/applyResult.js`
- `apps/desktop/webview/static/assets/renameHistoryView.js`
- `apps/desktop/webview/static/assets/renameLabels.js`
- `apps/desktop/webview/static/assets/reportsView.js`
- `apps/desktop/webview/static/assets/scheduleView.js`
- `apps/desktop/webview/static/assets/settings/backendResult.js`
- `apps/desktop/webview/static/assets/settings/builderControls.js`
- `apps/desktop/webview/static/assets/settings/metadataFields.js`
- `apps/desktop/webview/static/assets/settings/policyImpact.js`
- `apps/desktop/webview/static/assets/settingsCommandHistory.js`
- `apps/desktop/webview/static/assets/settingsLibraries.js`
- `apps/desktop/webview/static/assets/settingsMetadata.js`
- `apps/desktop/webview/static/assets/settingsOverview.js`
- `apps/desktop/webview/static/assets/settingsView.rawTriage.js`
- `apps/desktop/webview/static/assets/settingsView.safetyLocks.js`
- `apps/desktop/webview/static/assets/settingsWizard.js`
- `apps/desktop/webview/static/assets/styles.rename.css`
- `apps/desktop/webview/static/assets/telemetryView.js`
- `apps/desktop/webview/static/partials/page-completed.html`
- `apps/desktop/webview/static/partials/page-diagnostics.html`
- `apps/desktop/webview/static/partials/page-home.html`
- `apps/desktop/webview/static/partials/page-launch.html`
- `apps/desktop/webview/static/partials/page-libraries.html`
- `apps/desktop/webview/static/partials/page-maintenance.html`
- `apps/desktop/webview/static/partials/page-network.html`
- `apps/desktop/webview/static/partials/page-pending.html`
- `apps/desktop/webview/static/partials/page-reports.html`
- `apps/desktop/webview/static/partials/page-schedule.html`
- `apps/desktop/webview/static/partials/page-settings.html`
- `apps/desktop/webview/static/partials/page-telemetry.html`

Files not listed here are covered by findings or finding context.

## Files Marked Out Of Scope

No assigned W08 files were marked out of scope.

Out-of-scope items encountered but not reviewed as source of truth:

- Backend route implementations and contracts for `/api/rename/apply`, `/api/settings/save-patch`, `/api/queue/priority`, `/api/pipeline/start`, Diagnostics Tdarr matrix routes, and Completed promotion routes.
- Test files cited for coverage evidence.
- Aggregate review files such as `FINDINGS_REGISTER.md`, `COVERAGE_MATRIX.md`, and `FINAL_SYNTHESIS.md`.
- Generated `docs/reviews/function-module-audit-2026-06-11/symbol_inventory.json`.

## Incomplete Coverage

Skipped assigned files: none.

Incomplete coverage:

- Full line-by-line review of all 119 assigned files was not completed.
- Low/medium files without command routes or matched risk patterns received summary-first review plus static scan, not full source traversal.
- No browser smoke, local API smoke, or runtime tests were executed. This was a review-only worker pass.
- Backend validation of the cited APIs was outside W08 scope.
