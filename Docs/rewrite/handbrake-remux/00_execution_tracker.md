# HandBrake Remux Rewrite Execution Tracker

This tracker is scoped to the approved docs subtree for the rewrite planning
work. It is not a runtime status file and does not supersede the repository
canonical documents named in `AGENTS.md`.

## Approved Location

- Approved docs and tracker subtree: `Docs/rewrite/handbrake-remux/`
- Approval date: 2026-05-30
- Approved by: operator reply, "approve docs subtree path"
- Repository root: `C:/Users/lmmye/Documents/Codex/2026-04-20-files-mentioned-by-the-user-ass/MediaPipelineRemuxEncodeAIO_V6`

## Source Inputs

- Master prompt: `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- Execution order: `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- Current phase file: `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/12_FINAL_DOCS_OPERATOR_GUIDE_AND_CLEANUP.md`
- Phase 09 implementation scope: operator-provided Phase 08.5 + Phase 09
  plan in the 2026-05-30 Codex thread. The downloaded Phase 09 verification
  and publish file was read for context, but this pass implemented only the
  requested Settings `PipelinePlan` preview route and WebView consumption.
- Phase 09 verification/publish addendum scope: operator request on
  2026-05-30 to perform only the downloaded Phase 09 verification, Output Size
  Check, and publish-gate phase without committing or pushing.
- Phase 11 rollout scope: operator request on 2026-05-31 to perform only the
  downloaded rollout/backcompat/feature-flag phase without committing or
  pushing.
- Phase 12 final docs scope: operator request on 2026-05-31 to perform only
  the downloaded final docs, operator guide, and cleanup phase without
  committing or pushing.

## Current Phase

- Phase: 12 - Final docs, operator guide, and maintenance plan
- Status: Complete for documentation-only operator guide, developer guide,
  migration/rollback/cleanup plan, final acceptance doc, and tracker update.
  Production execution remains on the legacy PowerShell path.
- Completion date: 2026-05-31
- Edit domain: documentation and tracker only in this approved rewrite
  docs/tracker subtree.
- Runtime behavior changes: no production execution behavior changed. This
  phase added documentation only; it did not change route execution, settings
  persistence defaults, FFmpeg command generation, subtitle/audio handling,
  queue behavior, publish/drain behavior, source/scratch/output movement,
  cleanup, command journal behavior, or Tauri lifecycle ownership.
- Commit or push: not performed
- High-risk areas: routing/cutover, settings/config compatibility,
  verification/publish guards, and pending-publish semantics were discussed in
  documentation only. This pass does not approve high-risk production behavior
  changes or replace the required operator-run validation for future cutover.

## Completed Phases

