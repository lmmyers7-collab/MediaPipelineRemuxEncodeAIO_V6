# Extracted from ops/pipeline/engine/decide/encoder_descriptors.ps1. Responsibility: capability reports and dynamic-HDR parameter shaping

function New-MediaEncoderCapabilityReport {
    param(
        [string] $VideoCodec = 'hevc_nvenc',
        [string] $EncoderBackend = 'auto',
        [string] $FfmpegPath = $(Get-Variable -Name ffmpegPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [int] $TimeoutSeconds = 15,
        [switch] $Force,
        [switch] $SkipHardwareRuntimeProbe
    )

    $selection = Resolve-MediaEncoderSelection -VideoCodec $VideoCodec -EncoderBackend $EncoderBackend
    # This diagnostic is deliberately narrow: it reports descriptor/list/runtime
    # probe facts, but does not inspect device drivers or certify playback.
    $resolvedConfigFingerprint = 'unavailable'
    $resolvedConfig = Get-Variable -Name config -Scope Script -ValueOnly -ErrorAction SilentlyContinue
    if ($null -ne $resolvedConfig) {
        try {
            $configJson = $resolvedConfig | ConvertTo-Json -Depth 32 -Compress
            $hashBytes = [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($configJson))
            $resolvedConfigFingerprint = ([System.BitConverter]::ToString($hashBytes)).Replace('-', '').ToLowerInvariant()
        } catch {
            $resolvedConfigFingerprint = 'unavailable'
        }
    }
    $ffmpegVersion = ''
    try {
        if (-not [string]::IsNullOrWhiteSpace($FfmpegPath) -and (Test-Path -LiteralPath $FfmpegPath -PathType Leaf)) {
            $ffmpegVersion = [string](Get-Item -LiteralPath $FfmpegPath).VersionInfo.FileVersion
        }
    } catch {
        $ffmpegVersion = ''
    }
    $descriptorMap = [ordered]@{}
    foreach ($candidate in @(
        [pscustomobject]@{ Role = 'primary';      Descriptor = $selection.PrimaryDescriptor },
        [pscustomobject]@{ Role = 'cpu_fallback'; Descriptor = $selection.CpuFallbackDescriptor }
    )) {
        if ($null -eq $candidate.Descriptor) { continue }
        $descriptor = $candidate.Descriptor
        $key = @(
            ([string]$descriptor.Family).Trim().ToLowerInvariant(),
            ([string]$descriptor.Backend).Trim().ToLowerInvariant(),
            ([string]$descriptor.EncoderName).Trim().ToLowerInvariant()
        ) -join '|'
        if (-not $descriptorMap.Contains($key)) {
            $descriptorMap[$key] = [ordered]@{
                Descriptor = $descriptor
                Roles      = @()
            }
        }
        if (@($descriptorMap[$key]['Roles']) -notcontains [string]$candidate.Role) {
            $descriptorMap[$key]['Roles'] = @($descriptorMap[$key]['Roles']) + [string]$candidate.Role
        }
    }

    $rows = @()
    $byEncoder = [ordered]@{}
    foreach ($key in @($descriptorMap.Keys)) {
        $entry = $descriptorMap[$key]
        $descriptor = $entry['Descriptor']
        $backend = ([string]$descriptor.Backend).Trim().ToLowerInvariant()
        $probeArgs = @{
            Descriptor     = $descriptor
            FfmpegPath     = $FfmpegPath
            TimeoutSeconds = $TimeoutSeconds
        }
        if ($Force) { $probeArgs['Force'] = $true }
        if ($SkipHardwareRuntimeProbe -and @('nvenc', 'qsv', 'amf') -contains $backend) {
            $probeArgs['SkipRuntimeProbe'] = $true
        }

        $probe = Test-MediaEncoderDescriptorAvailable @probeArgs
        $activationEvidence = Get-MediaEncoderDescriptorActivationEvidence `
            -Descriptor $descriptor `
            -Roles @($entry['Roles']) `
            -VideoCodec $VideoCodec `
            -EncoderBackend $EncoderBackend
        $backendInvalidated = if ($probe.PSObject.Properties['BackendInvalidated']) { [bool]$probe.BackendInvalidated } else { $false }
        $row = [ordered]@{
            encoder_name          = [string]$descriptor.EncoderName
            probe_encoder_name    = [string]$descriptor.ProbeEncoderName
            family                = [string]$descriptor.Family
            backend               = [string]$descriptor.Backend
            roles                 = @($entry['Roles'])
            descriptor_flags_active = [bool]$activationEvidence.ActiveForAttempts
            activation            = @($activationEvidence.Activation)
            available             = [bool]$probe.Available
            probed                = [bool]$probe.Probed
            runtime_probe_skipped = if ($probe.PSObject.Properties['RuntimeProbeSkipped']) { [bool]$probe.RuntimeProbeSkipped } else { $false }
            encoder_list_match    = [bool]$probe.EncoderListMatch
            runtime_ok            = [bool]$probe.RuntimeOk
            backend_invalidated   = $backendInvalidated
            reason                = [string]$probe.Reason
            probed_at             = if ($probe.PSObject.Properties['ProbedAt']) { [string]$probe.ProbedAt } else { '' }
        }
        $rows += [pscustomobject]$row
        $byEncoder[[string]$descriptor.EncoderName] = [ordered]@{
            available             = [bool]$row.available
            reason                = [string]$row.reason
            probed_at             = [string]$row.probed_at
            roles                 = @($row.roles)
            family                = [string]$row.family
            backend               = [string]$row.backend
            descriptor_flags_active = [bool]$row.descriptor_flags_active
            activation            = @($row.activation)
            runtime_probe_skipped = [bool]$row.runtime_probe_skipped
            backend_invalidated   = [bool]$row.backend_invalidated
        }
    }

    $primaryDescriptor = $selection.PrimaryDescriptor
    $cpuFallbackDescriptor = $selection.CpuFallbackDescriptor
    $runtimeProbeSkipped = @($rows | Where-Object { [bool]$_.runtime_probe_skipped }).Count -gt 0
    $runtimeProbeState = if ($runtimeProbeSkipped) { 'partial_or_skipped' } else { 'completed' }
    $invalidatedBackends = @($rows | Where-Object { [bool]$_.backend_invalidated } | ForEach-Object { [string]$_.backend } | Select-Object -Unique)

    return [pscustomobject][ordered]@{
        schema          = 'mediapipeline.encoder_capabilities.v2'
        generated_at    = (Get-Date).ToString('o')
        video_codec     = [string]$VideoCodec
        encoder_backend = [string]$EncoderBackend
        ffmpeg_path     = [string]$FfmpegPath
        selection       = [ordered]@{
            resolved = [bool]$selection.Resolved
            reason   = [string]$selection.Reason
            family   = [string]$selection.Family
        }
        encoders        = @($rows)
        by_encoder      = $byEncoder
        evidence        = [ordered]@{
            evidence_schema = 'mediapipeline.encoder_capability_evidence.v1'
            freshness       = [ordered]@{
                generated_at = (Get-Date).ToString('o')
                ttl_seconds  = 900
                posture      = 'availability_and_runtime_probe_only'
            }
            resolved_config = [ordered]@{ fingerprint = $resolvedConfigFingerprint }
            ffmpeg          = [ordered]@{
                path         = [string]$FfmpegPath
                file_version = $ffmpegVersion
                identity_state = if ([string]::IsNullOrWhiteSpace($ffmpegVersion)) { 'path_only' } else { 'path_and_file_version' }
            }
            host            = [ordered]@{
                device_facts_state = 'not_collected'
                driver_facts_state = 'not_collected'
                certification_state = 'not_certified'
            }
            selected_descriptor_chain = [ordered]@{
                primary = [ordered]@{
                    family = if ($null -ne $primaryDescriptor) { [string]$primaryDescriptor.Family } else { '' }
                    backend = if ($null -ne $primaryDescriptor) { [string]$primaryDescriptor.Backend } else { '' }
                    encoder = if ($null -ne $primaryDescriptor) { [string]$primaryDescriptor.EncoderName } else { '' }
                }
                cpu_fallback = [ordered]@{
                    family = if ($null -ne $cpuFallbackDescriptor) { [string]$cpuFallbackDescriptor.Family } else { '' }
                    backend = if ($null -ne $cpuFallbackDescriptor) { [string]$cpuFallbackDescriptor.Backend } else { '' }
                    encoder = if ($null -ne $cpuFallbackDescriptor) { [string]$cpuFallbackDescriptor.EncoderName } else { '' }
                }
            }
            activation_state = [ordered]@{
                selected_resolved = [bool]$selection.Resolved
                selected_reason   = [string]$selection.Reason
                active_encoder_count = @($rows | Where-Object { [bool]$_.descriptor_flags_active }).Count
            }
            list_probe_state    = 'completed'
            runtime_probe_state = $runtimeProbeState
            invalidation_state  = [ordered]@{
                invalidated = @($invalidatedBackends).Count -gt 0
                backends    = @($invalidatedBackends)
            }
            metadata_proof_state = 'not_collected'
            playback_proof_state = 'not_collected'
        }
    }
}

function Write-MediaEncoderCapabilityReport {
    param(
        [Parameter(Mandatory)] $Report,
        [Parameter(Mandatory)] [string] $Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw 'Encoder capability report path is required.'
    }
    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
        [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    }
    ($Report | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $Path -Encoding UTF8 -Force
    return $Path
}

function Test-DynamicHdrX265ParameterRequested {
    param(
        [string] $DolbyVisionRpuPath = '',
        [string] $Hdr10PlusJsonPath = ''
    )

    return (-not [string]::IsNullOrWhiteSpace($DolbyVisionRpuPath)) -or
        (-not [string]::IsNullOrWhiteSpace($Hdr10PlusJsonPath))
}

function Add-DynamicHdrX265ParameterPairs {
    param(
        [Parameter(Mandatory)] [System.Collections.Generic.List[string]] $ParamPairs,
        [string] $DolbyVisionRpuPath = '',
        [string] $DolbyVisionTargetProfile = '',
        [string] $Hdr10PlusJsonPath = ''
    )

    $doviPath = if ($DolbyVisionRpuPath) { $DolbyVisionRpuPath.Trim() } else { '' }
    $hdr10PlusPath = if ($Hdr10PlusJsonPath) { $Hdr10PlusJsonPath.Trim() } else { '' }
    if ([string]::IsNullOrWhiteSpace($doviPath) -and [string]::IsNullOrWhiteSpace($hdr10PlusPath)) {
        return
    }

    foreach ($path in @($doviPath, $hdr10PlusPath)) {
        if (-not [string]::IsNullOrWhiteSpace($path) -and ($path.Contains(':') -or [System.IO.Path]::IsPathRooted($path))) {
            throw 'Dynamic HDR x265 artifact paths must be relative and colon-free because x265 parameter parsing uses colon separators.'
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($doviPath)) {
        $targetProfile = if ($DolbyVisionTargetProfile) { $DolbyVisionTargetProfile.Trim() } else { '' }
        if ($targetProfile -ne '8.1') {
            throw "Dynamic HDR Dolby Vision x265 parameters currently support only target profile '8.1'."
        }
        $ParamPairs.Add('dolby-vision-profile=8.1')
        $ParamPairs.Add('vbv-maxrate=50000')
        $ParamPairs.Add('vbv-bufsize=50000')
    }

    if (-not [string]::IsNullOrWhiteSpace($hdr10PlusPath)) {
        $ParamPairs.Add("dhdr10-info=$hdr10PlusPath")
    }
}
