---
file: ops/pipeline/engine/subtitles/vobsub.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: bf7a0c521f6f7c629a0a0b9bc7ec4591a7eecb3ebe1b5da6b5f837657ed695f1
---
# `ops/pipeline/engine/subtitles/vobsub.ps1`

**Purpose:** PowerShell implementation for vobsub; exposes Convert-VobSubMp4StreamToTemporaryMatroska, Convert-VobSubToSrt, ConvertTo-VobSubEmbeddedSrtTrackRecords.

**Public symbols:** `Convert-VobSubMp4StreamToTemporaryMatroska`, `Convert-VobSubToSrt`, `ConvertTo-VobSubEmbeddedSrtTrackRecords`, `Extract-VobSubToIdxSub`, `Find-VobSubSidecarPairs`, `Get-MkvmergeTrackLanguage`, `Get-MkvmergeTrackTitle`, `Get-VobSubIdxLanguage`, `Get-VobSubObjectPropertyValue`, `Get-VobSubOcrToolKind`, `Get-VobSubToolFailureSummary`, `Get-VobSubToolResultText`, `New-VobSubFailureRecord`, `New-VobSubSidecarSubtitleEntry`, `Resolve-VobSubMkvextractPath`, `Resolve-VobSubMkvTrackId`, `Resolve-VobSubOcrLanguage`, `Resolve-VobSubOcrToolInvocation`, `Resolve-VobSubTessdataDirectory`, `Resolve-VobSubTesseractInvocation`, `Test-CanPreserveVobSubInFfmpegOutput`, `Test-IsVobSubSubtitleStream`, `Test-MkvmergeTrackLooksLikeVobSub`, `Write-SubtitleTrackProgress`
**Invoked stages:** `convert_ocr`, `extract`, `subtitle-vobsub-extract`, `subtitle-vobsub-mkv-identify`, `subtitle-vobsub-mp4-stage`, `validate`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvextract`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/vobsub.ps1`._
