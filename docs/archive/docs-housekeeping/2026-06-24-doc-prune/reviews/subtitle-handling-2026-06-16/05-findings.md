# Findings

## F-001 High: MP4 compatibility can publish after dropping non-selected converted subtitles

`Build-SubtitleArgsForFFmpeg` converts routed ASS/TX3G/BDPGS/VobSub tracks, then MP4 compatibility mode selects one converted SRT sidecar and returns only that selected track. Non-selected converted candidates are logged and represented by a count, but not returned as durable per-track failures or review records.

Impact:

- A final MP4 can publish successfully with only one external SRT even when multiple retained subtitle tracks were converted.
- Forced, SDH, supplemental, or secondary preferred-language subtitles may be absent from the final artifact.
- The issue is not a conversion failure, so the existing conversion-failure gates do not block publish.

Evidence:

- `ops/pipeline/engine/subtitles/builders.ps1`: MP4 compatibility sidecar selection and `DroppedEmbeddedTrackCount`.
- `ops/pipeline/tests/Unit/Invoke-SubtitleBuilderDecisionChecks.ps1`: asserts exactly one converted SRT sidecar and dropped candidate count.
- `ops/pipeline/engine/publish/publish_completion.ps1`: sidecar metadata carries selected converted SRT track arrays, not full dropped-candidate detail.

Recommended fix:

- Treat each non-selected converted SRT candidate in MP4 compatibility mode as either:
  - a durable review-routed dropped-subtitle record with source kind, codec, language, forced/SDH/supplemental flags, and reason, or
  - a published sidecar with collision-safe naming if multi-sidecar MP4 policy is accepted.
- Block publish when retained forced/SDH/supplemental subtitles would be reduced to a single sidecar without explicit operator override.

## F-002 Medium: Completed-job schema omits VobSub subtitle evidence fields

Runtime sidecars require/write VobSub arrays, and pending manifests require/write VobSub arrays, but `media_pipeline_completed_job.schema.json` does not enumerate VobSub completed fields.

Impact:

- Schema-based consumers can miss VobSub evidence without validation failure.
- Future refactors can accidentally drop VobSub completed evidence while contract tests still pass.

Evidence:

- `ops/pipeline/config/schemas/media_pipeline_completed_job.schema.json`: lists TX3G/BDPGS fields but not VobSub fields.
- `ops/pipeline/engine/publish/sidecar.ps1`: validates required arrays including `vobsub_srt_failures` and `vobsub_embedded_srt_tracks`.
- `ops/pipeline/config/schemas/media_pipeline_pending_push_manifest.schema.json`: includes VobSub arrays.

Recommended fix:

- Add VobSub fields to the completed-job schema.
- Add contract tests asserting completed-job schema enumerates every subtitle array that sidecar round-trip validation requires.

## F-003 Medium: Blank ASS language can be filtered differently than blank TX3G/BDPGS/VobSub language

Blank TX3G, BDPGS, and VobSub language values are normalized to `und`, but blank ASS language values remain `""`. Defaults keep both `und` and `""`, so default behavior is safe. Custom language policy can make blank ASS drop while blank bitmap/TX3G tracks retain.

Impact:

- Config/profile overrides can silently drop blank-language ASS/SSA subtitles even when the operator intended `und` to keep undefined subtitles.

Evidence:

- `ops/pipeline/engine/subtitles/routing_decisions.ps1`: normalizes language only for TX3G/BDPGS/VobSub.
- `ops/pipeline/engine/subtitles/language_policy.ps1`: `Get-NormalizedSubtitleLanguage` maps blank to `und`.
- `ops/pipeline/engine/config/default_values.ps1`: default `SubKeepLanguages` includes both `und` and `""`.

Recommended fix:

- Normalize ASS language through `Get-NormalizedSubtitleLanguage` too, while preserving raw language separately for diagnostics if needed.
- Add tests for `AssKeepLanguages=@('und')` and blank ASS language tags.

## F-004 Medium: Two targeted subtitle tests fail before assertions

Two PowerShell tests failed because their repo-root calculation resolves paths under `ops\ops\...`.

Affected tests:

- `ops/pipeline/tests/Unit/Invoke-SrtValidationChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-FileOverrideSubtitleBurnChecks.ps1`

Impact:

- Direct SRT validation regressions and subtitle burn/drop override regressions are not covered by these tests in their current invocation shape.

Recommended fix:

- Correct repo-root resolution in both scripts.
- Run them from repo root and from their own directory to prevent recurrence.

## F-005 Low: Supplemental and SDH keyword matching uses wildcard semantics

`Test-SubtitleTitleMatchesAnyKeyword` uses `-like "*$kw*"`. Default keywords are simple, but custom keyword entries containing wildcard characters can overmatch.

Impact:

- Misconfigured keywords can classify unrelated tracks as SDH/supplemental/forced.
- Risk is operator-config dependent.

Evidence:

- `ops/pipeline/engine/subtitles/language_policy.ps1`: `Test-SubtitleTitleMatchesAnyKeyword`.

Recommended fix:

- Escape custom keyword patterns or switch to case-insensitive literal substring matching.
- Add tests for keywords containing `?`, `[`, `]`, and `*`.

## Non-Findings

- Subtitle probe failure does not silently continue; encode/remux abort.
- ASS/TX3G/BDPGS/VobSub conversion failures do not silently publish; encode/remux abort.
- BDPGS/VobSub unknown OCR language does not default to English; it fails closed.
- Missing BDPGS/VobSub OCR tools/tessdata/tesseract route to failure records.
- External VobSub sidecars with conversion disabled route to review rather than being marked preserved.
- Immediate and pending sidecar publish failures block final reveal and roll back sidecar state.
- Completed subtitle QA is read-only and blocks/reviews failed or incomplete image-subtitle OCR evidence.
