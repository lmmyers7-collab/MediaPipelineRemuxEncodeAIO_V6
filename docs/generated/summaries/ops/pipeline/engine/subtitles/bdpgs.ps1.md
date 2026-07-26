---
file: ops/pipeline/engine/subtitles/bdpgs.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 4a3df50d87d86210d1ffd61b32856b765f83a3238517db34b1382ad271d04f53
---
# `ops/pipeline/engine/subtitles/bdpgs.ps1`

**Purpose:** PowerShell implementation for bdpgs; exposes Convert-BdpgsToSrt, ConvertTo-BdpgsEmbeddedSrtTrackRecords, Extract-BdpgsToSup.

**Public symbols:** `Convert-BdpgsToSrt`, `ConvertTo-BdpgsEmbeddedSrtTrackRecords`, `Extract-BdpgsToSup`, `New-BdpgsFailureRecord`, `Repair-BdpgsOcrSrtPipeGlyphs`, `Repair-BdpgsOcrSrtPipeGlyphText`, `Resolve-BdpgsOcrLanguage`, `Resolve-BdpgsOcrTessdataPath`, `Resolve-BdpgsOcrToolInvocation`, `Test-CanPreserveBdpgsInFfmpegOutput`, `Test-IsBdpgsSubtitleStream`, `Write-SubtitleTrackProgress`
**Invoked stages:** `convert_ocr`, `extract`, `subtitle-bdpgs-sup-extract`, `validate`
**Invoked tools:** `ffmpeg`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/bdpgs.ps1`._
