# renameView.js Phase 0 Baseline

Change packet: `MP-CHANGE-2026-0626-010`

This is prework for a troubleshooting-oriented split of
`apps/desktop/webview/static/assets/renameView.js`. It documents the current
public contract and safety seams only. No runtime behavior, backend route,
rename policy, export name, or UI behavior is changed by this note.

## Current Contract

| Item | Current value |
|---|---|
| Source file | `apps/desktop/webview/static/assets/renameView.js` |
| Current size | 3,559 lines, 159,975 bytes |
| Public namespace | `window.mediaPipelineRenameView` |
| Namespace export count | 104 |
| Flat export count | 0 |
| Script tag | `/assets/renameView.js` |
| Existing pre-parent slice scripts | `/assets/rename/preview.js`, `/assets/rename/applyReadiness.js`, `/assets/rename/applyResult.js` |
| Required load rule | Any new child module must load before `/assets/renameView.js`; `renameView.js` remains the public facade |

Current script order in `apps/desktop/webview/static/index.html` is:

```text
/assets/renameLabels.js
/assets/renameHistoryView.js
/assets/rename/preview.js
/assets/rename/applyReadiness.js
/assets/rename/applyResult.js
/assets/renameView.js
```

Rollback rule for all seams: remove the new child script, restore the moved
implementation inside `renameView.js`, and keep every
`window.mediaPipelineRenameView` export name/signature callable during the
rollback. Do not move mutation policy into a child module; children may only
stage operator intent, render evidence, and call backend routes through the
parent facade contract.

## Export Ledger

Wrapper requirement for every row: keep the export on
`window.mediaPipelineRenameView`; do not add flat `window.*` exports. A future
child module may own implementation only if the parent continues to expose the
same facade entry.

Direct caller abbreviations:

- `app`: `apps/desktop/webview/static/assets/app.js`
- `settings`: `apps/desktop/webview/static/assets/settingsView.js`
- `node-smoke`: `tests/webview/test_webview_rename_readiness_smoke.py`
- `browser-smoke`: `tests/webview/test_webview_browser_rename_smoke.py`
- `settings-browser-smoke`: `tests/webview/test_webview_browser_settings_builder_flush_smoke.py`
- `static-rename`: `tests/python/desktop/test_application_facade_web_static_rename.py`

