# Phase 6 - Real-Media Pilot

## Goal

Rerun the repeatable real-media sample set against the named `V6.0.0` portable
candidate.

## Required Sample Categories

Use at least one sample for each category:

1. H.264 compatible remux/direct-play sample.
2. Encode/size-policy sample that should not remux.
3. Preferred-language ASS/SSA subtitle sample.
4. MP4/TX3G subtitle sample.
5. Audio-policy sample with default/preferred language and
   passthrough/transcode evidence.
6. Deferred publish/final-placement sample where output is parked, then
   drained.

## Pass Threshold

All six categories must pass with:

- source hash unchanged before and after
- current Queue route/decision reason
- Completed output proof
- completed manifest proof
- sidecar proof when expected
- relevant FFmpeg/run-log evidence
- subtitle behavior evidence
- audio behavior evidence
- size-growth/encode policy evidence
- Pending Publish park/drain or final-placement proof
- manual playback check
- Sample Validation record that reconciles to current backend evidence

Any of these blocks `V6.0.0`:

- source mutation
- silent subtitle conversion failure
- wrong audio policy
- unsafe publish/drain
- missing output with no parked/drain proof
- backend/WebView policy mismatch
- accepted validation note that no longer reconciles to current backend proof

## Steps

1. Generate or prepare a worksheet for each sample.
2. Select one sample at a time.
3. Verify saved Settings policy and Launch readiness.
4. Launch only through backend-owned controls.
5. Capture Queue, Completed, Pending Publish, Diagnostics, and playback proof.
6. Preview and append Sample Validation evidence only after proof is current.
7. Repeat until all six categories pass.

## Evidence

Use:

- `Docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`
- `Docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md`
- `scripts/operator/New-RealMediaValidationWorksheet.ps1`
- WebView Home Sample Validation evidence panels
- Completed selected pilot evidence packet
- Pending Publish post-drain trust review
- Diagnostics bounded tails and owner-row handoff

Detailed worksheets may contain personal paths and should stay outside clean
handoff artifacts unless explicitly sanitized.

## Exit Criteria

- Six required categories pass against the same named candidate.
- Evidence identifies candidate folder and app version.
- Real-media evidence does not rely on historical/stale records.
- Any failed sample has a clear rerun or release-blocking note.

