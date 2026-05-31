# Phase 10 End-to-End Test Matrix and Regression Fixtures

Date: 2026-05-30

Scope: additive regression-matrix tests and documentation for the
HandBrake/remux rewrite. This phase does not change production PowerShell
execution, FFmpeg command generation, subtitle/audio execution, settings
persistence, queue behavior, publish/drain behavior, source/scratch/output
movement, cleanup, command journal behavior, or Tauri lifecycle behavior.

## Phase Confirmations

- Approved docs and tracker location: `Docs/rewrite/handbrake-remux/`
- Edit domain for this phase: Python tests under `tests/`, generated
  summaries/project index context, and this approved rewrite docs/tracker
  subtree
- High-risk areas touched: yes, through tests and documentation only. The
  matrix exercises routing, settings/preset compatibility, verification,
  Output Size Check, and publish-gate modeling without changing runtime media
  policy or mutation behavior.

## Inputs Read

- `AGENTS.md`
- `Docs/CURRENT_PROJECT_STATE.md`
- `OPEN_WORK_CHECKLIST.md`
- `Docs/generated/PROJECT_INDEX.md`
- `Docs/audits/latest.md`
- `Docs/rewrite/handbrake-remux/00_execution_tracker.md`
- `Docs/rewrite/handbrake-remux/01_repo_audit.md` through
  `Docs/rewrite/handbrake-remux/09_verification_publish_plan.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/10_END_TO_END_TEST_MATRIX.md`

## Automated Coverage Added

New tests:

- `tests/integration/__init__.py`
- `tests/integration/test_handbrake_remux_regression_matrix.py`

The new integration tests use metadata JSON fixtures and in-test factories
only. They do not require large video files, external downloads, FFmpeg runs,
or real encode/remux jobs.

Coverage added:

- source metadata fixture/factory to Python decision engine to dry-run
  `pipeline_plan.v1`
- legacy flat config to `PresetV2` to effective policy to decision parity
- `PresetV2` to decision to dry-run plan
- Output Size Check warn/block/fail result separation
- unprobeable source rejection without publish

## Regression Matrix

| Case | Automated coverage | Assertion status |
| --- | --- | --- |
| TV under bitrate cap | `test_route_matrix_preserves_copy_remux_encode_regression_cases` using `tv_h264_1080p_12mbps_mkv.json` | Video stays copy; route is COPY or REMUX; no `encode_video` step |
| TV over bitrate cap | same test using `tv_h264_1080p_24mbps_mkv.json` | ENCODE with `VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP` |
| Movie under bitrate cap | same test using `movie_h264_1080p_30mbps_mkv.json` | Video stays copy; route is COPY or REMUX |
| Movie over bitrate cap | same test using `movie_h264_1080p_45mbps_mkv.json` | ENCODE with bitrate-over reason |
| Incompatible codec | same test using `avi_mpeg2_480p.json` | ENCODE with `SOURCE_CODEC_INCOMPATIBLE` |
| Container only | same test using an MP4 source factory from metadata | REMUX, video copy, no video encode |
| Filter enabled | same test with `video_filter_names=["deinterlace"]` | ENCODE with `FILTERS_ENABLED_ENCODE_REQUIRED` |
| Resolution over cap | same test with 4K fixture and `resolution_limit="1080p"` | ENCODE with output height 1080 |
| Audio incompatible | same test using `multi_audio_tracks.json` and MP4 output | Video copy plus audio transcode |
| Subtitle burn-in | same test with forced subtitle burn-in | ENCODE with subtitle burn action |
| Size warn | `test_output_size_check_matrix_separates_warn_block_and_fail` | Advisory warning only; no failure or publish blocker |
| Size block | same test | Publish blocker only; no job failure |
| Missing bitrate | route matrix test using `unknown_bitrate_source.json` | No crash; `MISSING_BITRATE_METADATA` advisory visible |
| Unknown media type | same fixture | `MEDIA_TYPE_UNKNOWN_CONSERVATIVE_CAP` advisory visible |
| Audio-only incompatibility | route matrix test using `multi_audio_tracks.json` | No video encode; per-stream audio actions correct |
| Container x subtitle | route matrix test using image subtitles and MP4 output | Subtitle incompatibility and burn-in reasons visible |
| Unprobeable source | `test_unprobeable_source_rejects_without_publish_plan` | REJECT with `NO_PUBLISH_FOR_REJECTED_SOURCE` |

## Existing Coverage Reused

| Layer | Existing test coverage |
| --- | --- |
| Source media normalization | `tests.contract.test_source_media_contract` |
| Schema validation and migration | `tests.contract.test_preset_policy_contract` |
| Decision engine route results | `tests.decide.test_processing_decision` |
| Guard evaluation | `tests.contract.test_verification_contract` |
| Command plan generation | `tests.orchestration.test_pipeline_planner` and `Pipeline/Tests/Unit/Invoke-PipelinePlanExecutorChecks.ps1` |
| Planner preview API | `DesktopApp.tests.test_settings_pipeline_plan_preview` |
| UI render/static labels | `DesktopApp.tests.test_webview_handbrake_settings_ui` |
| UI mutation boundary | `DesktopApp.tests.test_webview_frontend_mutation_boundary` |

## Manual or Deferred Coverage

- Optional real-media smokes remain manual/operator-run. Normal CI should not
  run long encodes or require external media downloads.
- Production route replacement, PowerShell executor cutover, real publish
  `block_publish` behavior, and real pending-publish drain behavior remain
  deferred to later operator-approved rollout work.
- Representative real-media validation must be rerun before any future change
  that alters FFmpeg/media-policy, subtitle/audio behavior, publish/drain,
  source/scratch/output movement, or cleanup behavior.

## CI and Validation Command List

Targeted Phase 10 checks:

```powershell
.\DesktopApp\Runtime\Python\python.exe -m unittest tests.integration.test_handbrake_remux_regression_matrix
.\DesktopApp\Runtime\Python\python.exe -m unittest tests.contract.test_source_media_contract tests.contract.test_preset_policy_contract tests.contract.test_verification_contract tests.decide.test_processing_decision tests.orchestration.test_pipeline_planner tests.integration.test_handbrake_remux_regression_matrix
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_settings_pipeline_plan_preview DesktopApp.tests.test_webview_handbrake_settings_ui DesktopApp.tests.test_webview_frontend_mutation_boundary
Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline\Tests\Unit\Invoke-PipelinePlanExecutorChecks.ps1
.\DesktopApp\Runtime\Python\python.exe scripts\dev\refresh_summaries.py --check
.\DesktopApp\Runtime\Python\python.exe scripts\dev\generate_project_index.py --check
.\DesktopApp\Runtime\Python\python.exe scripts\dev\check_active_doc_references.py
```

Broader release confidence before cutover remains governed by
`Docs/testing/VALIDATION_LADDER_RUNBOOK.md` and the operator-run real-media
validation gate.

## Acceptance Notes

- The Phase 10 matrix is represented in automated metadata-only tests or
  explicitly documented as manual/deferred.
- Legacy and v2 policy paths both feed the same decision/plan shape.
- UI coverage remains static/read-only and does not duplicate backend routing
  logic.
- No changed behavior is blessed for production execution; the rewrite remains
  dry-run/reporting-only until a later rollout phase.
