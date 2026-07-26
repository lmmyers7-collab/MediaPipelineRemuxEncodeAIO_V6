---
file: apps/desktop/webview/static/assets/maintenance/releaseCommands.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-07-11
sha256: 7fcb4c0130cf7daaed7e2d042ec545c66dead9614d8a38477004a7653a008fcd
---
# `apps/desktop/webview/static/assets/maintenance/releaseCommands.js`

**Purpose:** JavaScript implementation for release commands; exposes backfillProgressBars, collectReleaseBuildRequest, collectReleaseDryRunRequest.

**Public symbols:** `backfillProgressBars`, `collectReleaseBuildRequest`, `collectReleaseDryRunRequest`, `createMaintenanceReleaseCommands`, `dependencyAtlasProgressBars`, `initMaintenanceViewEvents`, `openDependencyAtlasFolder`, `recordReleasePreviewResult`, `releaseBuildConfirmMessage`, `releasePackageKindForCommand`, `releasePackageProgressBars`, `releasePackageResultHint`, `releasePackageResultStatus`, `releasePreviewMatchesCreate`, `releaseRequestSignature`, `renderBackfillDryRunResult`, `renderBackfillProgress`, `renderDependencyAtlasProgress`, `renderDependencyAtlasResult`, `renderReleaseBuildResult`, `renderReleaseDryRunResult`, `renderReleasePackageInFlightProgress`, `renderReleasePackageProgress`, `runBackfillDryRun`, `runDependencyAtlas`, `runReleaseBuild`, `runReleaseDryRun`, `setReleasePackageStatus`
**In-repo imports:** `window.__maintenanceReleaseCommandsModule`, `window.confirm`
**HTTP routes:** `/api/maintenance/completed-backfill-dry-run`, `/api/maintenance/dependency-atlas`, `/api/maintenance/dependency-atlas/open-folder`, `/api/maintenance/release-build`, `/api/maintenance/release-dry-run`
**State/config identifiers:** `release_manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/maintenance/releaseCommands.js`._