| Export | Current signature and source line | Known direct callers | Proposed owner |
|---|---|---|---|
| `collectRenameRequest` | `function collectRenameRequest()` at `renameView.js:74` | none found | `renameView.js` facade/state coordinator |
| `collectRenameMovieFilterTerms` | `function collectRenameMovieFilterTerms()` at `renameView.js:184` | none found | `assets/rename/cleaningFilters.js` |
| `collectRenameTvFilterTerms` | `function collectRenameTvFilterTerms()` at `renameView.js:201` | none found | `assets/rename/cleaningFilters.js` |
| `renameCleaningFilterConfigPatch` | `function renameCleaningFilterConfigPatch()` at `renameView.js:220` | `settings:1515`, `settings:1520`, `settings-browser-smoke:212`, `settings-browser-smoke:290` | `assets/rename/cleaningFilters.js` |
| `renderRenameCleaningFilterEditor` | `function renderRenameCleaningFilterEditor(message = "")` at `renameView.js:231` | none found | `assets/rename/cleaningFilters.js` |
| `saveRenameCleaningFilterDraft` | `function saveRenameCleaningFilterDraft(message = "Cleaning filter draft retained in this browser.")` at `renameView.js:259` | `settings:1508`, `settings:1509`, `static-rename:210` | `assets/rename/cleaningFilters.js` |
| `saveRenameCleaningFilterState` | `async function saveRenameCleaningFilterState(message = "Rename cleaning filters prepared for Save Settings.")` at `renameView.js:298` | none found | `assets/rename/cleaningFilters.js` |
| `resetRenameCleaningFilters` | `function resetRenameCleaningFilters()` at `renameView.js:326` | none found | `assets/rename/cleaningFilters.js` |
| `initRenameCleaningFilterEditorEvents` | `function initRenameCleaningFilterEditorEvents()` at `renameView.js:1015` | `app:1663`, `browser-smoke:216` | `assets/rename/cleaningFilters.js` |
| `refreshRenamePreview` | `async function refreshRenamePreview()` at `renameView.js:2665` | `app:1600`, `app:1602` | `renameView.js` facade/state coordinator |
| `renderRenamePreview` | `function renderRenamePreview(preview, requestSignature = "")` at `renameView.js:2467` | `browser-smoke:523`, `535`, `552`, `583`, `772`, `784`, `792`, `850`, `857` | `renameView.js` facade/state coordinator |
| `renderRenameRows` | `function renderRenameRows()` at `renameView.js:2492` | none found | `renameView.js` facade/state coordinator |
| `renderRenameSummary` | `function renderRenameSummary(preview)` at `rename/preview.js:143` | none found | existing `assets/rename/preview.js` slice |
| `renderRenameBatchSafety` | `function renderRenameBatchSafety(preview)` at `rename/preview.js:216` | none found | existing `assets/rename/preview.js` slice |
| `renameBatchSafetyLines` | `function renameBatchSafetyLines(preview)` at `rename/preview.js:172` | none found | existing `assets/rename/preview.js` slice |
| `renderRenamePipelineHandoff` | `function renderRenamePipelineHandoff(preview)` at `rename/preview.js:317` | none found | existing `assets/rename/preview.js` slice |
| `renamePipelineHandoffLines` | `function renamePipelineHandoffLines(preview)` at `rename/preview.js:258` | none found | existing `assets/rename/preview.js` slice |
| `renamePipelineHandoffStatus` | `function renamePipelineHandoffStatus(preview)` at `rename/preview.js:240` | none found | existing `assets/rename/preview.js` slice |
| `renameSavedSettingsConfig` | `function renameSavedSettingsConfig()` at `rename/preview.js:220` | none found | existing `assets/rename/preview.js` slice |
| `renderRenameReviewBoard` | `function renderRenameReviewBoard(preview)` at `rename/preview.js:136` | none found | existing `assets/rename/preview.js` slice |
| `renameReviewBoardLines` | `function renameReviewBoardLines(preview)` at `rename/preview.js:81` | none found | existing `assets/rename/preview.js` slice |
| `renameReviewBoardStatus` | `function renameReviewBoardStatus(preview)` at `rename/preview.js:55` | none found | existing `assets/rename/preview.js` slice |
| `renamePreviewAggregateObject` | `function renamePreviewAggregateObject(preview, aggregateKey, rowKey)` at `rename/preview.js:18` | none found | existing `assets/rename/preview.js` slice |
| `renameFormatCounts` | `function renameFormatCounts(counts, labeler = null)` at `rename/preview.js:31` | none found | existing `assets/rename/preview.js` slice |
| `renameTemplateLabel` | `function renameTemplateLabel(preview, key)` at `rename/preview.js:39` | none found | existing `assets/rename/preview.js` slice |
| `renderRenameBulkEditor` | `function renderRenameBulkEditor(message = "")` at `renameView.js:2018` | `app:1650` | `assets/rename/bulkEdit.js` |
| `stageRenameBulkEdit` | `function stageRenameBulkEdit()` at `renameView.js:2036` | `app:1654`, `static-rename:457` | `assets/rename/bulkEdit.js` |
| `usePipelineNamesForRenameScope` | `function usePipelineNamesForRenameScope()` at `renameView.js:2066` | `app:1656` | `assets/rename/bulkEdit.js` |
| `setRenameBulkForce` | `function setRenameBulkForce(forceValue)` at `renameView.js:2077` | `app:1658`, `app:1660`, `static-rename:458` | `assets/rename/bulkEdit.js` |
| `clearRenameBulkOverrides` | `function clearRenameBulkOverrides()` at `renameView.js:2093` | `app:1662`, `static-rename:459` | `assets/rename/bulkEdit.js` |
| `renameBulkScopeRows` | `function renameBulkScopeRows()` at `renameView.js:1961` | none found | `assets/rename/bulkEdit.js` |
| `renameBulkEditedName` | `function renameBulkEditedName(name)` at `renameView.js:1985` | none found | `assets/rename/bulkEdit.js` |
| `renameCurrentFinalName` | `function renameCurrentFinalName(row)` at `renameView.js:1149` | none found | `assets/rename/bulkEdit.js` |
| `renderRenameSelectionAudit` | `function renderRenameSelectionAudit()` at `rename/applyReadiness.js:76` | none found | existing `assets/rename/applyReadiness.js` slice |
| `renameSelectionAuditStatus` | `function renameSelectionAuditStatus(rows)` at `rename/applyReadiness.js:47` | none found | existing `assets/rename/applyReadiness.js` slice |
| `renameSelectionDuplicateTargets` | `function renameSelectionDuplicateTargets(rows)` at `rename/applyReadiness.js:58` | none found | existing `assets/rename/applyReadiness.js` slice |
| `renameApplyScopeBlockers` | `function renameApplyScopeBlockers(rows)` at `rename/applyReadiness.js:62` | none found | existing `assets/rename/applyReadiness.js` slice |
| `renderRenameApplyReadiness` | `function renderRenameApplyReadiness()` at `rename/applyReadiness.js:255` | none found | existing `assets/rename/applyReadiness.js` slice |
| `renameApplyReadinessRows` | `function renameApplyReadinessRows()` at `rename/applyReadiness.js:135` | none found | existing `assets/rename/applyReadiness.js` slice |
| `renameApplyReadinessStatus` | `function renameApplyReadinessStatus(rows)` at `rename/applyReadiness.js:243` | none found | existing `assets/rename/applyReadiness.js` slice |
| `setRenamePreviewBusy` | `function setRenamePreviewBusy(isBusy)` at `renameView.js:2564` | none found | `renameView.js` facade/state coordinator |
| `setRenameApplyBusy` | `function setRenameApplyBusy(isBusy)` at `renameView.js:2569` | none found | `renameView.js` facade/state coordinator |
| `syncRenameCommandButtons` | `function syncRenameCommandButtons()` at `renameView.js:2581` | `app:1617`, `app:1627`, `app:1651`, `node-smoke:414`, `browser-smoke:545` | `renameView.js` facade/state coordinator |
| `syncRenameBadCaseButton` | `function syncRenameBadCaseButton()` at `renameView.js:1399` | none found | `renameView.js` facade/state coordinator |
| `renameBadCasePayloadFromRow` | `function renameBadCasePayloadFromRow(row, overrides = {})` at `renameView.js:1330` | `node-smoke:348` | `assets/rename/badCase.js` |
| `submitRenameBadCasePayload` | `async function submitRenameBadCasePayload(payload)` at `renameView.js:1360` | `settings:2239`, `settings:2255`, `static-rename:213` | `assets/rename/badCase.js` |
| `openRenameBadCaseDialog` | `function openRenameBadCaseDialog()` at `renameView.js:1410` | `node-smoke:353` | `assets/rename/badCase.js` |
| `submitRenameBadCaseDialog` | `async function submitRenameBadCaseDialog()` at `renameView.js:1434` | `node-smoke:362` | `assets/rename/badCase.js` |
| `renderRenameDetail` | `function renderRenameDetail(item)` at `rename/applyReadiness.js:278` | none found | existing `assets/rename/applyReadiness.js` slice |
| `selectRenameRow` | `function selectRenameRow(item)` at `renameView.js:1920` | none found | `renameView.js` facade/state coordinator |
| `getSelectedRenameRow` | `function getSelectedRenameRow()` at `renameView.js:1078` | none found | `renameView.js` facade/state coordinator |
| `getCheckedRenameRows` | `function getCheckedRenameRows()` at `renameView.js:1083` | none found | `renameView.js` facade/state coordinator |
| `renameRowCanApply` | `function renameRowCanApply(item)` at `renameView.js:1154` | none found | `renameView.js` facade/state coordinator |
| `setRenameRowChecked` | `function setRenameRowChecked(item, checked)` at `renameView.js:1198` | none found | `renameView.js` facade/state coordinator |
| `checkApplicableRenameRows` | `function checkApplicableRenameRows()` at `renameView.js:1211` | `app:1637`, `node-smoke:398`, `node-smoke:412`, `node-smoke:520`, `node-smoke:534`, `static-rename:450` | `renameView.js` facade/state coordinator |
| `checkAllRenameRows` | `function checkAllRenameRows()` at `renameView.js:1234` | `app:1639`, `node-smoke:404`, `static-rename:451` | `renameView.js` facade/state coordinator |
| `clearCheckedRenameRows` | `function clearCheckedRenameRows()` at `renameView.js:1260` | `app:1641`, `node-smoke:397`, `node-smoke:403`, `node-smoke:410`, `browser-smoke:584`, `static-rename:452` | `renameView.js` facade/state coordinator |
| `moveCheckedRenamePaths` | `function moveCheckedRenamePaths(direction)` at `renameView.js:1846` | `app:1643`, `app:1645`, `static-rename:453`, `static-rename:454` | `renameView.js` facade/state coordinator |
| `naturalSortRenamePaths` | `function naturalSortRenamePaths()` at `renameView.js:1895` | `app:1647`, `static-rename:455` | `renameView.js` facade/state coordinator |
| `naturalCompareText` | `function naturalCompareText(left, right)` at `renameView.js:1880` | none found | `renameView.js` facade/state coordinator |
| `renderRenameFileSourceSummary` | `function renderRenameFileSourceSummary(message = "")` at `renameView.js:1656` | `app:1626`, `app:1629`, `node-smoke:328`, `browser-smoke:521` | `assets/rename/pathInput.js` |
| `useSelectedQueueRowForRename` | `function useSelectedQueueRowForRename()` at `renameView.js:1813` | `app:1604`, `node-smoke:263` | `assets/rename/pathInput.js` |
| `useLoadedQueueRowsForRename` | `function useLoadedQueueRowsForRename()` at `renameView.js:1825` | `app:1606`, `node-smoke:266` | `assets/rename/pathInput.js` |
| `appendRenamePaths` | `function appendRenamePaths(paths, sourceLabel, origin = "", messageSuffix = "")` at `renameView.js:1688` | none found | `assets/rename/pathInput.js` |
| `addRenamePathFromInput` | `function addRenamePathFromInput()` at `renameView.js:1725` | `app:1612`, `app:1621`, `node-smoke:258` | `assets/rename/pathInput.js` |
| `browseRenamePaths` | `async function browseRenamePaths(selectionMode = "files")` at `renameView.js:1738` | `app:1608`, `app:1610` | `assets/rename/pathInput.js` |
| `clearRenamePaths` | `function clearRenamePaths()` at `renameView.js:1785` | `app:1614`, `node-smoke:261`, `node-smoke:269`, `node-smoke:289`, `node-smoke:295` | `assets/rename/pathInput.js` |
| `syncRenameCheckedCount` | `function syncRenameCheckedCount()` at `renameView.js:1185` | none found | `renameView.js` facade/state coordinator |
| `applyRenameSelectedOverride` | `function applyRenameSelectedOverride()` at `renameView.js:2138` | `app:1631` | `assets/rename/bulkEdit.js` |
| `clearRenameSelectedOverride` | `function clearRenameSelectedOverride()` at `renameView.js:2153` | `app:1633` | `assets/rename/bulkEdit.js` |
| `applySelectedRename` | `async function applySelectedRename()` at `renameView.js:2463` | `app:1635`, `browser-smoke:850`, `browser-smoke:857` | `assets/rename/commands.js` |
| `undoLastRenameApply` | `async function undoLastRenameApply()` at `renameView.js:3406` | `node-smoke:462`, `node-smoke:474` | `assets/rename/commands.js` |
| `replaceRenamePathText` | `function replaceRenamePathText(appliedRows)` at `renameView.js:2169` | none found | `assets/rename/commands.js` |
| `renderRenameApplyResult` | `function renderRenameApplyResult(result)` at `renameView.js:2342` | `browser-smoke:643` | `renameView.js` facade/state coordinator delegating to existing `assets/rename/applyResult.js` slice |
| `renameApplyResultLines` | `function renameApplyResultLines(result)` at `rename/applyResult.js:11` | none found | existing `assets/rename/applyResult.js` slice |
| `renderRenameApplyOutcomeReview` | `function renderRenameApplyOutcomeReview(result)` at `rename/applyResult.js:225` | none found | existing `assets/rename/applyResult.js` slice |
| `renderRenameApplyProgress` | `function renderRenameApplyProgress(payload)` at `rename/applyResult.js:279` | none found | existing `assets/rename/applyResult.js` slice |
| `renameApplyProgressBars` | `function renameApplyProgressBars(payload)` at `rename/applyResult.js:252` | none found | existing `assets/rename/applyResult.js` slice |
| `renameApplyOutcomeRows` | `function renameApplyOutcomeRows(result)` at `rename/applyResult.js:117` | none found | existing `assets/rename/applyResult.js` slice |
| `renameApplyOutcomeStatus` | `function renameApplyOutcomeStatus(result)` at `rename/applyResult.js:87` | none found | existing `assets/rename/applyResult.js` slice |
| `renameApplyOutcomeSummaryLines` | `function renameApplyOutcomeSummaryLines(result)` at `rename/applyResult.js:199` | none found | existing `assets/rename/applyResult.js` slice |
| `renameApplyOutcomeStatusState` | `function renameApplyOutcomeStatusState(status)` at `rename/applyResult.js:104` | none found | existing `assets/rename/applyResult.js` slice |
| `renameSourceKey` | `function renameSourceKey(item)` at `renameView.js:1074` | none found | `renameView.js` facade/state coordinator |
| `renameStatusExplanation` | `function renameStatusExplanation(status)` at `renameLabels.js:2` | none found | `renameLabels.js` |
| `renamePreviewSourceLabel` | `function renamePreviewSourceLabel(value)` at `renameLabels.js:17` | none found | `renameLabels.js` |
| `renameConfidenceExplanation` | `function renameConfidenceExplanation(value)` at `renameLabels.js:38` | none found | `renameLabels.js` |
| `renameConfidenceLabel` | `function renameConfidenceLabel(item)` at `renameLabels.js:53` | none found | `renameLabels.js` |
| `isRenameApplyCommand` | `function isRenameApplyCommand(entry)` at `renameHistoryView.js:2` | none found | `renameHistoryView.js` |
| `renameApplyHistoryLine` | `function renameApplyHistoryLine(entry)` at `renameHistoryView.js:6` | none found | `renameHistoryView.js` |
| `renderRenameApplyHistory` | `function renderRenameApplyHistory(history = [])` at `renameHistoryView.js:29` | none found | `renameHistoryView.js` |
| `applyRenameWorkbench` | `async function applyRenameWorkbench()` at `renameView.js:3345` | none found | `assets/rename/commands.js` |
| `classifyRenamePathValues` | `function classifyRenamePathValues(paths = renameCurrentPathValues())` at `renameView.js:1486` | none found | `assets/rename/pathInput.js` |
| `normalizeRenameDroppedPathValues` | `function normalizeRenameDroppedPathValues(values)` at `renameView.js:1528` | none found | `assets/rename/pathInput.js` |
| `renameDroppedPathFromFile` | `function renameDroppedPathFromFile(file)` at `renameView.js:1541` | `node-smoke:281`, `browser-smoke:470` | `assets/rename/pathInput.js` |
| `renameDroppedPathValuesFromDataTransfer` | `function renameDroppedPathValuesFromDataTransfer(dataTransfer)` at `renameView.js:1551` | none found | `assets/rename/pathInput.js` |
| `renameDroppedPathValuesFromBridgeDetail` | `function renameDroppedPathValuesFromBridgeDetail(detail)` at `renameView.js:1557` | `node-smoke:270`, `browser-smoke:459` | `assets/rename/pathInput.js` |
| `handleRenameDroppedPaths` | `async function handleRenameDroppedPaths(paths, sourceLabel = "Drag and drop")` at `renameView.js:1562` | `node-smoke:284`, `node-smoke:290`, `node-smoke:296`, `browser-smoke:473`, `browser-smoke:480`, `browser-smoke:486` | `assets/rename/pathInput.js` |
| `renameApplicablePreviewRows` | `function renameApplicablePreviewRows()` at `renameView.js:3341` | none found | `assets/rename/commands.js` |
| `renameOpenConfirmDialog` | `function renameOpenConfirmDialog(rowsToApply, outsideRootRows)` at `renameView.js:3072` | none found | `assets/rename/dialogs.js` |
| `renameOpenUndoConfirmDialog` | `function renameOpenUndoConfirmDialog()` at `renameView.js:3120` | none found | `assets/rename/dialogs.js` |
| `renameOpenResultDialog` | `function renameOpenResultDialog(result)` at `renameView.js:3166` | `browser-smoke:691` | `assets/rename/dialogs.js` |
| `renameSyncModeFieldVisibility` | `function renameSyncModeFieldVisibility()` at `renameView.js:3443` | none found | `renameView.js` facade/state coordinator |
| `renameInitDropZone` | `function renameInitDropZone()` at `renameView.js:3459` | none found | `assets/rename/pathInput.js` |
| `renameInitWorkbenchEvents` | `function renameInitWorkbenchEvents()` at `renameView.js:3498` | `app:1666` | `renameView.js` facade/state coordinator |
## Rename Route Ledger