| Phase | Date | Output | Validation | Notes |
| --- | --- | --- | --- | --- |
| 01 | 2026-05-30 | `Docs/rewrite/handbrake-remux/01_repo_audit.md` | Docs-only path/reference checks passed; guardrail preflight/postflight red from baseline drift; see "Validation Notes" | No runtime edits. Worktree was dirty before Phase 01 began. |
| 02 | 2026-05-30 | `Docs/rewrite/handbrake-remux/02_taxonomy_and_terms.md` | Docs-only file existence/reference checks passed; active doc references passed; guardrail preflight/postflight red from the same baseline drift; see "Validation Notes" | No runtime edits, schema migration, UI rename, or label module added. |
| 03 | 2026-05-30 | `app/contracts/source_media.py`, `app/contracts/source_media_adapters.py`, `app/contracts/source_media_values.py`, `app/contracts/source_media_streams.py`, `app/contracts/source_media_derived.py`, `tests/fixtures/source_media/*.json`, `tests/contract/test_source_media_contract.py`, `Docs/rewrite/handbrake-remux/03_source_media_model.md` | Source-media contract tests passed; broader postflight validation recorded below | Additive model/fixtures only. No runtime caller was switched to the new model. |
| 04 | 2026-05-30 | `app/decide/__init__.py`, `app/decide/processing_decision.py`, `app/decide/routing.py`, `app/decide/routing_facts.py`, `app/decide/routing_outputs.py`, `tests/decide/test_processing_decision.py`, `Docs/rewrite/handbrake-remux/04_decision_engine_contract.md` | Decision tests, source-media contract tests, contract discovery, and PowerShell route-selection characterization passed; broader postflight validation recorded below | Additive pure Python decision surface only. Production PowerShell routing remains unchanged. |
| 05 | 2026-05-30 | `app/config/preset_policy.py`, `app/config/preset_migration.py`, `tests/contract/test_preset_policy_contract.py`, `Docs/rewrite/handbrake-remux/05_preset_schema_migration.md` | Preset-policy contract tests passed; broader postflight validation recorded below | Additive `PresetV2` schema and adapters only. Legacy write posture remains active; no v2 persistence or runtime route replacement. |
| 06 | 2026-05-30 | `app/config/preset_encoding_sections.py`, `app/config/preset_policy.py`, `app/config/encoding_capabilities.py`, `app/config/preset_migration.py`, `app/decide/processing_decision.py`, `app/decide/encoding_rules.py`, `app/decide/stream_actions.py`, `app/decide/routing.py`, `app/decide/routing_outputs.py`, `app/decide/__init__.py`, `tests/contract/test_preset_policy_contract.py`, `tests/decide/test_processing_decision.py`, `Docs/rewrite/handbrake-remux/06_encoding_model.md` | Encoding-model contract and decision tests passed; broader postflight validation recorded below | Additive HandBrake-style encoding model and planned-output DTO only. No PowerShell command behavior, UI, settings persistence, or runtime route replacement. |
| 07 | 2026-05-30 | `app/contracts/pipeline_plan.py`, `app/orchestration/planner.py`, `app/orchestration/__init__.py`, `app/contracts/__init__.py`, `tests/orchestration/test_pipeline_planner.py`, `Docs/rewrite/handbrake-remux/07_pipeline_plan_contract.md` | Pipeline planner and decision tests passed; broader postflight validation recorded below | Additive abstract dry-run `PipelinePlan` and command preview only. No concrete FFmpeg args, PowerShell execution change, UI, queue mutation, publish/drain mutation, or runtime route replacement. |
| 07B | 2026-05-30 | `engine/process/pipeline_plan_executor.ps1`, `engine/process/pipeline_plan_executor/validation.ps1`, `Pipeline/Tests/Unit/Invoke-PipelinePlanExecutorChecks.ps1`, `Docs/rewrite/handbrake-remux/07B_plan_executor.md` | Plan-executor parity harness passed; broader postflight validation recorded below | Additive PowerShell dry-run executor only. Production execution remains on the legacy path. Non-MKV concrete command parity and subtitle burn-in are rejected rather than guessed. |
| 08 | 2026-05-30 | `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-settings.html`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settings/patchReview.js`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsMetadata.js`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.js`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.builders.video.js`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/styles.components.css`, `DesktopApp/tests/test_webview_handbrake_settings_ui.py`, `Docs/rewrite/handbrake-remux/08_ui_plan.md` | Phase 08 static WebView tests and generated WebView/project checks passed; broader WebView/static batches remain red from known unrelated baseline drift recorded below | Display-only HandBrake-style Settings grouping. Existing backend settings Preview/Save Patch flow remains intact. No frontend routing decision engine was added; planner preview is honestly marked unavailable/predicted pending cutover. |
| 08.5 | 2026-05-30 | WebView static baseline cleanup in Rename markup/CSS, split-module static tests, lint declaration, summary scope, generated WebView artifacts, and summaries | Broad WebView static unittest batch, `npm run webview:prework:check`, summary freshness, project index, and active doc references passed | Cleanup only. Existing tests stayed contracts except split-module owner assertions were updated. No feature behavior, backend route, or media policy change. |
| 09 | 2026-05-30 | `app/api/commands.py`, `app/api/commands_settings.py`, `app/contracts/api_commands.py`, `app/config/settings_patch_facade.py`, `DesktopApp/mediapipeline_desktop_app/api/contract_command.py`, Settings WebView source-facts preview UI, WebView/API/planner tests, generated WebView/project artifacts, summaries | Backend route tests, planner tests, WebView mutation/static tests, full WebView prework, summary/project/doc checks, and Chrome headless operator-surface proof passed | Additive dry-run Settings `PipelinePlan` preview only. Settings UI sends explicit `SourceMediaInfo` JSON plus staged patch to the backend and renders backend `pipeline_plan.v1`; legacy production execution remains authoritative. |
| 09 verification/publish | 2026-05-30 | `app/contracts/verification.py`, `app/decide/processing_decision.py`, `app/decide/routing_outputs.py`, `app/contracts/pipeline_plan.py`, `app/orchestration/planner.py`, Phase 07B dry-run validator allowlist, Settings/WebView/readiness Output Size Check rendering and terminology, generated WebView artifacts, targeted tests, `Docs/rewrite/handbrake-remux/09_verification_publish_plan.md` | Focused contract/decision/planner/API/WebView tests passed; broader generated-context and postflight checks recorded below | Additive dry-run/reporting model only. Warn-only, block-publish, fail-job, and disabled Output Size Check actions are explicit; block-publish points to existing pending-publish parking but production PowerShell publish/drain behavior is unchanged. |
| 10 | 2026-05-30 | `tests/integration/test_handbrake_remux_regression_matrix.py`, `tests/integration/__init__.py`, `Docs/rewrite/handbrake-remux/10_test_matrix.md` | Focused integration, contract, decision, planner, API/WebView static, plan-executor dry-run, generated-context, and active-doc checks passed; guardrail remains red only from the pre-existing risky-file registry baseline | Metadata-only regression matrix. Covers copy/remux/encode route cases, legacy/v2 parity, dry-run plan shape, Output Size Check warn/block/fail separation, and unprobeable-source rejection without changing production execution. |
| 11 | 2026-05-31 | `app/config/rollout.py`, `tests/contract/test_rollout_policy.py`, Settings `PipelinePlan` preview rollout/comparison evidence, `Docs/rewrite/handbrake-remux/11_rollout_plan.md`, tracker update | Focused rollout-policy and Settings preview tests passed; generated-context and postflight checks recorded below | Additive rollout evidence only. Defaults stay legacy, comparison logging is opt-in, Settings preview remains dry-run/non-executable, and production PowerShell execution remains authoritative. |
| 12 | 2026-05-31 | `Docs/rewrite/handbrake-remux/12_operator_guide.md`, `Docs/rewrite/handbrake-remux/12_developer_guide.md`, `Docs/rewrite/handbrake-remux/12_migration_rollback_cleanup.md`, `Docs/rewrite/handbrake-remux/12_final_acceptance.md`, tracker update | Docs-only generated-context and guard checks recorded below | Documentation-only finalization. Operator/developer guides, migration/rollback notes, cleanup candidates, final acceptance, and cutover limits are documented without deleting code or changing runtime behavior. |

## Validation Notes

- Pre-edit guardrail baseline: `DesktopApp/Runtime/Python/python.exe scripts/dev/ai_guardrail.py preflight --json` failed before Phase 01 edits because of pre-existing worktree and generated-summary/risky-file-registry drift.
- Post-edit guardrail baseline: `DesktopApp/Runtime/Python/python.exe scripts/dev/ai_guardrail.py postflight --json` failed with the same required failing categories: `summary-freshness` and `risky-file-registry`.
- Passing post-edit checks inside the guardrail run: project index, pipeline map, lifecycle map, config schema, stage schema, active doc references, architecture guardrails, naming lint, god-file guard with warnings, and marketecture guard.
- Docs-only validation target passed: the new tracker and audit files exist, key referenced repo paths exist, active doc references pass, and Phase 01 changed only the approved docs subtree.
- Operator surface proof passed: token-enabled local API started from `DesktopApp`, emitted bootstrap on an ephemeral localhost port, and returned HTTP 200 for `/api/contract`; the temporary process was stopped.
- Phase 02 docs-only validation confirmed `00_execution_tracker.md`,
  `01_repo_audit.md`, and `02_taxonomy_and_terms.md` exist in the approved
  subtree, and the active doc reference checker passed.
- Phase 03 targeted validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_source_media_contract`.
  It covers raw ffprobe-style fixtures, existing `ProbeResult` adaptation,
  missing metadata, image subtitles, interlacing, audio policy annotations, and
  strict model validation.
