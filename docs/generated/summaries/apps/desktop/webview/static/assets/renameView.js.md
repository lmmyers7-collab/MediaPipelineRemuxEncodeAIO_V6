---
file: apps/desktop/webview/static/assets/renameView.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: rename
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: 7e2e70f1730e4c994bd1709893770a659b7cb0a81ae16dbe47fa060d72578997
---
# `apps/desktop/webview/static/assets/renameView.js`

**Purpose:** JavaScript implementation for rename view; exposes applyRenameWorkbench, applySelectedRename, byAnyId.

**Public symbols:** `applyRenameWorkbench`, `applySelectedRename`, `byAnyId`, `collectRenameRequest`, `initRenameCleaningFilterEditorEvents`, `onRenameFilterOptionChange`, `renameApplicablePreviewRows`, `renameCleaningNode`, `renameCurrentRequestSignature`, `renameMarkInputChanged`, `renamePreviewStatusText`, `renameRequestSignatureFromRequest`, `undoLastRenameApply`, `updateRenamePreviewFreshnessState`
**In-repo imports:** `window.__renameCleaningFiltersModule`, `window.__renameCleaningWorkbenchModule`, `window.__renameCommandEvidenceModule`, `window.__renameConfirmSummaryModule`, `window.__renameDialogsModule`, `window.__renameEditingModule`, `window.__renameInteractionsModule`, `window.__renamePathsModule`, `window.__renamePreviewLifecycleModule`, `window.__renameSelectionModule`, `window.apiGet`, `window.apiPost`, `window.appendCells`, `window.appendCommandResult`, `window.byId`, `window.clearRows`, `window.makeRowSelectable`, `window.mediaPipelineRenameHistoryView`, `window.mediaPipelineRenameLabels`, `window.mediaPipelineRenameView`, `window.setText`
**HTTP routes:** `/api/rename/apply`, `/api/rename/clean-filename-preview`, `/api/rename/cleaning-filters`, `/api/rename/movie-cleaning-filters`, `/api/rename/undo`
**DOM selectors:** `#settings-rename-preview-button`, `#settings-rename-preview-input`
**Exports:** `window.mediaPipelineRenameView.renameInitDropZone`, `window.mediaPipelineRenameView.renameInitWorkbenchEvents`, `window.mediaPipelineRenameView.renameSyncModeFieldVisibility`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/renameView.js`._
