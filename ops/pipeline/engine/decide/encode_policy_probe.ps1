# Extracted from ops/pipeline/engine/decide/encode_policy.ps1. Responsibility: NVENC descriptor probing and cache invalidation

function Test-NvencEncoderListMatch {
    param(
        [string] $EncoderListText = '',
        [string] $TestEncoder = 'hevc_nvenc'
    )

    $descriptor = Resolve-NvencProbeDescriptor -TestEncoder $TestEncoder
    if (Get-Command -Name Test-MediaEncoderDescriptorListMatch -ErrorAction SilentlyContinue) {
        return (Test-MediaEncoderDescriptorListMatch -EncoderListText ([string]$EncoderListText) -Descriptor $descriptor)
    }

    $escapedEncoder = [regex]::Escape(([string]$descriptor.ProbeEncoderName))
    return ([string]$EncoderListText -match "(?im)^\s*V[\.\w]+\s+$escapedEncoder\b")
}

function Resolve-NvencProbeDescriptor {
    param(
        [string] $TestEncoder = 'hevc_nvenc'
    )

    $encoder = if ($TestEncoder) { $TestEncoder.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($encoder)) { $encoder = 'hevc_nvenc' }

    $family = if (Get-Command -Name Resolve-MediaEncoderFamilyForCodec -ErrorAction SilentlyContinue) {
        Resolve-MediaEncoderFamilyForCodec -VideoCodec $encoder
    } else {
        ''
    }
    if ([string]::IsNullOrWhiteSpace($family)) {
        $family = 'unknown'
    }

    if ($family -ne 'unknown' -and (Get-Command -Name Get-MediaEncoderDescriptor -ErrorAction SilentlyContinue)) {
        $descriptor = Get-MediaEncoderDescriptor -Family $family -Backend 'nvenc'
        if ($descriptor -and ([string]$descriptor.ProbeEncoderName).Trim().ToLowerInvariant() -eq $encoder) {
            return $descriptor
        }
    }

    return [pscustomobject][ordered]@{
        EncoderName           = $encoder
        Family                = $family
        Backend               = 'nvenc'
        ProbeEncoderName      = $encoder
        SupportsHdr10Metadata = $false
    }
}

function Convert-DescriptorProbeToNvencProbeResult {
    param(
        [Parameter(Mandatory)] $ProbeResult,
        [Parameter(Mandatory)] $Descriptor,
        [string] $FfmpegPath = ''
    )

    return [pscustomobject][ordered]@{
        Available           = [bool]$ProbeResult.Available
        Probed              = [bool]$ProbeResult.Probed
        Reason              = [string]$ProbeResult.Reason
        EncoderListMatch    = [bool]$ProbeResult.EncoderListMatch
        RuntimeOk           = [bool]$ProbeResult.RuntimeOk
        ProbedAt            = if ($ProbeResult.PSObject.Properties['ProbedAt']) { [string]$ProbeResult.ProbedAt } else { (Get-Date).ToString('o') }
        RuntimeProbeSkipped = if ($ProbeResult.PSObject.Properties['RuntimeProbeSkipped']) { [bool]$ProbeResult.RuntimeProbeSkipped } else { $false }
        EncoderName         = if ($ProbeResult.PSObject.Properties['EncoderName']) { [string]$ProbeResult.EncoderName } else { [string]$Descriptor.EncoderName }
        Family              = if ($ProbeResult.PSObject.Properties['Family']) { [string]$ProbeResult.Family } else { [string]$Descriptor.Family }
        Backend             = if ($ProbeResult.PSObject.Properties['Backend']) { [string]$ProbeResult.Backend } else { [string]$Descriptor.Backend }
        ProbeEncoderName    = if ($ProbeResult.PSObject.Properties['ProbeEncoderName']) { [string]$ProbeResult.ProbeEncoderName } else { [string]$Descriptor.ProbeEncoderName }
        FfmpegPath          = [string]$FfmpegPath
        DescriptorProbeCache = $true
    }
}

function Test-NvencAvailable {
    <#
    .SYNOPSIS
    F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on
    this host, and cache the answer for the run.

    .DESCRIPTION
    Legacy wrapper over the descriptor-backed two-step probe: (1)
    `ffmpeg -encoders` must list the configured NVENC test encoder; (2)
    a 1-frame null encode with that descriptor verifies the driver and a
    usable GPU are present, which `-encoders` does not check.

    Returns a [pscustomobject] with:
      - Available  [bool]     final answer
      - Probed     [bool]     whether we reached the runtime probe
      - Reason     [string]   short human-readable cause
      - EncoderListMatch [bool]
      - RuntimeOk  [bool]

    The result is cached in `$script:NvencAvailableProbe` for the lifetime
    of the run. Pass -Force to re-probe.
    #>
    param(
        [string] $FfmpegPath = $script:ffmpegPath,
        [string] $TestEncoder = 'hevc_nvenc',
        [int]    $TimeoutSeconds = 15,
        [switch] $Force
    )

    $testEncoderName = if ($TestEncoder) { $TestEncoder.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($testEncoderName)) { $testEncoderName = 'hevc_nvenc' }
    $ffmpegPathKey = if ($FfmpegPath) { $FfmpegPath.Trim().ToLowerInvariant() } else { '' }

    if (-not $Force -and $script:NvencAvailableProbe) {
        if ($script:NvencAvailableProbe.PSObject.Properties['InvalidatedAt']) {
            return $script:NvencAvailableProbe
        }

        $cachedProbeEncoder = if ($script:NvencAvailableProbe.PSObject.Properties['ProbeEncoderName']) { ([string]$script:NvencAvailableProbe.ProbeEncoderName).Trim().ToLowerInvariant() } else { '' }
        $cachedFfmpegPath = if ($script:NvencAvailableProbe.PSObject.Properties['FfmpegPath']) { ([string]$script:NvencAvailableProbe.FfmpegPath).Trim().ToLowerInvariant() } else { '' }
        if ([string]::IsNullOrWhiteSpace($cachedProbeEncoder) -or ($cachedProbeEncoder -eq $testEncoderName -and $cachedFfmpegPath -eq $ffmpegPathKey)) {
            return $script:NvencAvailableProbe
        }
    }

    $descriptor = Resolve-NvencProbeDescriptor -TestEncoder $testEncoderName
    $probeArgs = @{
        Descriptor     = $descriptor
        FfmpegPath     = $FfmpegPath
        TimeoutSeconds = $TimeoutSeconds
    }
    if ($Force) { $probeArgs['Force'] = $true }

    $probeResult = Test-MediaEncoderDescriptorAvailable @probeArgs
    $script:NvencAvailableProbe = Convert-DescriptorProbeToNvencProbeResult -ProbeResult $probeResult -Descriptor $descriptor -FfmpegPath $FfmpegPath
    return $script:NvencAvailableProbe
}