- Phase 03 contract validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests\contract -p "test_*.py"`.
- Phase 03 postflight guardrail remained red in the same required categories
  as the preflight baseline: `summary-freshness` and `risky-file-registry`.
  Project index, pipeline map, lifecycle map, config schema, stage schema,
  active doc references, architecture guardrails, naming lint, god-file guard
  with warnings, and marketecture guard passed.
- Phase 03 adapter helpers were split before Phase 04. The largest new
  source-media helper file is now under the god-file warning threshold, and the
  source-media contract tests still pass.
- Phase 04 targeted decision validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.decide.test_processing_decision`.
  It covers the required reason framework, legacy-key policy mapping, Phase 03
  fixture route characterization, advisory size threshold behavior, unknown
  media type conservative caps, reject behavior, and MP4 audio/subtitle
  cross-constraints.
- Phase 04 compatibility validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_source_media_contract`,
  `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests\contract -p "test_*.py"`,
  `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests -p "test_*.py"`,
  and
  `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-MediaRouteSelectionChecks.ps1`.
- Phase 04 postflight guardrail remained red in the same required categories
  as preflight: `summary-freshness` and `risky-file-registry`. Project index,
  pipeline map, lifecycle map, config schema, stage schema, active doc
  references, architecture guardrails, naming lint, god-file guard with the
  existing warning count, and marketecture guard passed.
- Phase 05 targeted preset-policy validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_preset_policy_contract`.
  It covers legacy-to-`PresetV2` migration, v2 validation, v2-to-decision
  policy projection, section-labelled validation issues, source-fact rejection,
  future-field round-tripping, and the legacy-only write posture.
