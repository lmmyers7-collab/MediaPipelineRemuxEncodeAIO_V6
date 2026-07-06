# FFmpeg Media Policy Regression Matrix

Last reviewed: 2026-06-18

This document describes the machine-readable matrix at
`tests/fixtures/media_policy/ffmpeg_media_policy_regression_matrix.json`.
The matrix is validation metadata only. It is not a source of media policy;
Python planner code and the PowerShell runtime remain authoritative.

## Purpose

The matrix makes the expensive FFmpeg/media-policy validation surface explicit
without changing behavior. Every row must name:

- the expected outcome
- owning Python or PowerShell code paths
- at least one automated check
- a validation rung
- the safety boundary that applies before behavior changes

The required axes are remux, encode, subtitles, audio, size policy, stream
mapping, sidecars, pending publish, and failure modes.

## Current Coverage

The initial fixture covers 14 rows:

| Area | Example rows |
|---|---|
| Remux/copy | H.264 direct-copy safe, container-only remux |
| Encode | bitrate over cap, incompatible MPEG-2 AVI, subtitle burn-in |
| Audio | MP4 multi-audio reduction, audio-only advisory policy |
| Subtitles | image-subtitle MP4 rejection, burn-in, OCR/conversion review gate |
| Size policy | block-publish size growth |
| Sidecars/pending publish | sidecar manifest carry-forward, manifest-backed drain |
| Failure modes | unprobeable source, FFmpeg failure, subtitle OCR failure, orphan drain blockers |

## Validation

Run the matrix guard with the bundled Python runtime:

```powershell
apps\desktop\runtime\Python\python.exe -m unittest tests.python.integration.test_ffmpeg_media_policy_regression_matrix -q
```

That guard verifies row shape, owner/check path existence, axis coverage,
Python planner expectations for rows that have source fixtures, size-policy
contract expectations, and the TESTGAP-006 closure rule.

The guard does not process media and does not prove runtime FFmpeg behavior.
Rows that depend on PowerShell execution, subtitle/OCR output, audio stream
mapping, sidecar carry-forward, or pending-publish drain still require the
named PowerShell tests and, for behavior changes, representative real-media
validation.

## TESTGAP-006 Rule

`TESTGAP-006` stays open until both of these are true:

1. Python planner/preview and PowerShell runtime parity coverage exists for
   route, audio, subtitle, size, and publish-relevant rows.
2. Any behavior-changing FFmpeg, subtitle, audio, publish/drain, source/scratch,
   output, or cleanup work has representative real-media evidence.

Synthetic matrix rows and Tdarr samples are useful regression evidence, but
they do not replace the real-media gate described in
`docs/sample-validation/REAL_MEDIA_PILOT_CHECKLIST.md` and
`docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`.