| Route | Method | Source call site | Mutation class | Required confirmation | Owner and boundary | Test coverage |
|---|---|---|---|---|---|---|
| `/api/rename/cleaning-filters` | GET | `RENAME_FILTER_CATALOG_ROUTE` at `renameView.js:13`, called from `loadRenameMovieFilterCatalog` | `none` | none | Backend returns saved movie/TV cleaning filter catalog only | `test_api_contract_payload.py`, `test_application_facade_local_api_rename.py`, browser rename smoke |
| `/api/rename/movie-cleaning-filters` | GET | `RENAME_MOVIE_FILTER_CATALOG_ROUTE` at `renameView.js:14`, fallback at `renameView.js:453` | `none` | none | Backend returns movie cleaning filter catalog only | `test_api_contract_payload.py`, `test_application_facade_local_api_rename.py` |
| `/api/rename/clean-filename-preview` | GET | `RENAME_CLEAN_FILENAME_PREVIEW_ROUTE` at `renameView.js:15`; query builders at `renameView.js:462` and `renameView.js:700` | `none` | none | Backend cleaner/workbench comparison and suggestions; writes nothing | `test_api_contract_payload.py`, `test_application_facade_local_api_rename.py`, browser rename smoke |
| `/api/rename/preview` | POST | `refreshRenamePreview` posts at `renameView.js:2695` | `none` | none | Backend-owned predictions only; WebView may render preview evidence | `test_facade_rename_policy.py`, `test_service_rename_preview.py`, WebView rename smokes |
| `/api/rename/browse` | POST | dropped path resolution at `renameView.js:1576`; picker at `renameView.js:1752` | `shell-dialog` | none | Backend-owned native picker or dropped-path normalization; WebView stages returned media paths only | `test_application_facade_local_api_rename.py`, `test_api_path_dialogs.py`, WebView browser rename smoke |
| `/api/rename/filter-cases` | POST | `submitRenameBadCasePayload` posts at `renameView.js:1362` | `test-fixture-write` | `confirm_append: true` | Appends backend-validated bad-case corpus rows only; no media mutation | `test_rename_workbench.py`, `test_rename_bad_case_corpus.py`, `test_api_command_contracts.py`, node rename smoke |
| `/api/rename/apply` | POST | `applyRenameWorkbench` posts at `renameView.js:3387` | `filesystem-mutation` | `confirm_apply: true`; outside-root rows also require `allow_outside_configured_roots: true` | Backend rebuilds plan, checks roots/collisions/sidecars, and mutates files; WebView submits checked `selected_sources` only | `test_application_facade_rename.py`, `test_service_rename_apply.py`, WebView rename smokes |
| `/api/rename/undo` | POST | `undoLastRenameApply` posts at `renameView.js:3421` | `filesystem-mutation` | `confirm_undo: true` | Backend validates undo manifest under resolved undo root before reversing media/sidecar operations | `test_application_facade_local_api_rename.py`, `test_service_rename_apply_runner.py`, `test_api_command_contracts.py`, WebView rename smokes |

