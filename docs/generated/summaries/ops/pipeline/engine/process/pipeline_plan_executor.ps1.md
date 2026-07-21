---
file: ops/pipeline/engine/process/pipeline_plan_executor.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-06-30
last_reviewed: 2026-06-04
sha256: 2f15abfc3607033afa27825ee0fd5c13d59707c745fea291722efff43854e546
---
# `ops/pipeline/engine/process/pipeline_plan_executor.ps1`

**Purpose:** PowerShell implementation for pipeline plan executor; exposes ConvertTo-PipelinePlanBool, ConvertTo-PipelinePlanExecutorJson, ConvertTo-PipelinePlanFfmpegSubtitleFilterPath.

**Public symbols:** `ConvertTo-PipelinePlanBool`, `ConvertTo-PipelinePlanExecutorJson`, `ConvertTo-PipelinePlanFfmpegSubtitleFilterPath`, `ConvertTo-PipelinePlanInt`, `DebugLog`, `Format-PipelinePlanExecutorCommandLine`, `Get-PipelinePlanAllowNoAudio`, `Get-PipelinePlanAudioMaxChannels`, `Get-PipelinePlanEffectivePolicyValue`, `Get-PipelinePlanEncodeCodec`, `Get-PipelinePlanEncodeStep`, `Get-PipelinePlanGlobalTitle`, `Get-PipelinePlanInputPath`, `Get-PipelinePlanIsTV`, `Get-PipelinePlanOutputPath`, `Get-PipelinePlanPresetVideoValue`, `Get-PipelinePlanSubtitleOrdinalMap`, `Get-PipelinePlanTranscodeBitrate`, `Invoke-PipelinePlanExecutorDryRun`, `New-PipelinePlanExecutorAudioArgumentList`, `New-PipelinePlanExecutorDryRun`, `New-PipelinePlanExecutorEncodeCommand`, `New-PipelinePlanExecutorEncodeMuxArgumentList`, `New-PipelinePlanExecutorMkvmergeArgumentList`, `New-PipelinePlanExecutorMp4RemuxArgumentList`, `New-PipelinePlanExecutorNativeCommand`, `New-PipelinePlanExecutorRemuxAvArgumentList`, `New-PipelinePlanExecutorSubtitleArgumentList`, `New-PipelinePlanExecutorSubtitleBurnVideoFilterArgs`, `Resolve-PipelinePlanMkvmergeSubtitleTrackIds`, `Write-Log`
**Invoked stages:** `command`, `encode-mkvmerge`, `remux-av`, `remux-mkvmerge`, `remux-mp4`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/pipeline_plan_executor.ps1`._
