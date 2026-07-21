---
file: apps/desktop/webview/static/assets/app/lifecycle/navigation.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-16
last_reviewed: 2026-07-11
sha256: 3e849e1be0205ce650266afca4a4aed3b8001e043028e5e5215f8e6bd2e0a023
---
# `apps/desktop/webview/static/assets/app/lifecycle/navigation.js`

**Purpose:** JavaScript implementation for navigation; exposes activateCompletedTab, activateCrossPageTarget, activateDiagnosticsTab.

**Public symbols:** `activateCompletedTab`, `activateCrossPageTarget`, `activateDiagnosticsTab`, `activateSection`, `activateUiQuickLink`, `activateUiQuickLinkModule`, `applyCollapsed`, `applyDefaultActionTooltips`, `applyState`, `applyThemePreference`, `createAppLifecycleNavigation`, `defaultPageFocusTarget`, `ensureElementId`, `focusElementTarget`, `focusPageDestination`, `focusUiQuickLinkTarget`, `initCollapsibleSummaries`, `initCompletedTabNav`, `initDiagnosticsTabNav`, `initLaunchEvidenceToggle`, `initNavigation`, `initSettingsTabNav`, `initThemeToggle`, `initUiQuickLinks`, `kebabCase`, `navigateToPage`, `pagePanelHiddenReasonLines`, `panelHiddenByAdvancedGate`, `panelHiddenByEvidenceGate`, `panelIsCurrentlyVisible`, `panelVisibilityEmptyState`, `rememberPageFocus`, `renderSparkline`, `showCompletedOutputTab`, `showPage`
**In-repo imports:** `],
      [`, `window.__appLifecycleNavigationModule`, `window.mediaPipelineCompletedView`, `window.mediaPipelineLaunchView`, `window.mediaPipelineMaintenanceView`, `window.mediaPipelineMetricsView`, `window.mediaPipelineNetworkView`, `window.mediaPipelinePendingPublishView`, `window.mediaPipelineReportsView`, `window.mediaPipelineRunMonitor`, `window.mediaPipelineScheduleView`, `window.mediaPipelineTelemetryView`, `window.scrollTo`, `window.setTimeout`
**DOM selectors:** `#settings-save-header`, `.nav-button`, `.page-panel-empty-detail`, `.page.is-visible[data-page-panel]`, `.page[data-page-panel]`, `.panel`, `.settings-section-nav-btn[data-settings-tab]`, `.settings-tab-btn[data-completed-tab]`, `.settings-tab-btn[data-diag-tab]`, `.settings-tab-pane[data-completed-tab]`, `.settings-tab-pane[data-diag-tab]`, `.settings-tab-pane[data-settings-tab]`, `.workspace`, `[data-cross-page-target]`, `[data-page-panel]`, `[data-page-panel].is-visible`, `pre.prose-block`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/app/lifecycle/navigation.js`._