## DOM Ledger

The partial currently defines 96 unique `rename-*` IDs. All 96 are present in
`docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`.

| Region | IDs | Renderer/helper owner | Smoke/static coverage |
|---|---|---|---|
| Choose Files / path intake | `rename-stage-files-heading`, `rename-file-source-status`, `rename-browse-files-button`, `rename-browse-folder-button`, `rename-clear-paths-button`, `rename-add-path-input`, `rename-add-path-button`, `rename-drop-zone`, `rename-paths`, `rename-file-source-summary` | `browseRenamePaths`, `appendRenamePaths`, `addRenamePathFromInput`, `clearRenamePaths`, `handleRenameDroppedPaths`, `renderRenameFileSourceSummary` | `test_application_facade_web_static_rename.py`, `test_rename_workbench.py`, node rename smoke, browser rename smoke, `test_api_static_files_policy.py` for core table/readiness IDs |
| Naming Mode | `rename-stage-mode-heading`, `rename-status`, `rename-mode`, `rename-template-preset`, `rename-show`, `rename-season`, `rename-start`, `rename-movie-year`, `rename-sidecars`, `rename-force-pipeline`, `rename-pipeline-preview`, `rename-preview-button` | `collectRenameRequest`, `renameSyncModeFieldVisibility`, `refreshRenamePreview`, `syncRenameCommandButtons` | Static rename tests, workbench tests, node rename smoke, browser rename smoke |
| Preview table and selection | `rename-stage-preview-heading`, `rename-preview-status`, `rename-rows`, `rename-table-legend`, `rename-check-applicable-button`, `rename-check-all-button`, `rename-clear-checks-button`, `rename-selected-count`, `rename-selection-audit-status`, `rename-selection-audit`, `rename-detail` | `renderRenamePreview`, `renderRenameRows`, `selectRenameRow`, `checkApplicableRenameRows`, `checkAllRenameRows`, `clearCheckedRenameRows`, `renderRenameSelectionAudit`, `renderRenameDetail` | Static rename tests, node rename smoke, browser rename smoke |
| Review evidence panels | `rename-review-board-status`, `rename-review-board`, `rename-batch-safety`, `rename-pipeline-handoff-status`, `rename-pipeline-handoff`, `rename-summary` | existing `rename/preview.js` slice via parent facade | Static rename tests, workbench tests, node rename smoke, browser rename smoke |
| Apply controls and readiness | `rename-apply-button`, `rename-undo-button`, `rename-apply-status-hint`, `rename-apply-status-panel`, `rename-apply-status-summary`, `rename-undo-status`, `rename-apply-progress-bars`, `rename-apply-readiness-details`, `rename-apply-readiness-rows`, `rename-apply-readiness-legend`, `rename-apply-readiness-status` | `syncRenameCommandButtons`, existing `rename/applyReadiness.js`, existing `rename/applyResult.js`, apply/undo command flow | Static rename tests, workbench tests, node rename smoke, browser rename smoke, `test_api_static_files_policy.py` |
| Apply outcome and history | `rename-apply-outcome-details`, `rename-apply-outcome-rows`, `rename-apply-outcome-legend`, `rename-apply-outcome-status`, `rename-apply-outcome-summary`, `rename-last-apply-status`, `rename-last-apply-detail`, `rename-apply-history` | existing `rename/applyResult.js`, `renameHistoryView.js`, parent `renderRenameApplyResult` wrapper | Static rename tests, workbench tests, node rename smoke, browser rename smoke |
| Confirm dialog | `rename-confirm-dialog`, `rename-confirm-title`, `rename-confirm-count`, `rename-confirm-mutation-warning`, `rename-confirm-list`, `rename-confirm-warning`, `rename-confirm-cancel-button`, `rename-confirm-apply-button` | `renameOpenConfirmDialog`, `renameOpenUndoConfirmDialog`, dialog helpers | Workbench tests, node rename smoke, browser rename smoke |
| Result dialog | `rename-result-dialog`, `rename-result-title`, `rename-result-counts`, `rename-result-success-label`, `rename-result-success`, `rename-result-unchanged-label`, `rename-result-unchanged`, `rename-result-skipped-label`, `rename-result-skipped`, `rename-result-protected-label`, `rename-result-protected`, `rename-result-failed-label`, `rename-result-failed`, `rename-result-summary`, `rename-result-errors`, `rename-result-open-log-button` | `renameOpenResultDialog`, existing `rename/applyResult.js`, diagnostics open handoff for log folder | Static rename tests, workbench tests, browser rename smoke |
| Bad-case dialog | `rename-log-bad-case-button`, `rename-log-bad-case-status`, `rename-log-case-dialog`, `rename-log-case-title`, `rename-log-case-source-folder`, `rename-log-case-source-file`, `rename-log-case-expected-name`, `rename-log-case-expected-show`, `rename-log-case-expected-season`, `rename-log-case-status-select`, `rename-log-case-notes`, `rename-log-case-message`, `rename-log-case-cancel-button`, `rename-log-case-submit-button` | `renameBadCasePayloadFromRow`, `openRenameBadCaseDialog`, `submitRenameBadCaseDialog`, `submitRenameBadCasePayload` | Workbench tests, node rename smoke |

