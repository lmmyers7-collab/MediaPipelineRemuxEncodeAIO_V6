---
file: apps/desktop/webview/static/assets/app/layoutManager.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 5e15375794ed0d86993db40e9a8938b868a5c5bdc866f30baa6e77e1aeacc673
---
# `apps/desktop/webview/static/assets/app/layoutManager.js`

**Purpose:** JavaScript implementation for layout manager; exposes _beginPanelPointerDrag, _clearDropTargetClasses, _clearPanelHolding.

**Public symbols:** `_beginPanelPointerDrag`, `_clearDropTargetClasses`, `_clearPanelHolding`, `_finishPanelPointerDrag`, `_injectCustomizeBar`, `_layoutActivePage`, `_layoutContainerKey`, `_layoutContainerLabel`, `_layoutDefaultPanelType`, `_layoutPageIdFor`, `_layoutPageLabel`, `_layoutPanelIsAuthoredEvidence`, `_layoutPanelIsEditorExcluded`, `_layoutPanelIsEvidence`, `_layoutPanelsInContainer`, `_layoutPanelTitle`, `_layoutSetPanelType`, `_layoutSetStatus`, `_layoutSiblingPanels`, `_layoutSlug`, `_layoutTabPaneKey`, `_loadLayout`, `_movePanelByStep`, `_onDragEnd`, `_onDragHandlePointerDown`, `_onDragLeave`, `_onDragOver`, `_onDragStart`, `_onDrop`, `_panelIndexInContainer`, `_panelKey`, `_projectedDropState`, `_pulseMovedPanel`, `_resetPanelPointerDragState`, `_saveLayout`
**In-repo imports:** `window.__layoutManagerDrawerModule`, `window.__layoutManagerNormalizationModule`, `window.addEventListener`, `window.innerHeight`, `window.innerWidth`, `window.mediaPipelineAppLayoutManager`, `window.removeEventListener`
**DOM selectors:** `.layout-drag-hint`, `.page[data-page-panel]`, `.page[data-page-panel].is-visible`, `.panel-customize-bar`, `.panel-drop-above, .panel-drop-below, .panel-drop-target`, `.panel-heading h2, .panel-heading h3`, `.pcb-btn-advanced`, `.pcb-btn-hidden`, `.pcb-btn-move-down`, `.pcb-btn-move-up`, `.pcb-btn-move-up, .pcb-btn-move-down`, `.pcb-drag-handle`, `:scope > section.panel[data-panel-key]`, `h1`, `section.panel[data-panel-key]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/app/layoutManager.js`._