- Phase 05 compatibility validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests\contract -p "test_*.py"`,
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.decide.test_processing_decision`,
  `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests -p "test_*.py"`,
  and
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_app_config_contract`.
- Phase 05 generated-context checks passed after refreshing the new source
  summaries and regenerating the project index:
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`
  and
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`.
  `scripts/dev/check_godfiles.py` passed with the same 22 warning count as
  preflight after splitting the preset schema and migration adapter.
- Phase 05 postflight guardrail remained red in the same required categories
  as preflight: `summary-freshness` and `risky-file-registry`. Project index,
  pipeline map, lifecycle map, config schema, stage schema, active doc
  references, architecture guardrails, naming lint, god-file guard, and
  marketecture guard passed inside postflight.
- Phase 06 targeted validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_preset_policy_contract`
  and
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.decide.test_processing_decision`.
  It covers HandBrake-style Dimensions/Filters/Video/Audio/Subtitles/Container
  fields, data-supplied capability validation, video filters, downscale,
  subtitle burn-in, audio-only transcode without video encode, structured
  planned encode output, and existing copy/remux behavior.
- Phase 06 compatibility/generated-context validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests\contract -p "test_*.py"`,
  `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests -p "test_*.py"`,
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_app_config_contract`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_architecture_guardrails.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/lint-naming.py`, and
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_godfiles.py`.
  God-file warnings remained at the preflight baseline count of 22 after
  splitting Phase 06 section/action helpers.
- Phase 06 postflight guardrail remained red in the same required categories
  as preflight: `summary-freshness` and `risky-file-registry`. Project index,
  pipeline map, lifecycle map, config schema, stage schema, active doc
  references, architecture guardrails, naming lint, god-file guard, and
  marketecture guard passed inside postflight.
- Phase 07 preflight guardrail remained red before edits in the same required
  baseline categories: `summary-freshness` and `risky-file-registry`. Project
  index, pipeline map, lifecycle map, config schema, stage schema, active doc
  references, architecture guardrails, naming lint, god-file guard, and
  marketecture guard passed inside preflight.
- Phase 07 targeted validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.orchestration.test_pipeline_planner`
  and
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.decide.test_processing_decision`.
  It covers abstract dry-run COPY, REMUX, and ENCODE plans, ensures REMUX
  plans do not emit `encode_video`, verifies encode previews include
  dimensions/filters/video/audio/subtitles/container choices, and verifies
  `PresetV2` snapshots and deferred-publish strategy.
- Phase 07 compatibility/generated-context validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests\contract -p "test_*.py"`,
  `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests -p "test_*.py"`,
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_stage_entrypoint`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_architecture_guardrails.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/lint-naming.py`, and
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_godfiles.py`.
  God-file warnings remained at the preflight baseline count of 22.
- Phase 07 postflight guardrail remained red in the same required categories
  as preflight: `summary-freshness` and `risky-file-registry`. Project index,
  pipeline map, lifecycle map, config schema, stage schema, active doc
  references, architecture guardrails, naming lint, god-file guard, and
  marketecture guard passed inside postflight.
- Phase 07B preflight guardrail remained red before edits in the same required
  baseline categories: `summary-freshness` and `risky-file-registry`. Project
  index, pipeline map, lifecycle map, config schema, stage schema, active doc
  references, architecture guardrails, naming lint, god-file guard, and
  marketecture guard passed inside preflight.
- Phase 07B targeted validation passed:
  `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-PipelinePlanExecutorChecks.ps1`.
  The harness generated `pipeline_plan.v1` JSON for all 10 Phase 03
  source-media fixtures, validated strict plan rejection behavior, built
  dry-run FFmpeg/mkvmerge command records, verified REMUX/COPY plans do not
  invoke video encode, and verified ENCODE plans use `New-EncodeAttemptPlan`.
- Phase 07B focused compatibility checks passed:
  `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-MediaRouteSelectionChecks.ps1`,
  `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-AudioPolicyChecks.ps1`,
  `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-SubtitleBuilderDecisionChecks.ps1`,
  and
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.orchestration.test_pipeline_planner`.
- Phase 07B generated-context and guard checks passed:
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_architecture_guardrails.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/lint-naming.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_godfiles.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_pipeline_map.py --check`,
  and
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_lifecycle_map.py --check`.
  God-file warnings remained at the preflight baseline count of 22 after
  splitting the plan-executor validator into a helper file.
- Phase 07B broader reliability wrapper did not pass:
  `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1`
  failed in `Invoke-V6WebViewReliabilityChecks.ps1` with the pre-existing
  WebView/Tauri static-assets assertion: "Static WebView assets must be
  rendered through backend helpers while Tauri injects the token outside public
  index HTML." Phase 07B did not edit WebView/Tauri files.
- Phase 07B postflight guardrail remained red in the same required categories
  as preflight: `summary-freshness` and `risky-file-registry`. Project index,
  pipeline map, lifecycle map, config schema, stage schema, active doc
  references, architecture guardrails, naming lint, god-file guard, and
  marketecture guard passed inside postflight.