## Direct Caller Search Results

Search command:

```powershell
rg -n "mediaPipelineRenameView\.|const renameView = window\.mediaPipelineRenameView|window\.mediaPipelineRenameView" apps\desktop\webview\static\assets\app.js apps\desktop\webview\static\assets\settingsView.js tests\webview tests\python\desktop
```

Runtime direct callers:

- `app.js:1598-1666` reads `window.mediaPipelineRenameView` and wires:
  `refreshRenamePreview`, `useSelectedQueueRowForRename`,
  `useLoadedQueueRowsForRename`, `browseRenamePaths`, `addRenamePathFromInput`,
  `clearRenamePaths`, `syncRenameCommandButtons`,
  `renderRenameFileSourceSummary`, `applyRenameSelectedOverride`,
  `clearRenameSelectedOverride`, `applySelectedRename`,
  `checkApplicableRenameRows`, `checkAllRenameRows`,
  `clearCheckedRenameRows`, `moveCheckedRenamePaths`,
  `naturalSortRenamePaths`, `renderRenameBulkEditor`, `stageRenameBulkEdit`,
  `usePipelineNamesForRenameScope`, `setRenameBulkForce`,
  `clearRenameBulkOverrides`, `initRenameCleaningFilterEditorEvents`, and
  `renameInitWorkbenchEvents`.
