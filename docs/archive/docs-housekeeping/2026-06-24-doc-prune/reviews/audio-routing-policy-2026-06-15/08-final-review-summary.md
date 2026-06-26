# Final Audio Routing Review Summary

## Bottom Line

The current live PowerShell audio runtime is mostly sound where it matters most: it preserves non-MP4 tracks by default, standardizes PCM, records per-track decisions, avoids commentary as default, fails closed on bad probes, blocks all-audio-dropped overrides unless `AllowNoAudio` is enabled, and explicitly stamps MKV default audio tracks.

The main issues are policy drift around that runtime:

- Packaged `Default.psd1` can resolve as legacy `custom_codec_list` and allow FLAC/DTS passthrough instead of `plex_balanced`.
- Python preview/planner can force transcode for high-channel compatible audio, while PowerShell runtime copies it.
- The plan executor can emit no-audio output for all-dropped audio without the runtime `AllowNoAudio` guard.
- MP4 retained-track selection differs between PowerShell and Python.
- File override audio field ownership is split between Python validation and PowerShell runtime mapping.
- One integration matrix case still expects old MP4 multi-audio behavior.

## Findings

| ID | Severity | Summary |
|---|---:|---|
| 1 | High | Packaged `Default.psd1` can bypass `plex_balanced` by omitting `AudioPassthroughProfile` while carrying broad legacy codecs. |
| 2 | High | Python preview/planner transcodes above channel cap while PowerShell runtime copies compatible high-channel tracks. |
| 3 | High | Plan executor can emit `-an` for all dropped audio without carrying `AllowNoAudio`. |
| 4 | Medium | MP4 single-audio retained-track scoring differs between PowerShell and Python. |
| 5 | Medium | Per-file audio override contract is inconsistent across Python comments/API tests and PowerShell runtime mapping. |
| 6 | Medium | Integration regression matrix has stale MP4 audio expectations. |
| 7 | Low | Config preview profile-codec reconciliation depends on `CompatibleAudioCodecs` being in managed keys. |

## Good Existing Controls

- Runtime fails closed for missing audio unless `AllowNoAudio` is effective.
- Runtime fails closed for presence/metadata probe failure even when `AllowNoAudio` is enabled.
- Runtime fails closed when file overrides drop every audio stream unless `AllowNoAudio` is effective.
- Runtime records copied/transcoded/dropped/omitted audio decisions into completion sidecars.
- Runtime explicitly restamps MKV audio default-track flags through mkvmerge.
- Settings risk policy classifies `AllowNoAudio` and MP4 output as high risk.

## Highest Priority Fixes

1. Pin `Default.psd1` audio profile ownership and test it.
2. Align Python channel-cap semantics with PowerShell or intentionally change both.
3. Add `AllowNoAudio` fail-closed behavior to plan execution before any mutation promotion.
4. Unify MP4 selected-track ranking across PowerShell and Python.
5. Clarify supported per-file audio override fields and remove stale/deferred contract drift.
6. Update stale MP4 integration expectations.

## Validation Required Before Remediation Ships

- PowerShell audio policy unit tests.
- Python decision and integration tests.
- Runtime/preview parity fixtures for channel caps and MP4 selection.
- Real-media multi-audio validation with ffprobe/mkvmerge evidence.
- Completion sidecar inspection for every copied/transcoded/dropped/omitted track.
- Manual Plex/client playback review for DTS/FLAC/lossless/direct-play cases where practical.

## Files Produced

- `docs/reviews/audio-routing-policy-2026-06-15/00-review-scope.md`
- `docs/reviews/audio-routing-policy-2026-06-15/01-code-map.md`
- `docs/reviews/audio-routing-policy-2026-06-15/02-invariants-and-boundaries.md`
- `docs/reviews/audio-routing-policy-2026-06-15/03-risk-review.md`
- `docs/reviews/audio-routing-policy-2026-06-15/04-test-coverage-review.md`
- `docs/reviews/audio-routing-policy-2026-06-15/05-findings.md`
- `docs/reviews/audio-routing-policy-2026-06-15/06-remediation-plan.md`
- `docs/reviews/audio-routing-policy-2026-06-15/07-validation-plan.md`
- `docs/reviews/audio-routing-policy-2026-06-15/08-final-review-summary.md`
