# Test Coverage Review

## Tests Run During This Review

Passed:

- `ops/pipeline/tests/Unit/Invoke-SubtitleBuilderDecisionChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-SubtitleOcrPathResolutionChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-VobSubSubtitleChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-SidecarWriteSafetyChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-ContractSchemaChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1`
- `apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_subtitle_qa_feature -q`
- `PYTHONPATH=src apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_service_config_validation tests.python.desktop.test_metadata_contract -q`
- `PYTHONPATH=src apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_application_facade_web_static -q`
- `PYTHONPATH=src apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_telemetry_service -q`
- `PYTHONPATH=src apps/desktop/runtime/Python/python.exe -m pytest tests/python/core/subtitles/test_ass_to_srt_helpers.py -q`

Did not reach assertions:

- `ops/pipeline/tests/Unit/Invoke-SrtValidationChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-FileOverrideSubtitleBurnChecks.ps1`

Reason: both resolved repo paths under `ops\ops\...` when invoked from the repo root.

## Covered Behaviors

ASS/SSA:

- Python helper public surface.
- Text cleanup and rendering.
- Style whitelist/exclude behavior.
- Overlap splitting/merge and minimum gaps.
- Encoding selection and high-risk fallback decode review routing.

SRT:

- Runtime SRT validation exists and is used by conversion and sidecar writes.
- `Invoke-SrtValidationChecks.ps1` is intended to cover valid SRT, embedded blank lines, empty-cue tolerance, all-empty rejection, and invalid timing, but the harness failed before assertions in this run.

TX3G:

- Builder decisions preserve source/conversion provenance for generated sidecars.
- Sidecar plan/publish safety and rollback are covered.
- Existing-output TX3G sidecar export path is represented in legacy/static checks.

BDPGS:

- OCR promoted path resolution is covered.
- Builder decisions cover BDPGS conversion and unsupported-container review routing.
- Config validation rejects BDPGS OCR enabled without a tool path.

VobSub:

- Detection, language mapping, sidecar pair discovery, ambiguous embedded track mapping, OCR success, unknown language, missing tessdata, unsupported tool, and missing pair failures are covered.
- Config registry and metadata tests cover VobSub keys and UI metadata.

Publish/sidecar safety:

- Sidecar write fallback, publish sidecar rollback, pending park, pending drain, schema round-trip, and pending trust checks are covered.

QA/review routing:

- Completed QA passes non-empty SRT cue evidence.
- Completed QA reviews image subtitles without OCR/conversion evidence.
- Completed QA blocks explicit image-subtitle OCR failure.
- Local API subtitle QA routes/contracts are covered.

## Gaps

1. MP4 one-sidecar reduction is asserted as expected behavior, not guarded as subtitle-loss risk.

   The builder test confirms MP4 compatibility returns exactly one converted SRT sidecar and reports dropped candidate count. It does not require durable per-track dropped evidence or review routing for non-selected converted candidates.

2. No real-media OCR validation was run.

   BDPGS and VobSub tests use fakes/stubs. They cover control flow and failure routing but not real PGS/VobSub OCR output quality, sync, forced/default behavior, or renderer compatibility.

3. `Invoke-SrtValidationChecks.ps1` did not execute.

   This leaves the direct PowerShell SRT validator regression suite unverified in this review run.

4. `Invoke-FileOverrideSubtitleBurnChecks.ps1` did not execute.

   This leaves the explicit burn-selected/drop-selectable-subtitles contract unverified in this review run.

5. Completed-job schema coverage lags runtime VobSub metadata.

   Contract tests prove pending manifests carry VobSub fields, but the completed-job schema does not enumerate VobSub arrays.

6. ASS blank-language override edge case lacks a targeted test.

   There is no observed test proving blank ASS language behaves the same as `und` when `AssKeepLanguages` or `SubKeepLanguages` has been customized.

7. Supplemental keyword wildcard behavior lacks a targeted test.

   There is no test for custom supplemental/SDH keywords containing PowerShell wildcard characters.

## Recommended Coverage Additions

- Add a high-severity MP4 compatibility test that fails if non-selected converted SRT candidates are not durably recorded as dropped/review evidence.
- Add completed-job schema assertions for `vobsub_srt_failures` and `vobsub_embedded_srt_tracks`.
- Fix the repo-root calculation in the SRT validation and subtitle-burn PowerShell tests.
- Add ASS blank-language policy tests for `SubKeepLanguages=@('und')` and `AssKeepLanguages=@('und')`.
- Add language-specific real-media sample validation for BDPGS and VobSub OCR.
- Add publish-sidecar tests for multiple converted SRT candidates across ASS/TX3G/BDPGS/VobSub in MP4 mode.