- `settingsView.js:1505-1520` calls `saveRenameCleaningFilterDraft` and
  `renameCleaningFilterConfigPatch` during Settings save review merge.
- `settingsView.js:2238-2255` calls `submitRenameBadCasePayload` for Settings
  rename bad-case logging.

Test direct callers:

- `test_webview_rename_readiness_smoke.py` directly exercises path intake,
  bad-case dialog, checked-row selection, readiness, and undo exports in a Node
  VM with explicit asset load order.
- `test_webview_browser_rename_smoke.py` directly exercises cleaning filter
  init, drag/drop helpers, file source summary, preview rendering, command
  button sync, apply result rendering, result dialog rendering, and readiness
  globals in a browser.
- `test_webview_browser_settings_builder_flush_smoke.py` temporarily patches
  `renameCleaningFilterConfigPatch`.
- `test_application_facade_web_static_rename.py` source-pins namespace wiring,
  removed flat exports, route literals, strict confirmation text, and app shell
  calls.
- `test_rename_workbench.py` reads `renameView.js` directly and source-pins
  workbench labels, dialog IDs, route posts, strict confirmations, and command
  activity text.

## Source-Only Guardrails

These tests read source text or explicit asset lists and must be migrated with
any extraction:

| Test | Current assumption | Migration requirement |
|---|---|---|
| `tests/python/desktop/test_application_facade_web_static_rename.py` | `served_webview_static_contract_bundle()` includes `rename/preview.js`, `rename/applyReadiness.js`, `rename/applyResult.js`, and `renameView.js`; many assertions inspect `bundle.rename_view_js` as a concatenated source bundle | Add any new child asset to the bundle before updating assertions; keep parent facade strings where the test is guarding public namespace calls |
| `tests/python/desktop/test_rename_workbench.py` | Reads `renameView.js` directly through `RENAME_JS`; asserts route calls, strict confirmation snippets, dialog/workbench functions, and labels are in that file | Before moving a pinned snippet, update the test to inspect the new child file or a rename asset bundle; do not delete the assertion without equivalent coverage |
| `tests/webview/test_webview_rename_readiness_smoke.py` | Loads an explicit asset list in Node: DOM helpers, labels, history, `rename/preview.js`, `rename/applyReadiness.js`, `rename/applyResult.js`, then `renameView.js` | Insert new child modules before `renameView.js`; verify no child depends on parent being loaded first |
| `tests/webview/test_webview_browser_rename_smoke.py` | Waits for `window.mediaPipelineRenameView.renderRenamePreview` and `applySelectedRename`, then directly calls namespace exports | Keep namespace wrappers stable; add script tags before `renameView.js` |
| `tests/python/desktop/test_application_facade_web_static_shell.py` | Pins script order from `renameLabels.js` to `renameHistoryView.js` to `renameView.js`, and `renameView.js` before Settings assets | Extend the ordered pair list so every new child loads before `renameView.js` |
| `tests/webview/test_webview_frontend_mutation_boundary.py` | Allows `/api/rename/*` route posts from `renameView.js` only | If a route literal moves to a child file, update route-owner allowlist without weakening the route or confirmation guard |

