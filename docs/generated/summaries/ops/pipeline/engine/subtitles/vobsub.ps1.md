---
file: ops/pipeline/engine/subtitles/vobsub.ps1
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 097b2a8fb0c9ec3c034617dcf2d2c8c658b6879759a037368c8c616c34ab5311
---
# `ops/pipeline/engine/subtitles/vobsub.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Convert-VobSubMp4StreamToTemporaryMatroska`, `Convert-VobSubToSrt`, `ConvertTo-VobSubEmbeddedSrtTrackRecords`, `Extract-VobSubToIdxSub`, `Find-VobSubSidecarPairs`, `Get-MkvmergeTrackLanguage`, `Get-MkvmergeTrackTitle`, `Get-VobSubIdxLanguage`, `Get-VobSubObjectPropertyValue`, `Get-VobSubOcrToolKind`, `Get-VobSubToolFailureSummary`, `Get-VobSubToolResultText`, `New-VobSubFailureRecord`, `New-VobSubSidecarSubtitleEntry`, `Resolve-VobSubMkvTrackId`, `Resolve-VobSubMkvextractPath`, `Resolve-VobSubOcrLanguage`, `Resolve-VobSubOcrToolInvocation`, `Resolve-VobSubTessdataDirectory`, `Resolve-VobSubTesseractInvocation`, `Test-CanPreserveVobSubInFfmpegOutput`, `Test-IsVobSubSubtitleStream`, `Test-MkvmergeTrackLooksLikeVobSub`, `Write-SubtitleTrackProgress`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/vobsub.ps1`._