function Invalidate-NvencAvailableProbe {
    <#
    .SYNOPSIS
    Mark the cached NVENC probe as unavailable after a runtime failure.

    .DESCRIPTION
    `Test-NvencAvailable` runs once at startup. Without this helper, a GPU
    that dies mid-run (driver crash, eGPU disconnect, Windows update) keeps
    causing every subsequent file to attempt NVENC primary + safe-retry
    before falling back. Once the second hardware-encoder failure has
    fired in `Do-Encode`, call this helper so the next file's
    `Do-Encode` sees `$script:NvencAvailableProbe.Available -eq $false`
    and goes directly to a CPU plan.

    The cache is in-memory ($script: scope) so a pipeline restart
    re-probes from scratch — operators who reboot to fix a flaky GPU
    don't need to clear anything by hand.
    #>
    param(
        [string] $Reason = '',
        [string] $SourcePath = ''
    )

    $previous = if ($script:NvencAvailableProbe) { [bool]$script:NvencAvailableProbe.Available } else { $true }
    $previousProbeEncoder = if ($script:NvencAvailableProbe -and $script:NvencAvailableProbe.PSObject.Properties['ProbeEncoderName']) { [string]$script:NvencAvailableProbe.ProbeEncoderName } else { 'hevc_nvenc' }
    $previousFfmpegPath = if ($script:NvencAvailableProbe -and $script:NvencAvailableProbe.PSObject.Properties['FfmpegPath']) { [string]$script:NvencAvailableProbe.FfmpegPath } else { '' }
    $previousFamily = if (Get-Command -Name Resolve-MediaEncoderFamilyForCodec -ErrorAction SilentlyContinue) {
        Resolve-MediaEncoderFamilyForCodec -VideoCodec $previousProbeEncoder
    } else {
        ''
    }
    $invalidationReason = if ([string]::IsNullOrWhiteSpace($Reason)) { 'NVENC failed at runtime; probe cache invalidated' } else { $Reason }
    $backendInvalidation = if (Get-Command -Name Invalidate-EncoderBackendProbe -ErrorAction SilentlyContinue) {
        Invalidate-EncoderBackendProbe -Backend 'nvenc' -Reason $invalidationReason -SourcePath $SourcePath -Trigger 'runtime_nvenc_failure'
    } else {
        $null
    }
    $script:NvencAvailableProbe = [pscustomobject]@{
        Available            = $false
        Probed               = $true
        Reason               = $invalidationReason
        EncoderListMatch     = $false
        RuntimeOk            = $false
        ProbedAt             = (Get-Date).ToString('o')
        RuntimeProbeSkipped  = $false
        EncoderName          = $previousProbeEncoder
        Family               = $previousFamily
        Backend              = 'nvenc'
        ProbeEncoderName     = $previousProbeEncoder
        FfmpegPath           = $previousFfmpegPath
        DescriptorProbeCache = $true
        BackendInvalidated   = $true
        InvalidatedAt        = if ($backendInvalidation -and $backendInvalidation.PSObject.Properties['InvalidatedAt']) { [string]$backendInvalidation.InvalidatedAt } else { (Get-Date).ToString('o') }
        Trigger              = 'runtime_nvenc_failure'
    }

    if ($previous -and -not $backendInvalidation) {
        Write-Log "NVENC probe cache invalidated: $($script:NvencAvailableProbe.Reason)" "WARN"
        if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
            Write-PipelineEvent -EventType 'gpu_unavailable' -Stage 'encode' -Status 'warn' -SourcePath $SourcePath -Data @{
                trigger = 'runtime_nvenc_failure'
                reason  = [string]$script:NvencAvailableProbe.Reason
                backend = 'nvenc'
            } | Out-Null
        }
    }
}

function Test-NvencProbeReportsAvailable {
    <#
    .SYNOPSIS
    Returns $true when the cached NVENC probe believes NVENC is usable.

    Default ($null cache) is $true so the first encode attempt still
    runs the normal GPU-first ladder. Once `Invalidate-NvencAvailableProbe`
    has been called, this returns $false and `Do-Encode` skips the
    GPU/safe-retry attempts entirely.
    #>
    if (-not $script:NvencAvailableProbe) { return $true }
    return [bool]$script:NvencAvailableProbe.Available
}
