# Risk Review

## High Risk

### R-001: MP4 compatibility collapses multiple converted subtitle candidates to one sidecar

`Build-SubtitleArgsForFFmpeg` intentionally collects converted ASS/TX3G/BDPGS/VobSub SRT candidates, selects one preferred/default candidate for MP4 compatibility, and returns only that selected converted sidecar track. The other converted candidates are logged as skipped/dropped and summarized by count, but they are not returned as durable review failures or full dropped-track evidence.

Why this matters: if multiple preferred-language, forced, SDH, or supplemental subtitle tracks were retained and converted, the final MP4 publish can expose only one SRT sidecar while non-selected subtitle content is absent from the published artifact. This is not a conversion failure, so encode/publish can succeed. Under the review rule, this is a high-severity silent subtitle loss / bad publish risk.

Key evidence:

- `ops/pipeline/engine/subtitles/builders.ps1`: MP4 compatibility selection and dropped count.
- `ops/pipeline/tests/Unit/Invoke-SubtitleBuilderDecisionChecks.ps1`: tests currently assert the one-sidecar reduction.
- `ops/pipeline/engine/publish/publish_completion.ps1`: sidecar evidence carries selected tracks, not every non-selected converted candidate.

### R-002: Runtime sidecar metadata is stronger than the completed-job schema for VobSub

Runtime sidecars and pending manifests include VobSub evidence arrays, but `media_pipeline_completed_job.schema.json` enumerates only TX3G and BDPGS subtitle fields and omits VobSub completed fields. `additionalProperties=true` means runtime records can still contain those fields, but schema-based consumers are not forced to notice if VobSub evidence is missing.

Why this matters: VobSub OCR is high risk and can produce missing or bad text if evidence is dropped by downstream tooling. A stale schema lowers validation strength and can hide contract drift.

Key evidence:

- `ops/pipeline/config/schemas/media_pipeline_completed_job.schema.json`
- `ops/pipeline/engine/publish/sidecar.ps1`
- `ops/pipeline/config/schemas/media_pipeline_pending_push_manifest.schema.json`
- `ops/pipeline/tests/Unit/Invoke-ContractSchemaChecks.ps1`

## Medium Risk

### R-003: ASS blank-language handling is inconsistent with bitmap/TX3G language normalization

Blank TX3G, BDPGS, and VobSub language tags normalize to `und`; non-image/non-TX3G ASS uses the raw lower-case tag, so blank ASS remains `""`. Defaults include both `und` and `""`, so default behavior is safe. However, a library/profile override that keeps `und` but removes blank can retain blank bitmap/TX3G subtitles while dropping blank ASS subtitles.

Why this matters: this is a configuration-dependent silent-drop risk for ASS/SSA tracks that have no language tag.

Key evidence:

- `ops/pipeline/engine/subtitles/routing_decisions.ps1`
- `ops/pipeline/engine/subtitles/language_policy.ps1`
- `ops/pipeline/engine/config/default_values.ps1`

### R-004: Two targeted subtitle tests currently fail before their assertions

`Invoke-SrtValidationChecks.ps1` and `Invoke-FileOverrideSubtitleBurnChecks.ps1` failed in this review because their repo-root calculation resolved paths under `ops\ops\...`. The underlying runtime code may still be covered elsewhere, but these two explicit subtitle guard checks are currently ineffective when invoked from the repo root.

Why this matters: SRT validation and subtitle burn/drop behavior are high-impact areas, so dead test harnesses weaken confidence.

Observed failures:

- `Invoke-SrtValidationChecks.ps1` looked for `ops\ops\pipeline\engine\subtitles\srt.ps1`.
- `Invoke-FileOverrideSubtitleBurnChecks.ps1` looked for `ops\ops\pipeline\engine\queue\file_overrides.ps1`.

## Low Risk

### R-005: Supplemental title keywords are PowerShell wildcard patterns

`Test-SubtitleTitleMatchesAnyKeyword` compares title text with `-like "*$kw*"`. Default keywords are simple words, but custom keywords containing wildcard metacharacters can overmatch.

Why this matters: a broad custom keyword could mark tracks as SDH/supplemental unexpectedly. This is operator-config dependent and lower severity than conversion/publish failure gates.

## Positive Findings

- Subtitle probe failure blocks encode/remux before publish.
- ASS/TX3G/BDPGS/VobSub conversion failures block encode/remux before publish.
- BDPGS/VobSub OCR refuses unknown language rather than defaulting to English.
- BDPGS/VobSub missing OCR tools and missing tessdata become standard failure records.
- VobSub sidecar pairs are discovered and incomplete pairs retain review evidence.
- External VobSub sidecars with conversion disabled route to review rather than pretending they were preserved.
- Sidecar publish failure happens before final media reveal and rolls back partial state.
- Completed QA blocks explicit OCR failures and reviews image subtitles without conversion evidence.
