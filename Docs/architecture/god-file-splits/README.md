# God-File Split Plans

Last reviewed: 2026-06-04

This folder records decomposition plans for current monolithic or high-strain
files. It is an architecture planning aid, not an active work checklist and not
a behavior-change approval.

The review used `ops/scripts/dev/check_godfiles.py`, `rg` symbol inventories,
available `docs/generated/summaries/` files, `docs/CURRENT_PROJECT_STATE.md`, and
`docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`. Smoke tests and generated,
vendor, runtime, lock, and schema artifacts are not split targets here.

## Split Rules

- Preserve existing imports, globals, and entrypoints until callers and smoke
  coverage prove the new shape is stable.
- Extract pure helpers and DTO/render builders before mutating behavior.
- Keep Python destinations under `app/<domain>/`.
- Keep PowerShell destinations under `ops/pipeline/engine/<domain>/`.
- Keep WebView child modules under the owning asset folder and preserve
  namespace-first `window.mediaPipeline*` contracts.
- Do not move media policy, pending-publish drain, source/scratch/output
  movement, settings persistence, command journal, or close-readiness behavior
  without the high-risk validation ladder.

## Priority Set

| File | Plan |
|---|---|
| `ops/pipeline/engine/decide/routing.ps1` | [engine-decide-routing.md](engine-decide-routing.md) |
| `ops/pipeline/entrypoints/MediaPipeline.ps1` | [pipeline-mediapipeline.md](pipeline-mediapipeline.md) |
| `ops/pipeline/engine/publish/pending_transactions.ps1` | [engine-publish-pending-transactions.md](engine-publish-pending-transactions.md) |
| `ops/pipeline/engine/config/config_schema.ps1` | [engine-config-config-schema.md](engine-config-config-schema.md) |
| `ops/pipeline/engine/paths/output_path_planning.ps1` | [engine-paths-output-path-planning.md](engine-paths-output-path-planning.md) |
| `ops/pipeline/engine/subtitles/common.ps1` | [engine-subtitles-common.md](engine-subtitles-common.md) |
| `ops/pipeline/engine/queue/queue_plan.ps1` | [engine-queue-queue-plan.md](engine-queue-queue-plan.md) |
| `ops/pipeline/engine/queue/pipeline_engine.ps1` | [engine-queue-pipeline-engine.md](engine-queue-pipeline-engine.md) |
| `ops/pipeline/engine/queue/local_worker_slots.ps1` | [engine-queue-local-worker-slots.md](engine-queue-local-worker-slots.md) |
| `ops/pipeline/engine/naming/naming.ps1` | [engine-naming-naming.md](engine-naming-naming.md) |
| `app/publish/pending_policy.py` | [app-publish-pending-policy.md](app-publish-pending-policy.md) |
| `app/config/library_profiles.py` | [app-config-library-profiles.md](app-config-library-profiles.md) |
| `app/config/metadata_parts/basic_fields.py` | [app-config-metadata-basic-fields.md](app-config-metadata-basic-fields.md) |
| `app/config/metadata_parts/field_definitions.py` | [app-config-metadata-field-definitions.md](app-config-metadata-field-definitions.md) |
| `app/config/preset_migration.py` | [app-config-preset-migration.md](app-config-preset-migration.md) |
| `app/contracts/config.py` | [app-contracts-config.md](app-contracts-config.md) |
| `app/contracts/stages.py` | [app-contracts-stages.md](app-contracts-stages.md) |
| `app/decide/routing.py` | [app-decide-routing.md](app-decide-routing.md) |
| `app/kernel/config_keys.py` | [app-kernel-config-keys.md](app-kernel-config-keys.md) |
| `app/queue/policy_parts/rows.py` | [app-queue-policy-rows.md](app-queue-policy-rows.md) |
| `app/rename/policy.py` | [app-rename-policy.md](app-rename-policy.md) |
| `app/status/presentation.py` | [app-status-presentation.md](app-status-presentation.md) |
| `ops/pipeline/engine/config/runtime_config.ps1` | [engine-config-runtime-config.md](engine-config-runtime-config.md) |
| `apps/desktop/webview/static/assets/queue/fileOverrides.drawer.js` | [webview-queue-file-overrides-drawer.md](webview-queue-file-overrides-drawer.md) |
| `apps/desktop/webview/static/assets/queueView.js` | [webview-queue-view.md](webview-queue-view.md) |
| `apps/desktop/webview/static/assets/domHelpers.js` | [webview-dom-helpers.md](webview-dom-helpers.md) |
| `apps/desktop/webview/static/assets/launchView.js` | [webview-launch-view.md](webview-launch-view.md) |
| `apps/desktop/webview/static/assets/launchView.risk.js` | [webview-launch-risk.md](webview-launch-risk.md) |
| `apps/desktop/webview/static/assets/networkView.js` | [webview-network-view.md](webview-network-view.md) |
| `apps/desktop/webview/static/assets/settings/patchReview.js` | [webview-settings-patch-review.md](webview-settings-patch-review.md) |
| `apps/desktop/webview/static/assets/settings/policyImpact.js` | [webview-settings-policy-impact.md](webview-settings-policy-impact.md) |
| `apps/desktop/webview/static/assets/settingsLibraries.js` | [webview-settings-libraries.md](webview-settings-libraries.md) |
| `apps/desktop/webview/static/assets/settingsMetadata.js` | [webview-settings-metadata.md](webview-settings-metadata.md) |
| `apps/desktop/webview/static/assets/settingsView.js` | [webview-settings-view.md](webview-settings-view.md) |
| `apps/desktop/webview/static/assets/renameView.js` | [webview-rename-view.md](webview-rename-view.md) |
| `apps/desktop/webview/static/assets/progressView.js` | [webview-progress-view.md](webview-progress-view.md) |
| `apps/desktop/webview/static/assets/app.js` | [webview-app-shell.md](webview-app-shell.md) |
| `apps/desktop/webview/static/assets/completedView.evidence.js` | [webview-completed-evidence.md](webview-completed-evidence.md) |
| `apps/desktop/webview/static/assets/completedView.review.js` | [webview-completed-review.md](webview-completed-review.md) |
| `apps/desktop/webview/static/assets/reportsView.js` | [webview-reports-view.md](webview-reports-view.md) |
| `apps/desktop/tauri/src-tauri/src/backend_contract.rs` | [desktop-tauri-backend-contract.md](desktop-tauri-backend-contract.md) |
| CSS and Settings partial surfaces | [css-and-settings-partials.md](css-and-settings-partials.md) |
| `ops/pipeline/entrypoints/Audit-MediaLibrary.ps1` | [pipeline-audit-media-library.md](pipeline-audit-media-library.md) |

## Non-Targets

- `src/mediapipeline/contracts/schemas/*.json`, `docs/generated/*.json`, `package-lock.json`, and
  `ops/release/metadata/RELEASE_MANIFEST.json` are generated, lock, or release artifacts.
- Smoke tests are intentionally out of scope as split targets.
- `app/contracts/config.py` is listed because helper extraction is useful, but
  the central `Config` contract should remain a single canonical model unless a
  versioned contract redesign is explicitly approved.