- Phase 08 targeted WebView static validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_webview_handbrake_settings_ui DesktopApp.tests.test_webview_settings_libraries`.
  It covers the HandBrake-style Settings tab order, source-fact separation,
  preview honesty copy, replacement display labels, rule badges, collapsed
  advanced encoder disclosure, metadata label overrides, and existing
  settings-library expectations.
- Phase 08 WebView asset and generated-context checks passed:
  `npm run webview:check`,
  `npm run webview:map:check`,
  `npm run webview:contract:check`,
  `npm run webview:dom-gaps:check`,
  `npm run webview:routes:check`,
  `npm run webview:slices:check`,
  `npm run webview:script-order:smoke`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_architecture_guardrails.py`,
  and
  `DesktopApp/Runtime/Python/python.exe scripts/lint-naming.py`.
- Phase 08 operator-surface smoke passed: the local API was started from
  `DesktopApp` on an ephemeral localhost port with an explicit test token, the
  in-app browser opened the Settings page, and the rendered UI showed the
  Phase 08 tab order, Decision Preview, `Predicted pending cutover`, legacy
  authority warning, planner-unavailable text, and collapsed advanced encoder
  disclosure. The temporary local API process was stopped.
- Phase 08 refreshed generated WebView/project artifacts after the Settings
  UI edits:
  `Docs/generated/WEBVIEW_GODFILE_SPLIT_MAP.md`,
  `Docs/generated/WEBVIEW_PUBLIC_CONTRACT_BASELINE.json`,
  `Docs/generated/WEBVIEW_DOM_ID_GAP_REPORT.json`,
  `Docs/generated/WEBVIEW_SPLIT_CANDIDATES.json`,
  `Docs/generated/PROJECT_INDEX.md`, and
  `Docs/generated/DEPENDENCY_GRAPH.md`.
- Phase 08 broader WebView/static batches remain red from baseline drift that
  was outside the Settings rewrite scope. The combined static unittest batch
  failed on unrelated assertions in Rename/Tauri/static helper contracts and
  pre-existing CSS token violations in `styles.rename.css`. The repo
  `npm run webview:prework:check` and `npm run webview:lint:budget:check`
  fail at the existing lint budget gate with `warnings increased: 653 > 651`
  and `no-undef warnings increased: 392 > 390`. Direct ESLint over the Phase
  08 modified JavaScript files exits with warnings only and no errors.
- Phase 08 summary freshness check remained red from the existing summary
  baseline: `DesktopApp/Runtime/Python/python.exe scripts/dev/refresh_summaries.py --check`
  reported one missing summary, one stale summary, and existing WebView
  summary orphan records. Phase 08 refreshed the touched generated summaries
  and regenerated the project index, but did not prune the baseline orphan set.
- Phase 08 acceptance limitation at Phase 08 completion: Settings still had no backend Local API
  route that accepts a selected `SourceMediaInfo` payload and returns a
  `pipeline_plan.v1` preview. The UI therefore does not duplicate routing
  logic in JavaScript and keeps the Decision Preview at `UNKNOWN` /
  `Predicted pending cutover` with explicit text that backend planner preview
  is unavailable from the Settings workspace.
- Phase 08.5 baseline cleanup validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_api_static_files_policy DesktopApp.tests.test_application_facade_web_static DesktopApp.tests.test_webview_navigation_static DesktopApp.tests.test_webview_frontend_mutation_boundary DesktopApp.tests.test_webview_css_design_tokens`,
  `npm run webview:prework:check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/refresh_summaries.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`,
  and
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`.
  The cleanup restored missing read-only Rename DOM containers, fixed
  `styles.rename.css` token violations, kept the ESLint warning budget at
  `651/651`, brought WebView summaries into the refresh script's intended
  check scope, and refreshed stale/missing summaries without loosening the
  checks.
- Phase 09 backend route validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_api_command_contracts DesktopApp.tests.test_settings_pipeline_plan_preview`.
  It covers valid `SourceMediaInfo` payloads, malformed source rejection,
  unknown request-key rejection, `effect: none` route contract, local API
  `desktop_command_result.v1` response wrapping, embedded `pipeline_plan.v1`,
  `dryRunOnly`, `canExecute: false`, no settings save, REMUX baseline, and a
  staged patch changing the preview to ENCODE without saving.
- Phase 09 planner integration validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.orchestration.test_pipeline_planner tests.decide.test_processing_decision tests.contract.test_source_media_contract`.
  It preserves existing COPY, REMUX, and ENCODE abstract plan coverage plus
  source-media contract coverage.
