[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Encode core split checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-False {
    param([bool] $Condition, [string] $Message)
    if ($Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

foreach ($relativePath in @(
        'ops\pipeline\engine\process\encode_context.ps1',
        'ops\pipeline\engine\process\encode_preflight.ps1',
        'ops\pipeline\engine\process\encode_attempt_plan.ps1',
        'ops\pipeline\engine\process\encode_command_builder.ps1',
        'ops\pipeline\engine\process\encode_execution.ps1',
        'ops\pipeline\engine\process\encode_orchestrator.ps1'
    )) {
    . (Join-Path $repoRoot $relativePath)
}

$script:EncodeHarnessRoots = [System.Collections.Generic.List[string]]::new()

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

function Set-ProgressStage {
    param([string] $Stage, [string] $Status, [string] $Route, [string] $CopyState, $Percent, [switch] $SaveNow)
}

function Get-SafeLocalName {
    param([string] $Name)
    return "safe-$Name"
}

function Ensure-ScratchCopy {
    param($File, [string] $SafeName)
    return $script:ScratchPath
}

function Remove-ScratchFingerprint { param([string] $ScratchPath) }

function Remove-EmptyScratchContainer { param([string] $ScratchPath) }

function Get-OutputPaths {
    param($File, [bool] $IsTV, $TvInfo, [string] $SafeName)
    return $script:CurrentPaths
}

function Test-OutputNeedsReprocess {
    param([string] $OutputPath, $SourceFile)
    return $script:OutputNeedsReprocess
}

function Invoke-Tx3gSidecarExportForExistingOutput {
    param($SourceFile, [string] $ScratchPath, [string] $MediaOutputPath, [string] $Context)
    return $script:ExistingOutputSidecarOk
}

function New-ExistingOutputPublishResult {
    param($SourceFile, [string] $OutputPath)
    return [pscustomobject][ordered]@{
        Ok                = $true
        PublishMode       = 'existing-output'
        OutputPath        = $OutputPath
        DeleteLocalOutput = $false
        KeepScratchInput  = $false
    }
}

function Clear-SourceFailureState {
    param($SourceFile)
}

function Test-DiskSpace {
    param([string] $Path, [double] $MinGB, [string] $Label)
    return $script:DiskSpaceOk
}

function Test-EstimatedOutputSpace {
    param([string] $SourcePath, [string] $Label)
    return $script:EstimatedSpaceOk
}

function Test-SourceVideoStreamPublishPolicy {
    param([string] $FilePath, [string] $Route)
    return [pscustomobject][ordered]@{
        Allowed   = $script:VideoPolicyOk
        Reason    = if ($script:VideoPolicyOk) { '' } else { 'video policy blocked' }
        ErrorCode = if ($script:VideoPolicyOk) { '' } else { 'VIDEO_POLICY_BLOCKED' }
        Inventory = [pscustomobject][ordered]@{ RealVideoStreamCount = 1 }
    }
}

function Get-HDRState {
    param([string] $FilePath)
    return [pscustomobject][ordered]@{
        Known = $script:HdrKnown
        IsHDR = $script:HdrIsHdr
        Reason = if ($script:HdrKnown) { '' } else { 'probe failed' }
    }
}

function Register-SourceFailure {
    param(
        $SourceFile,
        [string] $ScratchPath,
        [string] $Classification,
        [string] $Reason,
        [string] $Stage,
        [string] $ErrorCode,
        [string] $SuggestedAction,
        $AdditionalProperties
    )
    $script:RegisteredFailures.Add($Stage) | Out-Null
    $script:RegisteredFailureScratchPaths.Add($ScratchPath) | Out-Null
}

function New-EncodeAttemptPlan {
    param(
        [switch] $UseCpuFallback,
        [switch] $UseSafeHardwareRetry,
        [bool] $IsTV,
        [bool] $IsHDR,
        [string] $InputPath,
        [array] $ExtraInputs,
        [string] $GlobalTitle,
        [array] $AudioArgs,
        [array] $SubtitleMapArgs,
        [array] $VideoFilterArgs,
        [string] $OutputPath,
        [string] $VideoCodec,
        [string] $VideoPreset,
        [int] $VideoQuality,
        [array] $ExtraVideoFlags,
        [int] $FallbackCpuQuality,
        [string] $EncoderBackend,
        [string] $EncodeLadder,
        [string] $CpuPreset,
        [int] $CpuMaxThreads,
        [string] $Hdr10MasterDisplay,
        [string] $Hdr10MaxCll
    )
    return [pscustomobject][ordered]@{
        Attempt              = if ($UseSafeHardwareRetry) { 'safe-retry' } elseif ($UseCpuFallback) { 'cpu' } else { 'primary' }
        Route                = if ($UseCpuFallback) { 'encode-cpu-fallback' } else { 'encode' }
        Label                = if ($UseSafeHardwareRetry) { 'ENCODE-SAFE-RETRY' } elseif ($UseCpuFallback) { 'ENCODE-CPU' } else { 'ENCODE' }
        ProgressStage        = if ($UseCpuFallback) { 'encode_cpu' } else { 'encode' }
        ProgressRoute        = if ($UseCpuFallback) { 'encode-cpu-fallback' } else { 'encode' }
        ReproStage           = if ($UseSafeHardwareRetry) { 'encode-safe-retry' } elseif ($UseCpuFallback) { 'encode-cpu-fallback' } else { 'encode' }
        UseCpuFallback       = [bool]$UseCpuFallback
        UseSafeHardwareRetry = [bool]$UseSafeHardwareRetry
        SelectedEncoder      = $VideoCodec
        EncoderKind          = if ($UseCpuFallback) { 'cpu' } else { 'hardware' }
        SelectedGpuDevice    = ''
        EncodeLadder         = $EncodeLadder
        CpuPreset            = $CpuPreset
        ArgumentList         = @('-i', $InputPath, '-c:v', $VideoCodec, '-preset', $VideoPreset, '-crf', [string]$VideoQuality, '-y', $OutputPath)
    }
}

function Invoke-FFmpegWithProgress {
    param(
        [array] $FFArgs,
        [string] $Label,
        [string] $InputFile,
        [int] $TimeoutSeconds,
        [string] $ProgressStage,
        [string] $ProgressRoute,
        [string] $ReproStage,
        [switch] $CpuEncode,
        [string] $ProcessPriority = 'inherit',
        [string] $OutputPath = '',
        [AllowNull()] $WasteGuardContext = $null,
        [string] $WorkingDirectory = ''
    )
    $script:LastFfmpegCall = [pscustomobject][ordered]@{
        FFArgs            = @($FFArgs)
        Label             = $Label
        InputFile         = $InputFile
        TimeoutSeconds    = $TimeoutSeconds
        ProgressStage     = $ProgressStage
        ProgressRoute     = $ProgressRoute
        ReproStage        = $ReproStage
        CpuEncode         = [bool]$CpuEncode
        ProcessPriority   = $ProcessPriority
        OutputPath        = $OutputPath
        WasteGuardContext = $WasteGuardContext
        WorkingDirectory  = $WorkingDirectory
    }
    return $script:FfmpegReturn
}

function Reset-EncodeHarness {
    param(
        [bool] $CreateExistingOutput = $false,
        [bool] $DiskSpacePasses = $true,
        [bool] $EstimatedSpacePasses = $true,
        [bool] $VideoPolicyPasses = $true,
        [bool] $HdrProbeKnown = $true,
        [bool] $IsHdr = $false
    )

    $root = Join-Path ([System.IO.Path]::GetTempPath()) "mediapipeline-encode-core-$([guid]::NewGuid().ToString('N'))"
    [System.IO.Directory]::CreateDirectory($root) | Out-Null
    $script:EncodeHarnessRoots.Add($root) | Out-Null

    $sourcePath = Join-Path $root 'source.mkv'
    $script:ScratchPath = Join-Path $root 'scratch.mkv'
    $localDir = Join-Path $root 'local'
    $serverDir = Join-Path $root 'server'
    [System.IO.Directory]::CreateDirectory($localDir) | Out-Null
    [System.IO.Directory]::CreateDirectory($serverDir) | Out-Null
    Set-Content -LiteralPath $sourcePath -Value 'source' -NoNewline
    Set-Content -LiteralPath $script:ScratchPath -Value 'scratch' -NoNewline

    $serverOut = Join-Path $serverDir 'output.mkv'
    if ($CreateExistingOutput) {
        Set-Content -LiteralPath $serverOut -Value 'existing' -NoNewline
    }
    $script:SourceFile = Get-Item -LiteralPath $sourcePath
    $script:CurrentPaths = [pscustomobject][ordered]@{
        LocalDir  = $localDir
        ServerDir = $serverDir
        LocalOut  = Join-Path $localDir 'output.mkv'
        ServerOut = $serverOut
    }
    $script:RegisteredFailures = [System.Collections.Generic.List[string]]::new()
    $script:RegisteredFailureScratchPaths = [System.Collections.Generic.List[string]]::new()
    $script:OutputNeedsReprocess = $false
    $script:ExistingOutputSidecarOk = $true
    $script:DiskSpaceOk = $DiskSpacePasses
    $script:EstimatedSpaceOk = $EstimatedSpacePasses
    $script:VideoPolicyOk = $VideoPolicyPasses
    $script:HdrKnown = $HdrProbeKnown
    $script:HdrIsHdr = $IsHdr
    $script:LastPublishResult = $null
    $script:CurrentEncodeAttempts = @('stale')
    $script:CurrentSizePolicyResult = [pscustomobject]@{ stale = $true }
    $script:LastRemuxFallbackRejection = [pscustomobject]@{ stale = $true }
    $script:LastQualityVerification = [pscustomobject]@{ stale = $true }
    $script:CurrentDynamicHdrEvidence = [pscustomobject]@{ stale = $true }
    $script:pipelineStatus = 'Processing'
    $script:LocalBase = $root
    $script:MinFreeSpaceGB = 0
    $script:processingDir = $root
    $script:FfmpegReturn = $true
    $script:LastFfmpegCall = $null
}

try {
    Reset-EncodeHarness
    $context = New-MediaPipelineEncodeContext -File $script:SourceFile -IsTV:$false -TvInfo $null
    Assert-Equal $context.SafeName 'safe-source.mkv' 'Encode context safe name drifted.'
    foreach ($propertyName in @(
            'TempOut',
            'SubResult',
            'AudioArgs',
            'DefaultAudioLang',
            'VerifyRoute',
            'EncodePlan',
            'FfArgs',
            'WasteGuardContext',
            'UsingCpu',
            'UsingSafeRetry',
            'PushOk',
            'DynamicHdrForceCpuEncode',
            'DynamicHdrWorkingDirectory',
            'DynamicHdrTempFiles',
            'DynamicHdrDolbyVisionRpuPath',
            'DynamicHdrDolbyVisionTargetProfile',
            'DynamicHdrHdr10PlusJsonPath',
            'Hdr10MasterDisplay',
            'Hdr10MaxCll',
            'Hdr10Verification',
            'NormalizedEncoderBackend',
            'ForceCpuBackendEncode',
            'SkipGpuDueToProbe',
            'CpuFallbackEncoderName',
            'GlobalTitle',
            'PublishResult',
            'SizePolicyResult'
        )) {
        Assert-True ($null -ne $context.PSObject.Properties[$propertyName]) "Encode context must expose $propertyName for stage handoff."
    }
    Assert-Equal @($script:CurrentEncodeAttempts).Count 0 'Encode context should reset CurrentEncodeAttempts.'
    Assert-True ($null -eq $script:LastPublishResult) 'Encode context should clear LastPublishResult.'
    Assert-True ($null -eq $script:CurrentSizePolicyResult) 'Encode context should clear CurrentSizePolicyResult.'
    Assert-True ($null -eq $script:LastRemuxFallbackRejection) 'Encode context should clear LastRemuxFallbackRejection.'
    Assert-True ($null -eq $script:LastQualityVerification) 'Encode context should clear LastQualityVerification.'
    Assert-True ($null -eq $script:CurrentDynamicHdrEvidence) 'Encode context should clear CurrentDynamicHdrEvidence.'

    $preflight = Invoke-MediaPipelineEncodePreflight -Context $context
    Assert-False ([bool]$preflight.Terminal) 'Successful encode preflight should not be terminal.'
    Assert-Equal $context.LocalIn $script:ScratchPath 'Encode preflight scratch path drifted.'
    Assert-Equal $context.Paths.ServerOut $script:CurrentPaths.ServerOut 'Encode preflight output path drifted.'
    Assert-False ([bool]$context.IsHDR) 'Encode preflight HDR flag drifted for SDR source.'

    Reset-EncodeHarness -CreateExistingOutput:$true
    $context = New-MediaPipelineEncodeContext -File $script:SourceFile -IsTV:$false -TvInfo $null
    $preflight = Invoke-MediaPipelineEncodePreflight -Context $context
    Assert-True ([bool]$preflight.Terminal) 'Existing-output encode preflight should be terminal.'
    Assert-True ([bool]$preflight.Value) 'Existing-output encode preflight should return true.'
    Assert-Equal $script:LastPublishResult.PublishMode 'existing-output' 'Existing-output encode preflight should populate LastPublishResult.'
    Assert-Equal $context.LocalIn $script:ScratchPath 'Existing-output encode preflight should leave scratch cleanup to Do-Encode finally.'

    Reset-EncodeHarness -HdrProbeKnown:$false
    $context = New-MediaPipelineEncodeContext -File $script:SourceFile -IsTV:$false -TvInfo $null
    $preflight = Invoke-MediaPipelineEncodePreflight -Context $context
    Assert-True ([bool]$preflight.Terminal) 'HDR probe failure should be terminal.'
    Assert-False ([bool]$preflight.Value) 'HDR probe failure should return false.'
    Assert-True ($script:RegisteredFailures.ToArray() -contains 'hdr-detection') 'HDR probe failure should register hdr-detection evidence.'
    Assert-True ($null -eq $context.LocalIn) 'HDR probe failure should preserve scratch by nulling LocalIn like the original path.'

    Reset-EncodeHarness
    $attempt = New-MediaPipelineEncodeCoreAttemptPlan `
        -IsTV:$false `
        -IsHDR:$false `
        -InputPath $script:ScratchPath `
        -ExtraInputs @('sub.srt') `
        -GlobalTitle 'Encoded by MediaPipeline test' `
        -AudioArgs @('-map','0:a:0','-c:a:0','copy') `
        -SubtitleMapArgs @('-map','1:0','-c:s:0','srt') `
        -VideoFilterArgs @() `
        -OutputContainer 'mkv' `
        -VideoCodec 'hevc_nvenc' `
        -VideoPreset 'p7' `
        -VideoQuality 22 `
        -ExtraVideoFlags @('-profile:v','main10') `
        -FallbackCpuQuality 20 `
        -EncoderBackend 'auto' `
        -EncodeLadder 'quality' `
        -CpuPreset 'medium' `
        -CpuMaxThreads 4 `
        -Hdr10MasterDisplay '' `
        -Hdr10MaxCll '' `
        -TempPrefix 'encode_temp'
    Assert-True ([string]$attempt.OutputPath -like '*encode_temp_*.mkv') 'Primary encode attempt temp path drifted.'
    Assert-Equal $attempt.Plan.Label 'ENCODE' 'Primary encode plan label drifted.'
    $args = Get-MediaPipelineEncodeCommandArgumentList -Plan $attempt.Plan
    Assert-Equal $args[0] '-i' 'Encode command handoff should preserve plan argument list order.'
    Assert-Equal $args[-1] $attempt.OutputPath 'Encode command handoff should preserve output path as final argument.'

    $explicitPath = Join-Path $script:processingDir 'encode_temp_safe_explicit.mkv'
    $safeAttempt = New-MediaPipelineEncodeCoreAttemptPlan `
        -UseSafeHardwareRetry:$true `
        -IsTV:$false `
        -IsHDR:$false `
        -InputPath $script:ScratchPath `
        -OutputContainer 'mkv' `
        -VideoCodec 'hevc_nvenc' `
        -VideoPreset 'p7' `
        -VideoQuality 22 `
        -FallbackCpuQuality 20 `
        -EncoderBackend 'auto' `
        -EncodeLadder 'quality' `
        -CpuPreset 'medium' `
        -CpuMaxThreads 4 `
        -OutputPath $explicitPath
    Assert-Equal $safeAttempt.OutputPath $explicitPath 'Safe-retry encode attempt must honor explicit temp path.'
    Assert-Equal $safeAttempt.Plan.ReproStage 'encode-safe-retry' 'Safe-retry repro stage drifted.'

    $wasteGuard = [pscustomobject][ordered]@{ Enabled = $true }
    $ok = Invoke-MediaPipelineEncodeAttemptExecution -Plan $attempt.Plan -ArgumentList $args -InputPath $script:ScratchPath -OutputPath $attempt.OutputPath -TimeoutSeconds 123 -WasteGuardContext $wasteGuard
    Assert-True $ok 'Encode execution helper should return FFmpeg wrapper result.'
    Assert-Equal $script:LastFfmpegCall.Label 'ENCODE' 'Encode execution label drifted.'
    Assert-Equal $script:LastFfmpegCall.TimeoutSeconds 123 'Encode execution timeout drifted.'
    Assert-Equal $script:LastFfmpegCall.ProgressStage 'encode' 'Encode execution progress stage drifted.'
    Assert-Equal $script:LastFfmpegCall.ReproStage 'encode' 'Encode execution repro stage drifted.'
    Assert-Equal $script:LastFfmpegCall.OutputPath $attempt.OutputPath 'Encode execution output path drifted.'
    Assert-True ($script:LastFfmpegCall.WasteGuardContext -eq $wasteGuard) 'Encode execution waste guard context drifted.'

    # A completed temp encode must be the retained failure artifact when an
    # unexpected exception happens after FFmpeg. Re-registering the scratch
    # source and deleting TempOut would discard hours of valid encode work.
    function Invoke-MediaPipelineEncodePreflight {
        param($Context)
        $Context.LocalIn = $script:ScratchPath
        $Context.TempOut = $script:CompletedTempOutput
        throw 'simulated post-encode verification exception'
    }

    Reset-EncodeHarness
    $script:CompletedTempOutput = Join-Path $script:processingDir 'completed-temp-output.mkv'
    Set-Content -LiteralPath $script:CompletedTempOutput -Value 'completed encoded output' -NoNewline
    $encoded = Invoke-MediaPipelineEncode -file $script:SourceFile -isTV:$false -tvInfo $null
    Assert-False ([bool]$encoded) 'Unexpected post-encode exception should return a failed encode result.'
    Assert-Equal $script:RegisteredFailureScratchPaths[0] $script:CompletedTempOutput 'Unexpected post-encode exception must retain the completed temp output as failure evidence.'
    Assert-True (Test-Path -LiteralPath $script:CompletedTempOutput -PathType Leaf) 'Unexpected post-encode exception must not delete the completed temp output after it is handed to failure retention.'
    Assert-False (Test-Path -LiteralPath $script:ScratchPath -PathType Leaf) 'Scratch input should still be cleaned after the completed temp output is retained.'
} finally {
    foreach ($root in @($script:EncodeHarnessRoots.ToArray())) {
        if (-not [string]::IsNullOrWhiteSpace($root) -and $root.StartsWith([System.IO.Path]::GetTempPath(), [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host 'Encode core split checks passed.'
