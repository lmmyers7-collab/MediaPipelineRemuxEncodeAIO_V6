# Validation - Pipeline Processing Split

## Validation Principle

Use the smallest safe rung for each phase, but do not under-validate high-risk
media behavior. A clean unit test does not prove real FFmpeg behavior. A clean
smoke does not prove real-media correctness.

## Docs-Only Validation For This Planning Pack

For edits only to this planning pack and `docs/DOCS_INDEX.md`, run:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke

.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
  mediapipeline.tools.dev.check_active_doc_references

.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
  mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

If strict coverage fails because unrelated files were dirty before the work,
do not absorb unrelated files into the packet. Report the uncovered files.

## Implementation Validation Ladder

| Implementation change | Minimum validation |
|---|---|
| Add tests only | New/changed targeted tests plus change-packet validation. |
| Add new PowerShell helper module without behavior move | Mandatory module load-order test plus related targeted unit tests. |
| Move remux command construction or mkvmerge execution | Remux-targeted unit tests, pipeline plan executor checks, reliability regression, tool integration, real-media remux validation. |
| Move encode command construction or FFmpeg execution | Encoder flag/runtime/capability tests, pipeline plan executor checks, adversarial force-kill encode, reliability regression, tool integration, real-media encode validation. |
| Move fallback, verification, size guard, or publish handoff | Targeted fallback/verification/size/publish tests, publish-order characterization, pending publish checks, adversarial force-kill encode, reliability regression, tool integration, real-media validation. |
| Touch subtitle/audio/pending publish/drain behavior | Targeted domain tests plus real-media samples covering that domain. |
| Add live dependency on `pipeline_plan_executor.ps1` | Add it to `module_loader.ps1`, prove real startup load-order, and keep command-shape parity fixtures. |
| Change module loader or drain-only startup path | Non-mutating startup/load-order harness for normal, worker-child `-SingleFile`, and `-DrainPendingPushes`; do not run live drain as a loader test. |

## Targeted PowerShell Checks

Use the bundled PowerShell runtime:

```powershell
$pwsh = ".\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe"
```

Do not rely on a generic `Invoke-UnitChecks.ps1` wrapper unless a phase creates
and validates that wrapper. Use the explicit scripts below.

Core processing:

```powershell
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PipelineProcessingPreflightChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PipelineProcessingSourceProbeChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PipelinePlanExecutorChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-MediaRouteSelectionChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-FFmpegProgressChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerSlotChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerClaimLifecycleChecks.ps1
```

Encode:

```powershell
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-EncodeFlagPolicyChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-EncoderRuntimeMatrixChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-EncoderCapabilityProbeChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-EncodeSizeGuardInspectionChecks.ps1
```

Dynamic HDR and verification:

```powershell
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-DynamicHdrDetectionChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-DynamicHdrToolingChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-QualityVerificationChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-MultiVideoTopologyChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-MediaVerificationSafetyChecks.ps1
```

Audio, subtitles, publish:

```powershell
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-AudioPolicyChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-SubtitleBuilderDecisionChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-SubtitleOcrPathResolutionChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-VobSubSubtitleChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishSafetyChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishOwnershipChecks.ps1
```

Command-shape parity fixtures must cover the live command builders and
`pipeline_plan_executor.ps1` for:

- primary encode;
- safe hardware retry;
- CPU fallback;
- Dynamic HDR preserve encode;
- remux FFmpeg AV temp stage;
- mkvmerge remux with attachments, subtitles, and audio default flags;
- MP4 remux argument shape where applicable.

Publish-order characterization must fail if `Complete-PipelineOutputPublish`
can run before output existence, duration verification, video-stream
preservation, Dynamic HDR output verification when applicable, quality
verification, and size/waste guard acceptance.

For remux publish handoff, the equivalent characterization must fail if
`Complete-PipelineOutputPublish` can run before output existence/non-empty,
duration verification, video-stream preservation, accepted mkvmerge result, and
subtitle/sidecar forwarding readiness.

Fallback characterization must cover both public `Do-Remux` fallback switches:
`-FallbackFromOversizedEncode` and `-FallbackFromDynamicHdrEncode`. Assert
fallback-specific rejection objects, route reason restoration,
`LastPublishResult`, `KeepScratchInput`, scratch retention, cleanup decisions,
and boolean return semantics.

Regression and tool checks:

```powershell
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Invoke-ReliabilityRegressionChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Invoke-ToolIntegrationChecks.ps1
& $pwsh -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Invoke-AdversarialForceKillEncodeChecks.ps1
```

## Real-Media Validation Matrix

Run real-media validation after any behavior-affecting implementation phase.
The exact media set can vary, but cover these behaviors when touched:

| Behavior touched | Required sample proof |
|---|---|
| Remux command/mkvmerge | Remux sample publishes, output ffprobe confirms expected container/streams, source hash unchanged. |
| Encode command/FFmpeg execution | Encode sample publishes, output ffprobe confirms codec/profile/tags, source hash unchanged. |
| CPU fallback | Sample or config that forces CPU fallback, output route evidence shows CPU fallback correctly. |
| Dynamic HDR | Dolby Vision and/or HDR10+ sample depending on touched family, output metadata verification passes or blocks publish as expected. |
| Subtitle planning | Subtitle-bearing sample for touched formats: TX3G, BDPGS, ASS/SSA, VobSub as applicable. |
| Audio policy | Multi-audio sample confirms passthrough/transcode/default-track behavior. |
| Multi-video verification | Multi-video sample confirms every real source video stream is preserved or publish is blocked. |
| Size guard/remux fallback | Oversized encode scenario confirms fallback or rejection evidence. |
| Pending publish/publish handoff | Deferred publish sample parks, manifests, drains, and preserves source/output hashes. |

If a phase moves FFmpeg, mkvmerge, fallback, verification, size guard, or publish
handoff code, real-media validation is mandatory before release acceptance. If a
sample is unavailable, record the missing case as an unresolved validation gap
instead of marking the phase complete for release.

Record evidence using:

```text
docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md
```

Or generate a worksheet:

```powershell
.\ops\scripts\operator\New-RealMediaValidationWorksheet.ps1 -SamplePath "<absolute media source path>" -Shell "WebView preview"
```

## Change-Packet Validation

During implementation:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
  mediapipeline.tools.change_control.record_change_touch `
  MP-CHANGE-YYYY-MMDD-### path/to/file --area pipeline --note "Why changed."
```

Before final response:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
  mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

## Generated Summary Refresh

After source edits:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
  mediapipeline.tools.dev.refresh_summaries --changed
```

Do not hand-edit files under `docs/generated/` unless a file explicitly says it
is human-maintained.

## Failure Triage

If validation fails after an extraction:

1. Confirm the failing test passed before the extraction.
2. Identify whether the failure is load order, missing function, changed output
   shape, changed failure evidence, changed media behavior, or environment.
3. If behavior changed unintentionally, revert only the current extraction
   slice, not unrelated user changes.
4. If behavior changed intentionally, stop and write a separate behavior-change
   plan with real-media validation.
5. Re-run the smallest failing test before broader suites.
