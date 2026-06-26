# Real-media validation runs

This folder is the operator evidence anchor for representative real-media
validation. Detailed worksheets may contain personal source/output paths, so
release packaging can exclude run-specific files from this folder.

## Current status

- Status: complete by operator attestation.
- Attested date: 2026-05-28.
- Covered categories: remux, encode/size policy, subtitle conversion, audio
  policy, and pending-publish/final-placement behavior.
- Evidence handling: keep detailed worksheets or local notes outside packaged
  release artifacts when they contain personal paths.

## Post-module-move status

- Status: closed local evidence as of 2026-05-29.
- Full source/dev release self-test passed after the `ops\pipeline\engine\` migration.
- A copied release package with the Tauri executable included launched and
  closed in package mode on this machine.
- Runtime Completed evidence from 2026-05-29 proves real remux/immediate
  publish rows with output/sidecar, audio-copy, subtitle-decision, and
  size-delta fields.
- Scratch-only post-move validation covers forced encode/size policy, subtitle
  conversion, audio evidence, deferred pending publish, drain, and rename-output
  safety without processing the original real source directly.
- The legacy-removal gate is closed in `docs/OPEN_WORK_CHECKLIST.md`: `Pipeline\Modules`
  is no longer an active module surface, and active PowerShell implementations
  live under `ops\pipeline\engine\<domain>`.

See `post-module-move-evidence-2026-05-29.md` for the non-sensitive local
evidence summary.

## Tdarr proof-pack media-policy status

- Status: completed local proof-pack rerun for MP-CHANGE-2026-0622-001 on
  2026-06-22.
- Evidence run: `run-20260622-codex-proof-all-final`.
- Covered scope: Tdarr-generated sample matrix remux/encode routing,
  source-video probe behavior, REMUX-AV timestamp synthesis, invalid-container
  failure classification, output probing, and source-hash preservation.
- Result: 92/92 selected cases executed; 76 outputs published and ffprobe
  verified with video streams; 92/92 source hashes unchanged.
- Remaining warnings are fail-closed expected/invalid fixtures: audio-only or
  manifest-mismatched video-missing cases report `SOURCE_MEDIA_VIDEO_MISSING`,
  and the corrupt AVI/rawvideo fixture reports `SOURCE_MEDIA_CONTAINER_INVALID`.
  These warnings are terminal and non-retryable.

## Targeted Dynamic HDR metadata preservation status

- Status: targeted local metadata-preservation proofs complete for the currently
  implemented Dolby Vision P8.1 and HDR10+ encode paths as of 2026-06-22.
- Dolby Vision proof: MP-CHANGE-2026-0622-004, public Dolby Browser Test Kit
  P8.1 SD source, CPU/libx265 encode with FFmpeg native Dolby Vision coding,
  output DOVI verified, source/output RPU frame counts `1721/1721`, source hash
  unchanged.
- HDR10+ proof: MP-CHANGE-2026-0622-007, public FFPictures Lake HDR10+ sample,
  CPU/libx265 encode with relative `dhdr10-info`, output HDR10+ verified,
  source/output extracted HDR10+ JSON hashes matched, source hash unchanged.
- Evidence handling: detailed source/output paths and generated proof artifacts
  remain under gitignored `LocalBase\DynamicHdrValidationRuns\` and
  `LocalBase\DynamicHdrValidationSamples\`.
- Limitation: these are automated metadata-preservation proofs. Playback-device
  Dolby Vision/HDR10+ indicator checks and broader untested profile/source
  combinations remain future real-media validation gates for those cases.

## Revalidation rule

Rerun representative real-media validation whenever FFmpeg command generation,
subtitle conversion/OCR, audio routing, source/scratch/output movement,
pending-publish drain, final publish, or cleanup behavior changes.
