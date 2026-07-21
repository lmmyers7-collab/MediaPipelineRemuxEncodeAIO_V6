---
file: apps/desktop/webview/static/assets/queue/priority.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: orchestration
token_priority: medium
owner_domain: webview
last_modified: 2026-07-20
last_reviewed: 2026-07-10
sha256: d6e7d39269999b62b5d16d3840701c73fec0251ea38099947407793a54b3ca09
---
# `apps/desktop/webview/static/assets/queue/priority.js`

**Purpose:** JavaScript implementation for priority; exposes actionsPausedForScan, applyDisplayedFileOverrideMarker, applyDisplayedPriorityUpdates.

**Public symbols:** `actionsPausedForScan`, `applyDisplayedFileOverrideMarker`, `applyDisplayedPriorityUpdates`, `beginCommand`, `clearDisplayedPriorityManifest`, `clearPriorityManifest`, `confirmBulk`, `confirmClearManifest`, `controlIds`, `createQueuePriorityModule`, `displayedFileOverrideMarkerForRow`, `endCommand`, `exportPriorityQueue`, `isCurrentCommand`, `normalizedLevel`, `pathKey`, `priorityItemsForSelected`, `refreshDisplayedRows`, `rowHasVisibleMarker`, `rowMatchesPath`, `rowPath`, `rowWithDisplayedFileOverrideMarker`, `sendPriority`, `sendPriorityBulk`, `sendSelectedPriority`, `updateControls`
**In-repo imports:** `);
      try {
        const result = await apiPost(`, `, {});
        const data = result?.data && typeof result.data ===`, `;
        if (isCurrentCommand(seq)) setText(`, `];
    }
    function updateControls() {
      const disabled = Boolean(inFlight || getScanLoading());
      controlIds().forEach((id) => { const button = byId(id); if (button) button.disabled = disabled; });
      updateManualOrderControls();
    }
    function beginCommand(message =`, `window.__queuePriorityModule`, `window.confirm`
**HTTP routes:** `/api/queue/priority`, `/api/queue/priority-export`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/queue/priority.js`._
