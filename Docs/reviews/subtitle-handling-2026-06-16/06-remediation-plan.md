# Remediation Plan

No code changes were made in this review. This is the proposed implementation order.

## Phase 1: Prevent Bad Publish and Silent Loss

1. Fix MP4 compatibility subtitle reduction.

   Add durable evidence for every converted SRT candidate that is not selected for MP4 external sidecar publish. At minimum, emit per-track dropped/review records with source stream index, source kind, source codec, language, title, forced, SDH, supplemental, conversion kind, and reason.

2. Add blocking rules for high-value subtitle classes.

   Block publish or route to review if MP4 compatibility would drop retained forced, SDH, or supplemental converted candidates without an explicit operator override.

3. Extend sidecar evidence.

   Add a neutral `converted_srt_sidecar_candidates` or `subtitle_output_reduction` array so publish sidecars and pending manifests record selected and non-selected converted candidates consistently across ASS/TX3G/BDPGS/VobSub.

4. Update tests.

   Change MP4 compatibility tests from asserting only the reduced one-sidecar behavior to asserting durable review/drop evidence for every non-selected candidate.

## Phase 2: Repair Contract Drift

1. Update completed-job schema.

   Add:

   - `vobsub_srt_failures`
   - `vobsub_embedded_srt_tracks`
   - any new MP4 subtitle reduction evidence fields

2. Add schema parity tests.

   Assert completed-job schema, runtime sidecar required arrays, pending manifest schema, and pending manifest trust required arrays stay aligned.

3. Update desktop QA if new evidence fields are added.

   Completed QA should include selected and dropped/reviewed converted SRT candidates in conversion evidence.

## Phase 3: Normalize Language Handling

1. Normalize ASS language through `Get-NormalizedSubtitleLanguage`.

   Keep raw tags in diagnostics, but make filtering policy use normalized values consistently.

2. Add tests.

   Cover blank ASS language with:

   - default `SubKeepLanguages`
   - `SubKeepLanguages=@('und')`
   - `AssKeepLanguages=@('und')`
   - supplemental and forced ASS titles

## Phase 4: Restore Dead Test Guards

1. Fix repo-root calculations in:

   - `Invoke-SrtValidationChecks.ps1`
   - `Invoke-FileOverrideSubtitleBurnChecks.ps1`

2. Run those tests from:

   - repo root
   - test directory
   - CI runner working directory

3. Add a small path-resolution helper if more tests duplicate the same brittle parent traversal.

## Phase 5: Harden Supplemental Keyword Matching

1. Replace wildcard matching with literal case-insensitive substring matching, or escape custom wildcard metacharacters.

2. Add tests for custom keywords with PowerShell wildcard characters.

3. Keep existing default behavior for current simple keywords.

## Phase 6: Real-Media Validation

1. Build or select representative samples:

   - ASS with signs/songs, dialogue, karaoke, blank language
   - TX3G/mov_text MP4
   - BDPGS English and unknown-language samples
   - VobSub embedded Matroska sample
   - external `.idx`/`.sub` pair with matching, missing, and empty `.sub`
   - multi-subtitle MP4 compatibility sample

2. Validate:

   - no publish on conversion failure
   - no publish on sidecar failure
   - sidecar evidence includes every retained/converted/dropped/reviewed subtitle
   - playback shows expected default/forced/supplemental subtitles
   - OCR output is non-empty and roughly aligned

## Priority

1. F-001 MP4 compatibility loss risk.
2. F-004 dead SRT/burn test harnesses.
3. F-002 completed schema VobSub drift.
4. F-003 ASS language normalization consistency.
5. F-005 supplemental keyword literal matching.