- Phase 09 WebView/static validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_api_static_files_policy DesktopApp.tests.test_application_facade_web_static DesktopApp.tests.test_webview_navigation_static DesktopApp.tests.test_webview_frontend_mutation_boundary DesktopApp.tests.test_webview_css_design_tokens DesktopApp.tests.test_webview_handbrake_settings_ui DesktopApp.tests.test_api_command_contracts DesktopApp.tests.test_settings_pipeline_plan_preview`
  and `npm run webview:prework:check`.
  The Settings preview route is allowlisted as non-mutating, the UI calls only
  `/api/settings/pipeline-plan-preview` for plan preview, and the Decision
  Preview remains labelled `Predicted pending cutover`.
- Phase 09 generated-context validation passed:
  `DesktopApp/Runtime/Python/python.exe scripts/dev/refresh_summaries.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`,
  and
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`.
- Phase 09 operator-surface proof passed: the token-protected local API was
  started from `DesktopApp` on `http://127.0.0.1:16701`, Chrome headless CDP
  opened the Settings WebView, selected Source / Compatibility, loaded the
  `tv_h264_1080p_12mbps_mkv` `SourceMediaInfo` fixture, staged
  `H264RemuxMaxHeight: 720`, clicked Preview Plan, and rendered `ENCODE`,
  `Preview ready`, stream actions, command preview lines, `Dry run only: yes`,
  and `Predicted pending cutover`. The temporary local API and browser
  processes were stopped.
- Phase 09 verification/publish addendum preflight guardrail remained red
  before edits because `scripts/dev/check_risky_file_registry.py` still
  references removed legacy paths. Summary freshness, project index, pipeline
  map, lifecycle map, config schema, stage schema, active doc references,
  architecture guardrails, naming lint, god-file guard, and marketecture guard
  passed inside preflight.
- Phase 09 verification/publish addendum targeted validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_verification_contract tests.contract.test_preset_policy_contract tests.decide.test_processing_decision tests.orchestration.test_pipeline_planner DesktopApp.tests.test_settings_pipeline_plan_preview DesktopApp.tests.test_webview_handbrake_settings_ui DesktopApp.tests.test_service_config_option_policy`.
  It covers explicit Output Size Check actions, advisory-warning versus
  publish-blocker versus failure result separation, dry-run plan
  verification/publish fields, Settings preview API output, and Settings UI
  terminology.
- Phase 09 verification/publish addendum dry-run executor compatibility passed:
  `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-PipelinePlanExecutorChecks.ps1`.
- Phase 09 verification/publish addendum WebView/static validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_api_static_files_policy DesktopApp.tests.test_application_facade_web_static DesktopApp.tests.test_webview_navigation_static DesktopApp.tests.test_webview_frontend_mutation_boundary DesktopApp.tests.test_webview_css_design_tokens DesktopApp.tests.test_webview_handbrake_settings_ui DesktopApp.tests.test_settings_pipeline_plan_preview DesktopApp.tests.test_webview_browser_completed_pending_proof_smoke DesktopApp.tests.test_webview_real_media_smoke`,
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_settings_risk_policy_rules DesktopApp.tests.test_sample_validation_api DesktopApp.tests.test_webview_settings_live_smoke`,
  `npm run webview:prework:check`,
  `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File SmokeTests/Test-WebViewSettingsLaunchPolicySmoke.ps1`,
  and
  `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File SmokeTests/Test-WebViewSettingsLaunchLiveConfigSmoke.ps1`.
  Generated WebView split-map, public-contract, and split-candidate artifacts
  were refreshed to match the terminology/preview changes.
- Phase 09 verification/publish addendum generated-context validation passed:
  `DesktopApp/Runtime/Python/python.exe scripts/dev/refresh_summaries.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`,
  and
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`.
- Phase 09 verification/publish addendum postflight guardrail remained red
  only because `scripts/dev/check_risky_file_registry.py` still references
  removed legacy paths. Summary freshness, project index, pipeline map,
  lifecycle map, config schema, stage schema, active doc references,
  architecture guardrails, naming lint, god-file guard, and marketecture guard
  passed inside postflight.
- Phase 10 preflight guardrail remained red before edits only because
  `scripts/dev/check_risky_file_registry.py` still references removed legacy
  paths. Summary freshness, project index, pipeline map, lifecycle map, config
  schema, stage schema, active doc references, architecture guardrails, naming
  lint, god-file guard, and marketecture guard passed inside preflight.
