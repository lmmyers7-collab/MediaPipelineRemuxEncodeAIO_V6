---
file: apps/desktop/webview/static/assets/completed/promotionCommands.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-06-18
last_reviewed: 2026-06-04
sha256: 92aa94786e218735187da6f9159e80eca4f504b096a48eaf8e3d759dfca8b94a
---
# `apps/desktop/webview/static/assets/completed/promotionCommands.js`

**Purpose:** JavaScript implementation for promotion commands; exposes appendCompletedPromotionCellAction, createCompletedPromotionButton, createCompletedPromotionCommandsModule.

**Public symbols:** `appendCompletedPromotionCellAction`, `createCompletedPromotionButton`, `createCompletedPromotionCommandsModule`, `currentFinalLibraryPromotionRunId`, `finalLibraryPromotionActionState`, `finalLibraryPromotionActiveRun`, `finalLibraryPromotionChipState`, `finalLibraryPromotionConfirmMessage`, `finalLibraryPromotionFlagLines`, `finalLibraryPromotionItemsByKey`, `finalLibraryPromotionRunActive`, `finalLibraryPromotionStatusText`, `mergeFinalLibraryPromotionRows`, `noop`, `normalizeDeps`, `promotionStatusTone`, `renderCompletedPromotionActions`, `renderFinalLibraryPromotion`, `requestFinalLibraryPromotion`, `requestFinalLibraryPromotionPause`, `requestFinalLibraryPromotionResume`, `requestSelectedFinalLibraryPromotion`, `setFinalLibraryPromotionCommandBusy`, `setInlineStatus`, `shouldConfirmFinalLibraryPromotion`
**In-repo imports:** `window.__completedViewPromotionCommandsModule`, `window.confirm`, `window.mediaPipelineAppHome`
**HTTP routes:** `/api/final-library-promotion/pause`, `/api/final-library-promotion/promote-queue`, `/api/final-library-promotion/resume`
**DOM selectors:** `[data-completed-promote-selected]`, `td`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/completed/promotionCommands.js`._
