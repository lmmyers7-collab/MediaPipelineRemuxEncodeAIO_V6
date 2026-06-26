---
file: ops/pipeline/engine/subtitles/vobsub.ps1
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-06-12
last_reviewed: 2026-06-04
sha256: 60faf8e0921cef853301e852625e2e2edfb85bd9245277c657438bde1bcfb589
---
# `ops/pipeline/engine/subtitles/vobsub.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Convert-VobSubToSrt`, `ConvertTo-VobSubEmbeddedSrtTrackRecords`, `Extract-VobSubToIdxSub`, `Find-VobSubSidecarPairs`, `Get-MkvmergeTrackLanguage`, `Get-MkvmergeTrackTitle`, `Get-VobSubIdxLanguage`, `Get-VobSubObjectPropertyValue`, `Get-VobSubOcrToolKind`, `New-VobSubFailureRecord`, `New-VobSubSidecarSubtitleEntry`, `Resolve-VobSubMkvTrackId`, `Resolve-VobSubMkvextractPath`, `Resolve-VobSubOcrLanguage`, `Resolve-VobSubOcrToolInvocation`, `Resolve-VobSubTessdataDirectory`, `Resolve-VobSubTesseractInvocation`, `Test-CanPreserveVobSubInFfmpegOutput`, `Test-IsVobSubSubtitleStream`, `Test-MkvmergeTrackLooksLikeVobSub`, `Write-SubtitleTrackProgress`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/vobsub.ps1`._
