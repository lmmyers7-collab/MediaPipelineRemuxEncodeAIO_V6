---
file: apps/desktop/webview/static/assets/queue/priority.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: orchestration
token_priority: medium
owner_domain: webview
last_modified: 2026-07-16
last_reviewed: 2026-07-10
sha256: 75305159a2f396ca9f132d521039d122e34bb62188fdff9103b6b39968143f4e
---
# `apps/desktop/webview/static/assets/queue/priority.js`

**Purpose:** JavaScript implementation for priority; exposes actionsPausedForScan, applyDisplayedFileOverrideMarker, applyDisplayedPriorityUpdates.

**Public symbols:** `actionsPausedForScan`, `applyDisplayedFileOverrideMarker`, `applyDisplayedPriorityUpdates`, `beginCommand`, `clearDisplayedPriorityManifest`, `clearPriorityManifest`, `confirmBulk`, `confirmClearManifest`, `controlIds`, `createQueuePriorityModule`, `displayedFileOverrideMarkerForRow`, `endCommand`, `isCurrentCommand`, `normalizedLevel`, `pathKey`, `priorityItemsForSelected`, `refreshDisplayedRows`, `rowHasVisibleMarker`, `rowMatchesPath`, `rowPath`, `rowWithDisplayedFileOverrideMarker`, `sendPriority`, `sendPriorityBulk`, `sendSelectedPriority`, `updateControls`
**In-repo imports:** `window.__queuePriorityModule`, `window.confirm`
**HTTP routes:** `/api/queue/priority`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/queue/priority.js`._
