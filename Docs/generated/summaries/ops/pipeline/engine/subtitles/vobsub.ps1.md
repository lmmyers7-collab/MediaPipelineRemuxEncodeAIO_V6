---
file: ops/pipeline/engine/subtitles/vobsub.ps1
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 7829ef3287cc68842671028e554e039000949695df2d1160e8a1f76bb28e5c06
---
# `ops/pipeline/engine/subtitles/vobsub.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Convert-VobSubToSrt`, `ConvertTo-VobSubEmbeddedSrtTrackRecords`, `Extract-VobSubToIdxSub`, `Find-VobSubSidecarPairs`, `Get-MkvmergeTrackLanguage`, `Get-MkvmergeTrackTitle`, `Get-VobSubIdxLanguage`, `Get-VobSubObjectPropertyValue`, `Get-VobSubOcrToolKind`, `New-VobSubFailureRecord`, `New-VobSubSidecarSubtitleEntry`, `Resolve-VobSubMkvTrackId`, `Resolve-VobSubMkvextractPath`, `Resolve-VobSubOcrLanguage`, `Resolve-VobSubOcrToolInvocation`, `Resolve-VobSubTessdataDirectory`, `Resolve-VobSubTesseractInvocation`, `Test-CanPreserveVobSubInFfmpegOutput`, `Test-IsVobSubSubtitleStream`, `Test-MkvmergeTrackLooksLikeVobSub`, `Write-SubtitleTrackProgress`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/vobsub.ps1`._
