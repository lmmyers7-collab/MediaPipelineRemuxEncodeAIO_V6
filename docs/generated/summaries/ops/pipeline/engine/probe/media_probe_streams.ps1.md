---
file: ops/pipeline/engine/probe/media_probe_streams.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-07-16
last_reviewed: 2026-07-11
sha256: 92057790418103e233b11cc3aaa18eb77630a36d7d9a3458c9942d0c41b60b23
---
# `ops/pipeline/engine/probe/media_probe_streams.ps1`

**Purpose:** PowerShell implementation for media probe streams; exposes ConvertTo-VideoStreamEvidenceBool, ConvertTo-VideoStreamEvidenceInt, ConvertTo-VideoStreamEvidenceRows.

**Public symbols:** `ConvertTo-VideoStreamEvidenceBool`, `ConvertTo-VideoStreamEvidenceInt`, `ConvertTo-VideoStreamEvidenceRows`, `ConvertTo-VideoStreamFailureEvidence`, `Get-SourceTitleTag`, `Get-SourceVideoCodec`, `Get-SourceVideoStreamInventory`, `Get-VideoStreamEvidenceProperty`, `Test-Hdr10OutputMetadataPreservation`, `Test-OutputVideoStreamPreservation`, `Test-SourceVideoStreamAttachedPicture`, `Test-SourceVideoStreamPublishPolicy`
**Invoked stages:** `source-title-tag`, `source-video-codec`, `source-video-stream-inventory`
**Invoked tools:** `ffmpeg`, `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe_streams.ps1`._