- Phase 10 targeted integration validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.integration.test_handbrake_remux_regression_matrix`.
  It covers the Phase 10 copy/remux/encode route matrix, metadata-only
  container/source factories, legacy-to-v2 parity, v2 preset to plan preview,
  Output Size Check warn/block/fail separation, and unprobeable-source reject
  behavior.
- Phase 10 focused compatibility validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_source_media_contract tests.contract.test_preset_policy_contract tests.contract.test_verification_contract tests.decide.test_processing_decision tests.orchestration.test_pipeline_planner tests.integration.test_handbrake_remux_regression_matrix`,
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_settings_pipeline_plan_preview DesktopApp.tests.test_webview_handbrake_settings_ui DesktopApp.tests.test_webview_frontend_mutation_boundary`,
  and
  `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-PipelinePlanExecutorChecks.ps1`.
- Phase 10 generated-context validation passed after refreshing summaries and
  regenerating the project index:
  `DesktopApp/Runtime/Python/python.exe scripts/dev/refresh_summaries.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`,
  and
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`.
- Phase 10 postflight guardrail remained red only because
  `scripts/dev/check_risky_file_registry.py` still references removed legacy
  paths. Summary freshness, project index, pipeline map, lifecycle map, config
  schema, stage schema, active doc references, architecture guardrails, naming
  lint, god-file guard, and marketecture guard passed inside postflight.
- Phase 11 preflight guardrail remained red before edits only because
  `scripts/dev/check_risky_file_registry.py` still references removed legacy
  paths. Summary freshness, project index, pipeline map, lifecycle map, config
  schema, stage schema, active doc references, architecture guardrails, naming
  lint, god-file guard, and marketecture guard passed inside preflight; no
  changed paths matched the risky-file registry.
- Phase 11 targeted validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_rollout_policy`
  and
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_settings_pipeline_plan_preview`.
  It covers default legacy authority, shadow comparison without execution,
  two-key cutover state resolution, disabled/enabled planner comparison
  records, Settings preview rollout payloads, and no config save.
- Phase 11 focused compatibility validation passed:
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_rollout_policy tests.contract.test_preset_policy_contract tests.contract.test_source_media_contract tests.contract.test_verification_contract`,
  `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_settings_pipeline_plan_preview DesktopApp.tests.test_webview_frontend_mutation_boundary`,
  and
  `DesktopApp/Runtime/Python/python.exe -m unittest tests.integration.test_handbrake_remux_regression_matrix tests.orchestration.test_pipeline_planner`.
- Phase 11 generated-context and guard checks passed:
  `DesktopApp/Runtime/Python/python.exe scripts/dev/refresh_summaries.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_architecture_guardrails.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/lint-naming.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_godfiles.py`, and
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_marketecture.py`.
- Phase 11 postflight guardrail remained red only because
  `scripts/dev/check_risky_file_registry.py` still references removed legacy
  paths. Summary freshness, project index, pipeline map, lifecycle map, config
  schema, stage schema, active doc references, architecture guardrails, naming
  lint, god-file guard, and marketecture guard passed inside postflight; no
  changed paths matched the risky-file registry.
- Phase 12 preflight guardrail remained red before docs edits only because
  `scripts/dev/check_risky_file_registry.py` still references removed legacy
  paths. Summary freshness, project index, pipeline map, lifecycle map, config
  schema, stage schema, active doc references, architecture guardrails, naming
  lint, god-file guard, and marketecture guard passed inside preflight.
- Phase 12 docs-only validation passed:
  `DesktopApp/Runtime/Python/python.exe scripts/dev/refresh_summaries.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_architecture_guardrails.py`,
  `DesktopApp/Runtime/Python/python.exe scripts/lint-naming.py`, and
  `DesktopApp/Runtime/Python/python.exe scripts/dev/check_marketecture.py`.
- Phase 12 postflight guardrail remained red only because
  `scripts/dev/check_risky_file_registry.py` still references removed legacy
  paths. Summary freshness, project index, pipeline map, lifecycle map, config
  schema, stage schema, active doc references, architecture guardrails, naming
  lint, god-file guard, and marketecture guard passed inside postflight; no
  Phase 12 changed path matched the risky-file registry.

## Known Baseline Issues Observed During Phase 01

- `Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md` was absent in the current checkout; operator clarified on 2026-05-30 that the architecture overhaul plan has been deleted.
- `SESSION.md` was not present as an active root tracker; operator confirmed on 2026-05-30 that the approved subtree tracker is sufficient.
- Audit path mismatch resolved on 2026-05-30: `Docs/audits/latest.md` is the canonical audit path for this rewrite; the singular `Docs/audit/latest.md` path should not be used.
- `scripts/dev/ai_guardrail.py preflight --json` reported stale/missing summary and risky-file-registry entries before this phase wrote any files.
- The git worktree already contained many modified files and untracked route-selection test files before Phase 01 began.
- The untracked route-selection test file was verified on 2026-05-30: it is referenced by the modified reliability suite, has no prior git history at that path, targets `engine/decide/routing.ps1`, and passes when run directly.

## Operator Decisions Recorded On 2026-05-30 And 2026-05-31

- Missing architecture plan: do not restore; the architecture overhaul plan has been deleted.
- Active session tracker: no root `SESSION.md`; the approved subtree tracker is sufficient.
- Audit path: use `Docs/audits/latest.md`.
- Route fallback model for future Option A work: remux codec fallback and CPU fallback should be modeled in Python.
- Phase 02 display vocabulary accepted by operator reply on 2026-05-30:
  use `Processing Strategy` for the future `RoutingProfile` display label;
  `Playback Goal` may be explanatory/help copy only.
