---
file: ops/pipeline/engine/subtitles/builders.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 7f964e6ee0920e4de8221e7bcc8cf754182dc565b424b92f51994cd2d90efcaf
---
# `ops/pipeline/engine/subtitles/builders.ps1`

**Purpose:** PowerShell implementation for builders; exposes Build-SubtitleArgsForFFmpeg, Build-SubtitleTracksForMkvmerge, ConvertTo-FfmpegSubtitleFilterPath.

**Public symbols:** `Build-SubtitleArgsForFFmpeg`, `Build-SubtitleTracksForMkvmerge`, `ConvertTo-FfmpegSubtitleFilterPath`, `Get-MkvmergeAudioTids`, `Get-MkvmergeTidMap`, `Get-SubtitleBuilderObjectText`, `Get-SubtitleBuilderObjectValue`, `Get-SubtitleBuilderSourceSubtitleKind`, `New-SubtitleBuilderConvertedSrtCandidateRecord`, `New-SubtitleBuilderConvertedSrtSidecarTrack`, `New-SubtitleBuilderMp4ReductionFailureRecord`, `New-SubtitleBurnFailureRecord`, `New-SubtitleBurnVideoFilterArgsForFFmpeg`, `Publish-SubtitleBuilderRunMonitorPolicy`
**Invoked stages:** `remux-audio-mkvmerge-identify`, `subtitle-mkvmerge-identify`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/builders.ps1`._