Stop condition: if a source-only guardrail would fail after extraction and no
replacement assertion exists, do not extract the code.

## Mutable State Baseline

Current mutable state in `renameView.js`:

| State category | Current variables | Owner rule |
|---|---|---|
| Selected row | `selectedRenameSourceKey`; derived through `getSelectedRenameRow`, `selectRenameRow` | Single owner: parent facade/state coordinator until a dedicated selection model is introduced |
| Checked rows | `checkedRenameSourceKeys` | Single owner: checked-row model; child renderers may receive getter/setter dependencies only |
| Path origins | `renamePathOrigins` | Single owner: path intake; backend browse remains the authority for resolved paths |
| Final overrides | `renameFinalOverrides` | Single owner: bulk edit/selected override model |
| Force overrides | `renameForceOverrides` | Single owner: bulk edit/selected override model |
| Preview payload/signature | `lastRenameRows`, `lastRenameEmptyMessage`, `lastRenamePreviewSignature`, `renamePreviewStale`, `renamePreviewRequestId`, `activeRenamePreviewRequestId` | Single owner: preview coordinator; child view modules render snapshots only |
| Command activity | `renameCommandActivityTimer`, `renameCommandActivityState`, `renamePreviewInFlight`, `renameBrowseInFlight`, `renameApplyInFlight`, `renameUndoInFlight`, `renameBadCaseInFlight` | Single owner: command coordinator; children may call busy setters through injected deps |
| Undo manifest | `lastRenameUndoManifest`, `lastRenameUndoCompleted`, `lastRenameApplyHadResult`, `lastRenameApplyResultPayload` | Single owner: apply/undo command coordinator |
| Dialog state | DOM `dialog.returnValue` plus last apply/undo payload state | Single owner: dialogs may render, commands decide when to call backend |
| Workbench state | `renameWorkbenchInFlight`, `renameWorkbenchEventsBound`, `lastRenameWorkbenchPayload`, `renameWorkbenchHasStagedSuggestions` | Single owner: settings cleaner workbench; stages suggestions only |
| Filter editor state | `renameCleaningFilterEventsBound`, `renameFilterPreviewRequestId`, `renameFilterPreviewTimer`, `renameCleaningFilterSaveMessage`, `renameCleaningFilterSaveMessageUntil`, localStorage key `mediapipeline.rename.cleaningFilters.v1` | Single owner: cleaning filter editor; it can stage Settings patch/local draft only |