- Phase 02 threshold semantics accepted by operator reply on 2026-05-30:
  keep `EncodeThresholdGB` and `TVEncodeThresholdGB` as route source-size
  limits. Do not display them as target output sizes unless a later phase
  changes the behavior and adds true target fields.
- Phase 02 config compatibility accepted by operator reply on 2026-05-30:
  keep old JSON/PSD1 keys as compatibility keys through the rewrite. Phase 05
  may add v2 aliases only if needed.
- Phase 02 codec-default direction accepted by operator reply on 2026-05-30:
  keep `hevc_nvenc` as the current default. Phase 06 may make codec choice
  preset-driven after the encoding model and tests define preset semantics.
- Phase 04 parity-gate direction accepted by operator reply on 2026-05-30:
  before Python decisions can replace `Resolve-InitialMediaRoutePlan` in
  production, a golden parity harness must show zero unexplained divergences
  across the route matrix, any intentional divergences must be documented and
  operator-approved, shadow-mode comparison must report no unresolved
  divergences, and representative real-media validation must be rerun for the
  touched media-policy surface.
- Phase 05 schema direction accepted by operator reply on 2026-05-30: add a
  versioned `PresetV2` wrapper for persisted/user-facing policy, but keep
  `EffectiveDecisionPolicy` as the computed adapter target consumed by
  `ProcessingDecision`. The intended flow is legacy config or `PresetV2` to
  `EffectiveDecisionPolicy` to `ProcessingDecision`; do not store
  `EffectiveDecisionPolicy` as the preset schema.
- Phase 06 target-mode review accepted by operator reply on 2026-05-30:
  support `auto`, `constant_quality`, `average_bitrate`, and `max_bitrate`.
- Phase 06 preset/tune review accepted by operator reply on 2026-05-30:
  presets should control speed/compression effort and encoder family/backend
  choices, including NVENC `p1`-`p7` and x264 versus x265 selection; `tune`
  remains a separate content/behavior tune.
- Phase 06 advanced-control review accepted by operator reply on 2026-05-30:
  advanced controls should stay hidden by default in the Phase 08 UI,
  including framerate mode, profile, level, tune, custom crop, pixel aspect,
  colorspace, raw legacy flags, CPU fallback settings, process
  priority/thread caps, muxer flags, and tool timeouts.
- Phase 08 proceed direction accepted by operator request on 2026-05-30:
  perform only Phase 08, do not implement future phases, do not commit or
  push, and keep changes within the approved docs/tracker location and the
  Phase 08 edit domain.
- Phase 08.5 + Phase 09 proceed direction accepted by operator request on
  2026-05-30: clean up the WebView validation baseline before adding the
  backend-owned Settings `PipelinePlan` preview route; include explicit
  `SourceMediaInfo` JSON as the first source-selection payload; keep the route
  read-only and dry-run only; do not commit or push.
- Phase 09 verification/publish proceed direction accepted by operator request
  on 2026-05-30: perform only the downloaded Phase 09 verification, Output
  Size Check, and publish-gate phase; confirm docs location, edit domain, and
  high-risk posture before editing; do not commit or push.
- Phase 10 proceed direction accepted by operator request on 2026-05-30:
  perform only Phase 10 using the downloaded Phase 10 test-matrix file;
  confirm docs location, edit domain, and high-risk posture before editing;
  do not commit or push.
- Phase 11 proceed direction accepted by operator request on 2026-05-31:
  perform only the downloaded Phase 11 rollout/backcompat/feature-flag phase;
  confirm docs location, edit domain, and high-risk posture before editing;
  do not implement future phases; do not commit or push.
- Phase 12 proceed direction accepted by operator request on 2026-05-31:
  perform only the downloaded final docs/operator guide/cleanup phase; confirm
  docs location, edit domain, and high-risk posture before editing; do not
  implement future phases; do not commit or push.

## Next Phase Gate

Phase 12 final documentation is complete in the approved rewrite subtree. The
operator guide, developer guide, migration/rollback/cleanup plan, and final
acceptance doc describe the dry-run preview model, contract boundaries, current
legacy execution authority, cleanup candidates, and cutover limits.

Runtime route replacement must not begin until the accepted parity gate above
is satisfied with zero unexplained divergences, operator-approved intentional
differences, live old/new shadow evidence, Phase 07B concrete command parity,
and representative real-media validation for the touched media-policy surface.
V2 config persistence, production default flips, and any mutation controls
should wait for a separate operator-approved high-risk cutover phase.

No automatic next rewrite phase is ready. Future cutover or cleanup work must
be separately scoped and operator-approved.
