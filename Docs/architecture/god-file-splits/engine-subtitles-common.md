# ops/pipeline/engine/subtitles/common.ps1

## Current Strain

- Approximate size: 1,014 lines, 37 functions.
- Risk level: high.
- Mixed concerns: subtitle config switches, language normalization,
  preferred/fallback default policy, failure records, progress reporting,
  title keyword matching, subtitle stream policy, route decision records, and
  filtering.

## Ideal Split

- `ops/pipeline/engine/subtitles/language_policy.ps1`: language normalization,
  preferred/fallback default matching, and display maps.
- `ops/pipeline/engine/subtitles/failure_records.ps1`: failure text, failure records, and
  registration helpers.
- `ops/pipeline/engine/subtitles/routing_decisions.ps1`: enriched title, policy chain,
  routing decisions, and decision records.
- `ops/pipeline/engine/subtitles/filtering.ps1`: filter entries and stream filtering.
- Keep common config/path helpers in `common.ps1` until callers are moved.

## Extraction Order

1. Extract language and title-keyword pure helpers.
2. Extract failure-record helpers.
3. Extract decision-record constructors.
4. Extract stream filtering only after subtitle tests pin every branch.

## Validation

- Subtitle builder decision checks.
- SRT, TX3G, BDPGS, ASS, and VobSub unit checks where available.
- Real-media subtitle samples for TX3G, BDPGS, ASS/SSA, and VobSub when touched.

## Must Not Change

Original subtitles are preserved by default, configured SRT conversion remains
explicit, OCR/conversion failure routes to review, and no subtitle track is
silently dropped.

