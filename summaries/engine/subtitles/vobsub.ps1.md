---
file: engine/subtitles/vobsub.ps1
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-05-31
last_reviewed: 2026-05-31
sha256: d337f34458f14f41d4c25493ce853149aacd94d3bec6c0e5cc06ed96693528c1
---
# `engine/subtitles/vobsub.ps1`

**Purpose:** VobSub/DVD bitmap subtitle detection, external IDX/SUB sidecar pairing, Matroska extraction, Subtitle Edit `seconv` OCR invocation, SRT validation, and failure records.

**Functions:** `Convert-VobSubToSrt`, `ConvertTo-VobSubEmbeddedSrtTrackRecords`, `Extract-VobSubToIdxSub`, `Find-VobSubSidecarPairs`, `Get-VobSubIdxLanguage`, `New-VobSubFailureRecord`, `New-VobSubSidecarSubtitleEntry`, `Resolve-VobSubMkvTrackId`, `Resolve-VobSubMkvextractPath`, `Resolve-VobSubOcrLanguage`, `Resolve-VobSubOcrToolInvocation`, `Resolve-VobSubTesseractInvocation`, `Test-CanPreserveVobSubInFfmpegOutput`, `Test-IsVobSubSubtitleStream`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/subtitles/vobsub.ps1`._