## Target Troubleshooting Seams

| Seam | Candidate owner | Current code | Clean failure seam | Rollback rule |
|---|---|---|---|---|
| Cleaning filter editor | `assets/rename/cleaningFilters.js` | `renameView.js:128-546`, `1015-1072`; exports listed above | Can stage filter patch through Settings namespace and localStorage; must not save settings directly | Move functions back into parent and remove child script; keep Settings callers unchanged |
| Settings filename cleaner workbench | `assets/rename/workbench.js` | `renameView.js:557-983` | Builds read-only backend clean-filename queries and suggestion rows; `saveRenameWorkbenchCase` delegates to bad-case append with `confirm_append` | Move functions back into parent; keep bad-case submit facade stable |
| Path intake | `assets/rename/pathInput.js` | `renameView.js:1466-1825`, drop-zone init at `3459` | Handles typed paths, backend browse results, queue handoffs, and drag/drop; backend browse remains shell-dialog authority | Move handlers back into parent; route owner remains `/api/rename/browse` |
| Preview model | existing `assets/rename/preview.js`, possible `assets/rename/preview.model.js` later | Existing slice plus parent helpers at `1074-1185` | Classifies duplicates/statuses/warnings/caps from backend preview rows only | Keep existing slice; if a new model fails, collapse back into `preview.js` or parent |
| Preview view | existing `assets/rename/preview.js`, possible `assets/rename/preview.view.js` later | Parent render table at `2467-2564`, existing review panels in `rename/preview.js` | Renders preview rows, selected-row detail, file summary, and source summaries without mutation | Move view renderers back into parent; backend preview route unchanged |
| Bulk edit | `assets/rename/bulkEdit.js` | `renameView.js:1961-2093`, selected overrides at `2138-2153` | Stages local final-name/force overrides only; must not call apply | Move functions back into parent; preserve override state owner |
| Bad-case logging | `assets/rename/badCase.js` | `renameView.js:1330-1434`, Settings caller at `settingsView.js:2238-2255` | Builds bad-case fixture append payloads with `confirm_append: true`; no media mutation | Move payload/dialog code back into parent; route remains `/api/rename/filter-cases` |
| Apply readiness | existing `assets/rename/applyReadiness.js` | Existing slice loaded before parent | Explains apply blockers; no route calls | Already extracted; rollback is inline slice body into parent |
| Apply/undo commands | `assets/rename/commands.js` | `renameView.js:2169-2463`, `3341-3423` | Calls backend apply/undo with `confirm_apply`/`confirm_undo`; no child owns rename policy | Move commands back into parent; strict confirmation snippets must remain |
| Dialogs | `assets/rename/dialogs.js` | `renameView.js:2849-3339` | Renders confirm/result/undo dialogs; does not decide backend safety | Move dialog helpers back into parent; command flow remains strict-confirmed |

First valid extraction phase: cleaning filter editor only. It has a stable
settings-facing facade (`saveRenameCleaningFilterDraft`,
`renameCleaningFilterConfigPatch`, `initRenameCleaningFilterEditorEvents`), no
media mutation route, and a rollback path that restores the functions into
`renameView.js`. Before executing it, update the source-only tests to read the
new child asset and keep the parent namespace wrappers.

## Required Validation Before Any Extraction

Baseline commands requested for this prework:

```powershell
git status --short
rg -n "mediaPipelineRenameView|renameView.js|/api/rename|confirm_apply|confirm_undo|confirm_append" apps tests docs/inventories
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_rename_readiness_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_rename_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_web_static_rename -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_rename_workbench -q
npm run webview:prework:check
```

Additional extraction-gate checks:

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_web_static_shell -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_frontend_mutation_boundary -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_contract_payload -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_command_contracts -q
```

Real-media validation is not required for this docs-only prework. A later
behavior-preserving WebView extraction also should not require real-media
validation unless it changes backend rename apply/undo policy, route payloads,
source/scratch/output movement, sidecar policy, or confirmation semantics.
