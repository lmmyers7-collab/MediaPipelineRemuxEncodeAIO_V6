---
file: apps/desktop/webview/static/assets/launch/scopeControls.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: b00efdb0495b28713d16c22599a738f5228964afb1e6edc99b8e622ba775caa6
---
# `apps/desktop/webview/static/assets/launch/scopeControls.js`

**Purpose:** JavaScript implementation for scope controls; exposes createLaunchScopeControlsModule, loadPriorityExportStatus, pipelineModeLabel.

**Public symbols:** `createLaunchScopeControlsModule`, `loadPriorityExportStatus`, `pipelineModeLabel`, `pipelineModeStartLabel`, `pipelineSingleFileValue`, `selectPipelineModePreset`, `selectPipelineScopePreset`, `syncPipelineModeControls`, `syncPipelineScopeControls`
**In-repo imports:** `);
      const ready = Boolean(payload?.ready) && String(payload?.status ||`, `);
    const idInput = byId(`, `);
    if (priorityExportContainer) {
      const show = selectedScope ===`, `);
    if (status) status.textContent =`, `;
      }
    } catch (error) {
      if (status) status.textContent = `Priority export status failed to load: ${error}`;
    }
    renderAllLaunchPreflights();
    onControlsChanged();
  }

  function selectPipelineScopePreset(scope) {
    const requestedScope = String(scope ||`, `;
    if (idInput) {
      idInput.value =`, `window.__launchScopeControlsModule`
**HTTP routes:** `/api/queue/priority-export`
**DOM selectors:** `[data-pipeline-mode-preset]`, `[data-pipeline-priority-export-container]`, `[data-pipeline-scope-preset]`, `[data-pipeline-single-file-container]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/launch/scopeControls.js`._
