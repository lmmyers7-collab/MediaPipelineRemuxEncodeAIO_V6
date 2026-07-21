---
file: apps/desktop/webview/static/assets/app/layoutManager/normalization.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 4da08a3382dec94e0e22ed316d42e433dcf08b90e8f8ea24206978497dedcaad
---
# `apps/desktop/webview/static/assets/app/layoutManager/normalization.js`

**Purpose:** JavaScript implementation for normalization; exposes _applyStoredOrder, _applyStoredPanelState, _copyPanelContextAttributes.

**Public symbols:** `_applyStoredOrder`, `_applyStoredPanelState`, `_copyPanelContextAttributes`, `_createLayoutGeneratedPanel`, `_extractLooseGroups`, `_flattenAdvancedWrappers`, `_initLayoutContainer`, `_initPageLayout`, `_layoutInferPanelType`, `_layoutMakeHeading`, `_layoutManagedContainers`, `_layoutNodeHasContent`, `_layoutPanelTitleFromHeading`, `_layoutPaneTitle`, `_normalizeLayoutTabPaneContainers`, `_panelKeys`, `_splitDirectPanelSubsections`, `_splitLooseContentIntoPanels`, `_storedOrderMatchesCurrentPanels`, `add`, `createLayoutManagerNormalization`
**In-repo imports:** `window.__layoutManagerNormalizationModule`
**DOM selectors:** `.panel-customize-bar`, `.panel-heading h2, .panel-heading h3`, `.pcb-btn-advanced`, `.pcb-btn-hidden`, `.pcb-btn-move-down`, `.pcb-btn-move-up`, `.pcb-drag-handle`, `.settings-tab-pane`, `.settings-tab-pane:not(section.panel)[data-settings-tab], .settings-tab-pane:not(section.panel)[data-diag-tab], .settings-tab-pane:not(section.panel)[data-completed-tab], .settings-tab-pane:not(section.panel)[data-launch-tab-panel], .settings-tab-pane:not(section.panel)[data-queue-tab-panel], .settings-tab-pane:not(section.panel)[data-reports-tab-panel]`, `:scope > .panel-heading`, `:scope > .panel-heading.panel-subheading`, `:scope > div[data-advanced]`, `:scope > section.panel`, `:scope > section.panel[data-advanced]`, `section.panel > div, .settings-tab-pane > div`, `section.panel.settings-tab-pane`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/app/layoutManager/normalization.js`._
