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

- Status: partial local evidence as of 2026-05-29.
- Full source/dev release self-test passed after the `engine\` migration.
- A copied release package with the Tauri executable included launched and
  closed in package mode on this machine.
- Runtime Completed evidence from 2026-05-29 proves real remux/immediate
  publish rows with output/sidecar, audio-copy, subtitle-decision, and
  size-delta fields.
- Remaining evidence gap before deleting `Pipeline\Modules` compatibility
  shims: fresh representative proof for encode/size, deferred pending publish,
  drain, and operator-accepted real-media validation records after the module
  move.

See `post-module-move-evidence-2026-05-29.md` for the non-sensitive local
evidence summary.

## Revalidation rule

Rerun representative real-media validation whenever FFmpeg command generation,
subtitle conversion/OCR, audio routing, source/scratch/output movement,
pending-publish drain, final publish, or cleanup behavior changes.
