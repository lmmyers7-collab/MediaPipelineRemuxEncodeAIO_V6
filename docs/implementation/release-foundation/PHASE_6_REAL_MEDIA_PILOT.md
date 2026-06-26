# Phase 6 - Real-Media Pilot

## Goal

Rerun the repeatable real-media sample set against the named `2026.06.04.001` portable
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

Also include a BDPGS/OCR subtitle sample when that path is configured and a
representative sample is practical. If it cannot be included, record an
explicit waiver explaining the missing sample/tooling condition and the
residual validation risk.

## Prerequisites

- Read the required context docs listed in `AGENTS.md`.
- Confirm Phase 5 passed for the exact candidate folder used in this pilot.
- Confirm Phase 5 runtime-state externalization evidence passed for the exact
  candidate folder used in this pilot.
- Confirm samples are controlled validation copies or otherwise approved
  operator samples.
- Capture before-hash evidence for each source before launch.
- Confirm saved policy does not enable source deletion or source cleanup unless
  an intentionally named safe-delete setting is explicitly required and
  approved for this run.
- Confirm scratch-copy/run-log evidence will be captured for each sample.
- Stop if package/open/close evidence, source before-hashes, saved-policy
  source-safety posture, or sample ownership cannot be proven.

## Pass Threshold

All required categories must pass with:

- source hash unchanged before and after
- scratch-copy evidence or run-log evidence that processing used scratch
- current Queue route/decision reason
- Completed output proof
- completed manifest proof
- sidecar proof when expected
- relevant FFmpeg/run-log evidence
- subtitle behavior evidence, including original-subtitle preservation and
  preferred-language SRT evidence when configured
- audio behavior evidence
- size-growth/encode policy evidence
- Pending Publish park/drain or final-placement proof
- manual playback check
- Sample Validation record that reconciles to current backend evidence

Any of these blocks `2026.06.04.001`:

- source mutation
- silent subtitle conversion failure
- wrong audio policy
- unsafe publish/drain
- missing output with no parked/drain proof
- backend/WebView policy mismatch
- accepted validation note that no longer reconciles to current backend proof

## Steps

1. Generate or prepare a worksheet for each sample.
2. Record candidate identity, Phase 5 evidence, before-hash, and source-safety
   posture before launch.
3. Select one sample at a time.
4. Verify saved Settings policy and Launch readiness.
5. Launch only through backend-owned controls.
6. Capture Queue, scratch-copy/run-log, Completed, Pending Publish,
   Diagnostics, and playback proof.
7. Preview and append Sample Validation evidence only after proof is current.
8. Repeat until all required categories pass or are explicitly blocked.

## Evidence

Use:

- `docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`
- `docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md`
- `ops/scripts/operator/New-RealMediaValidationWorksheet.ps1`
- WebView Home Sample Validation evidence panels
- Completed selected pilot evidence packet
- Pending Publish post-drain trust review
- Diagnostics bounded tails and owner-row handoff

After evidence is recorded, run:

```powershell
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py --require-worktree-coverage
```

Detailed worksheets may contain personal paths and should stay outside clean
handoff artifacts unless explicitly sanitized.

## Exit Criteria

- All required categories pass against the same named candidate, with any
  BDPGS/OCR waiver explicitly recorded.
- Evidence identifies candidate folder and app version.
- Real-media evidence does not rely on historical/stale records.
- Any failed sample has a clear rerun or release-blocking note.

## Change Ledger And Rollback

- Create or update one change packet for this phase before evidence capture.
- Record the exact candidate folder, Phase 5 package/open/close evidence
  reference, Phase 5 runtime-state evidence reference, sample categories,
  sanitized evidence locations, and validation decisions.
- Roll back by marking failed or stale sample evidence as rejected/review-only
  and rebuilding or rerunning through earlier phases as needed. Do not repair,
  publish, drain, rename, clean up, or delete source media outside backend-owned
  controls.
