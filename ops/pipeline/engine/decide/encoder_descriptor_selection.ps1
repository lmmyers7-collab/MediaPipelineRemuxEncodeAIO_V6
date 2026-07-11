# Extracted from ops/pipeline/engine/decide/encoder_descriptors.ps1. Responsibility: selection traces, activation evidence, and availability probes

function Test-MediaEncoderCapabilityProbeValue {
    param(
        $ProbeResult
    )

    if ($null -eq $ProbeResult) { return $false }
    if ($ProbeResult -is [bool]) { return [bool]$ProbeResult }
    if ($ProbeResult.PSObject.Properties['Available']) { return [bool]$ProbeResult.Available }
    if ($ProbeResult.PSObject.Properties['RuntimeOk']) { return [bool]$ProbeResult.RuntimeOk }
    return $false
}

function Resolve-MediaEncoderSelection {
    param(
        [string] $VideoCodec = '',
        [string] $EncoderBackend = 'auto',
        [bool] $IsHDR = $false,
        [scriptblock] $CapabilityProbe = $null
    )

    $codec = if ($VideoCodec) { $VideoCodec.Trim().ToLowerInvariant() } else { '' }
    $backend = if ($EncoderBackend) { $EncoderBackend.Trim().ToLowerInvariant() } else { 'auto' }
    if ([string]::IsNullOrWhiteSpace($backend)) { $backend = 'auto' }
    $trace = @()
    $result = [pscustomobject][ordered]@{
        Resolved              = $false
        Reason                = ''
        VideoCodec            = [string]$VideoCodec
        EncoderBackend        = [string]$backend
        Family                = ''
        PrimaryDescriptor     = $null
        CpuFallbackDescriptor = $null
        ResolutionTrace       = @()
    }

    $family = Resolve-MediaEncoderFamilyForCodec -VideoCodec $codec
    $result.Family = [string]$family
    if ([string]::IsNullOrWhiteSpace($family)) {
        $result.Reason = "unsupported encoder family for codec '$VideoCodec'"
        $trace += New-MediaEncoderSelectionTraceEntry -Stage 'family' -Status 'blocked' -Message $result.Reason
        $result.ResolutionTrace = @($trace)
        return $result
    }
    $trace += New-MediaEncoderSelectionTraceEntry -Stage 'family' -Status 'resolved' -Message "resolved family '$family'" -Family $family

    $fallback = Resolve-MediaEncoderCpuFallbackDescriptor -VideoCodec $codec -IsHDR:$IsHDR
    if ($fallback.Descriptor -and -not [bool]$fallback.HdrBlocked) {
        $result.CpuFallbackDescriptor = $fallback.Descriptor
        $trace += New-MediaEncoderSelectionTraceEntry -Stage 'cpu_fallback' -Status 'resolved' -Message $fallback.Reason -Descriptor $fallback.Descriptor
    } elseif ($fallback.HdrBlocked) {
        $trace += New-MediaEncoderSelectionTraceEntry -Stage 'cpu_fallback' -Status 'blocked' -Message $fallback.Reason -Family $family -Backend 'cpu' -EncoderName ([string]$fallback.EncoderName)
    } else {
        $trace += New-MediaEncoderSelectionTraceEntry -Stage 'cpu_fallback' -Status 'blocked' -Message $fallback.Reason -Family $family -Backend 'cpu'
    }

    $primaryBackend = ''
    if ($backend -eq 'auto') {
        $primaryBackend = Resolve-MediaEncoderBackendForCodec -VideoCodec $codec
        if ([string]::IsNullOrWhiteSpace($primaryBackend)) {
            $result.Reason = "unsupported encoder backend for codec '$VideoCodec'"
            $trace += New-MediaEncoderSelectionTraceEntry -Stage 'primary' -Status 'blocked' -Message $result.Reason -Family $family
            $result.Resolved = $false
            $result.CpuFallbackDescriptor = $null
            $result.ResolutionTrace = @($trace)
            return $result
        }
    } elseif ($backend -in @('cpu', 'nvenc', 'qsv', 'amf')) {
        $primaryBackend = $backend
    } else {
        $result.Reason = "unsupported encoder backend '$EncoderBackend'"
        $trace += New-MediaEncoderSelectionTraceEntry -Stage 'primary' -Status 'blocked' -Message $result.Reason -Family $family
        $result.Resolved = $false
        $result.CpuFallbackDescriptor = $null
        $result.ResolutionTrace = @($trace)
        return $result
    }

    $primary = Get-MediaEncoderDescriptor -Family $family -Backend $primaryBackend
    if ($null -eq $primary) {
        $result.Reason = "missing primary descriptor for '$family/$primaryBackend'"
        $trace += New-MediaEncoderSelectionTraceEntry -Stage 'primary' -Status 'blocked' -Message $result.Reason -Family $family -Backend $primaryBackend
        $result.Resolved = $false
        $result.ResolutionTrace = @($trace)
        return $result
    }

    if ($backend -eq 'auto' -and $primaryBackend -eq 'cpu' -and ([string]$primary.EncoderName).Trim().ToLowerInvariant() -ne $codec) {
        $result.Reason = "literal CPU codec '$VideoCodec' does not match descriptor encoder '$($primary.EncoderName)'"
        $trace += New-MediaEncoderSelectionTraceEntry -Stage 'primary' -Status 'blocked' -Message $result.Reason -Descriptor $primary
        $result.Resolved = $false
        $result.ResolutionTrace = @($trace)
        return $result
    }

    if ($IsHDR -and -not [bool]$primary.SupportsHdr10Metadata) {
        $result.Reason = "primary descriptor '$family/$primaryBackend' does not support HDR10 metadata preservation"
        $trace += New-MediaEncoderSelectionTraceEntry -Stage 'primary' -Status 'blocked' -Message $result.Reason -Descriptor $primary
        $result.Resolved = ($null -ne $result.CpuFallbackDescriptor)
        $result.ResolutionTrace = @($trace)
        return $result
    }

    if ($CapabilityProbe -and $primaryBackend -ne 'cpu') {
        $probeResult = & $CapabilityProbe $primary
        if (-not (Test-MediaEncoderCapabilityProbeValue -ProbeResult $probeResult)) {
            $probeReason = if ($probeResult -and $probeResult.PSObject.Properties['Reason']) { [string]$probeResult.Reason } else { "capability probe rejected '$($primary.EncoderName)'" }
            $result.Reason = $probeReason
            $trace += New-MediaEncoderSelectionTraceEntry -Stage 'capability' -Status 'blocked' -Message $probeReason -Descriptor $primary
            $result.Resolved = ($null -ne $result.CpuFallbackDescriptor)
            $result.ResolutionTrace = @($trace)
            return $result
        }
        $trace += New-MediaEncoderSelectionTraceEntry -Stage 'capability' -Status 'available' -Message "capability probe accepted '$($primary.EncoderName)'" -Descriptor $primary
    }

    $result.PrimaryDescriptor = $primary
    $result.Resolved = $true
    $result.Reason = "resolved primary descriptor '$family/$primaryBackend'"
    $trace += New-MediaEncoderSelectionTraceEntry -Stage 'primary' -Status 'resolved' -Message $result.Reason -Descriptor $primary
    $result.ResolutionTrace = @($trace)
    return $result
}

function Get-MediaEncoderDescriptorActivationEvidence {
    param(
        [Parameter(Mandatory)] $Descriptor,
        [AllowEmptyCollection()] [array] $Roles = @(),
        [string] $VideoCodec = '',
        [string] $EncoderBackend = 'auto'
    )

    $activationRows = @()
    $activeForAttempts = $false
    foreach ($rawRole in @($Roles)) {
        $role = if ($rawRole) { ([string]$rawRole).Trim().ToLowerInvariant() } else { '' }
        if ([string]::IsNullOrWhiteSpace($role)) { continue }
        $useCpuFallback = $role -eq 'cpu_fallback'
        if ($role -notin @('primary', 'cpu_fallback')) {
            $activationRows += [pscustomobject][ordered]@{
                role                      = $role
                active                    = $false
                descriptor_encoder        = [string]$Descriptor.EncoderName
                active_descriptor_encoder = ''
                reason                    = "unknown descriptor role '$role'"
            }
            continue
        }

        $activeFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec $VideoCodec -UseCpuFallback:$useCpuFallback -EncoderBackend $EncoderBackend
        if ($null -eq $activeFlagsDescriptor) {
            $activationRows += [pscustomobject][ordered]@{
                role                      = $role
                active                    = $false
                descriptor_encoder        = [string]$Descriptor.EncoderName
                active_descriptor_encoder = ''
                reason                    = "descriptor flags are not active for $role attempt"
            }
            continue
        }

        $descriptorEncoder = ([string]$Descriptor.EncoderName).Trim().ToLowerInvariant()
        $activeEncoder = ([string]$activeFlagsDescriptor.EncoderName).Trim().ToLowerInvariant()
        $isActive = $descriptorEncoder -eq $activeEncoder
        if ($isActive) { $activeForAttempts = $true }
        $activationRows += [pscustomobject][ordered]@{
            role                      = $role
            active                    = [bool]$isActive
            descriptor_encoder        = [string]$Descriptor.EncoderName
            active_descriptor_encoder = [string]$activeFlagsDescriptor.EncoderName
            reason                    = if ($isActive) {
                "descriptor-owned flags are active for $role attempt"
            } else {
                "active descriptor encoder '$($activeFlagsDescriptor.EncoderName)' does not match '$($Descriptor.EncoderName)' for $role attempt"
            }
        }
    }

    return [pscustomobject][ordered]@{
        ActiveForAttempts = [bool]$activeForAttempts
        Activation        = @($activationRows)
    }
}

function Get-MediaEncoderDescriptorProbeCacheKey {
    param(
        [Parameter(Mandatory)] $Descriptor,
        [string] $FfmpegPath = '',
        [bool] $SkipRuntimeProbe = $false
    )

    $pathKey = if ($FfmpegPath) { $FfmpegPath.Trim().ToLowerInvariant() } else { '' }
    $probeMode = if ($SkipRuntimeProbe) { 'list' } else { 'runtime' }
    return @(
        ([string]$Descriptor.Family).Trim().ToLowerInvariant(),
        ([string]$Descriptor.Backend).Trim().ToLowerInvariant(),
        ([string]$Descriptor.ProbeEncoderName).Trim().ToLowerInvariant(),
        $probeMode,
        $pathKey
    ) -join '|'
}

function Test-MediaEncoderDescriptorListMatch {
    param(
        [Parameter(Mandatory)] [string] $EncoderListText,
        [Parameter(Mandatory)] $Descriptor
    )

    $probeEncoder = ([string]$Descriptor.ProbeEncoderName).Trim()
    if ([string]::IsNullOrWhiteSpace($probeEncoder)) { return $false }
    $escaped = [regex]::Escape($probeEncoder)
    return ($EncoderListText -match "(?im)^\s*V[\.\w]+\s+$escaped\b")
}

function New-MediaEncoderDescriptorProbeArgumentList {
    param(
        [Parameter(Mandatory)] $Descriptor
    )

    return @(
        '-hide_banner', '-loglevel', 'error',
        '-f', 'lavfi', '-i', 'color=c=black:s=256x144:r=1',
        '-frames:v', '1',
        '-c:v', [string]$Descriptor.ProbeEncoderName,
        '-f', 'null', '-'
    )
}

function Invalidate-EncoderBackendProbe {
    param(
        [Parameter(Mandatory)] [string] $Backend,
        [string] $Reason = '',
        [string] $SourcePath = '',
        [string] $Trigger = 'runtime_encoder_failure',
        [switch] $SuppressEvent
    )

    $backendName = if ($Backend) { $Backend.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($backendName)) {
        throw 'Encoder backend is required for probe invalidation.'
    }
    if ([string]::IsNullOrWhiteSpace($Reason)) {
        $Reason = "encoder backend '$backendName' failed at runtime; probe cache invalidated"
    }
    if ([string]::IsNullOrWhiteSpace($Trigger)) {
        $Trigger = 'runtime_encoder_failure'
    }

    if (-not $script:EncoderDescriptorBackendInvalidations) {
        $script:EncoderDescriptorBackendInvalidations = @{}
    }
    if (-not $script:EncoderDescriptorCapabilityProbeCache) {
        $script:EncoderDescriptorCapabilityProbeCache = @{}
    }

    $alreadyInvalidated = $script:EncoderDescriptorBackendInvalidations.ContainsKey($backendName)
    $invalidation = [pscustomobject][ordered]@{
        Available           = $false
        Probed              = $true
        RuntimeProbeSkipped = $false
        Reason              = [string]$Reason
        EncoderListMatch    = $false
        RuntimeOk           = $false
        EncoderName         = ''
        Family              = ''
        Backend             = $backendName
        ProbeEncoderName    = ''
        ProbedAt            = (Get-Date).ToString('o')
        InvalidatedAt       = (Get-Date).ToString('o')
        Trigger             = [string]$Trigger
        BackendInvalidated  = $true
    }
    $script:EncoderDescriptorBackendInvalidations[$backendName] = $invalidation

    foreach ($key in @($script:EncoderDescriptorCapabilityProbeCache.Keys)) {
        $parts = ([string]$key) -split '\|'
        if ($parts.Count -ge 2 -and $parts[1] -eq $backendName) {
            $script:EncoderDescriptorCapabilityProbeCache.Remove($key)
        }
    }

    if (-not $SuppressEvent -and -not $alreadyInvalidated) {
        if (Get-Command -Name Write-Log -ErrorAction SilentlyContinue) {
            Write-Log "Encoder backend probe cache invalidated for ${backendName}: $Reason" "WARN"
        }
        if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
            Write-PipelineEvent -EventType 'gpu_unavailable' -Stage 'encode' -Status 'warn' -SourcePath $SourcePath -Data @{
                trigger = [string]$Trigger
                reason  = [string]$Reason
                backend = $backendName
            } | Out-Null
        }
    }

    return $invalidation
}

function Test-MediaEncoderDescriptorAvailable {
    param(
        [Parameter(Mandatory)] $Descriptor,
        [string] $FfmpegPath = $(Get-Variable -Name ffmpegPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [int] $TimeoutSeconds = 15,
        [switch] $Force,
        [switch] $SkipRuntimeProbe
    )

    if (-not $script:EncoderDescriptorCapabilityProbeCache) {
        $script:EncoderDescriptorCapabilityProbeCache = @{}
    }
    $cacheKey = Get-MediaEncoderDescriptorProbeCacheKey -Descriptor $Descriptor -FfmpegPath $FfmpegPath -SkipRuntimeProbe ([bool]$SkipRuntimeProbe)
    $backendName = ([string]$Descriptor.Backend).Trim().ToLowerInvariant()
    if (-not $Force -and $script:EncoderDescriptorBackendInvalidations -and $script:EncoderDescriptorBackendInvalidations.ContainsKey($backendName)) {
        $invalidation = $script:EncoderDescriptorBackendInvalidations[$backendName]
        $invalidatedResult = [pscustomobject][ordered]@{
            Available           = $false
            Probed              = $true
            RuntimeProbeSkipped = $false
            Reason              = [string]$invalidation.Reason
            EncoderListMatch    = $false
            RuntimeOk           = $false
            EncoderName         = [string]$Descriptor.EncoderName
            Family              = [string]$Descriptor.Family
            Backend             = [string]$Descriptor.Backend
            ProbeEncoderName    = [string]$Descriptor.ProbeEncoderName
            ProbedAt            = (Get-Date).ToString('o')
            InvalidatedAt       = if ($invalidation.PSObject.Properties['InvalidatedAt']) { [string]$invalidation.InvalidatedAt } else { (Get-Date).ToString('o') }
            Trigger             = if ($invalidation.PSObject.Properties['Trigger']) { [string]$invalidation.Trigger } else { 'runtime_encoder_failure' }
            BackendInvalidated  = $true
        }
        $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $invalidatedResult
        return $invalidatedResult
    }
    if (-not $Force -and $script:EncoderDescriptorCapabilityProbeCache.ContainsKey($cacheKey)) {
        return $script:EncoderDescriptorCapabilityProbeCache[$cacheKey]
    }

    $result = [pscustomobject][ordered]@{
        Available           = $false
        Probed              = $false
        RuntimeProbeSkipped = $false
        Reason              = ''
        EncoderListMatch    = $false
        RuntimeOk           = $false
        EncoderName         = [string]$Descriptor.EncoderName
        Family              = [string]$Descriptor.Family
        Backend             = [string]$Descriptor.Backend
        ProbeEncoderName    = [string]$Descriptor.ProbeEncoderName
        ProbedAt            = (Get-Date).ToString('o')
    }

    if ([string]::IsNullOrWhiteSpace($FfmpegPath) -or -not (Test-Path -LiteralPath $FfmpegPath -PathType Leaf)) {
        $result.Reason = "ffmpeg not found at '$FfmpegPath'"
        $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
        return $result
    }

    try {
        $listOut = & $FfmpegPath -hide_banner -encoders 2>&1
        if ($LASTEXITCODE -ne 0) {
            $result.Reason = "ffmpeg -encoders exited $LASTEXITCODE"
            $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
            return $result
        }
        $listText = ($listOut | Out-String)
        $result.EncoderListMatch = Test-MediaEncoderDescriptorListMatch -EncoderListText $listText -Descriptor $Descriptor
        if (-not $result.EncoderListMatch) {
            $result.Reason = "ffmpeg build does not list encoder '$($result.ProbeEncoderName)'"
            $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
            return $result
        }
    } catch {
        $result.Reason = "ffmpeg -encoders threw: $($_.Exception.Message)"
        $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
        return $result
    }

    if ($SkipRuntimeProbe) {
        $result.RuntimeProbeSkipped = $true
        $result.Reason = "encoder '$($result.ProbeEncoderName)' is listed; runtime availability not confirmed because probe was skipped"
        $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
        return $result
    }

    $result.Probed = $true
    try {
        $proc = [System.Diagnostics.Process]::new()
        $psi = [System.Diagnostics.ProcessStartInfo]@{
            FileName               = $FfmpegPath
            UseShellExecute        = $false
            RedirectStandardError  = $true
            RedirectStandardOutput = $true
            CreateNoWindow         = $true
        }
        foreach ($arg in (New-MediaEncoderDescriptorProbeArgumentList -Descriptor $Descriptor)) {
            $psi.ArgumentList.Add([string]$arg)
        }
        $proc.StartInfo = $psi
        [void]$proc.Start()
        $stderrTask = $proc.StandardError.ReadToEndAsync()
        if (-not $proc.WaitForExit([int]([math]::Max(1, $TimeoutSeconds)) * 1000)) {
            try { $proc.Kill() } catch {}
            $result.Reason = "encoder '$($result.ProbeEncoderName)' probe timed out after ${TimeoutSeconds}s"
            $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
            return $result
        }
        $stderrText = ''
        try { $stderrText = $stderrTask.Result } catch {}
        if ($proc.ExitCode -eq 0) {
            $result.RuntimeOk = $true
            $result.Available = $true
            $result.Reason = "encoder '$($result.ProbeEncoderName)' probe succeeded"
            if ($Force -and $script:EncoderDescriptorBackendInvalidations -and $script:EncoderDescriptorBackendInvalidations.ContainsKey($backendName)) {
                $script:EncoderDescriptorBackendInvalidations.Remove($backendName)
            }
        } else {
            $tail = ($stderrText -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -Last 1)
            $result.Reason = "encoder '$($result.ProbeEncoderName)' probe exit $($proc.ExitCode): $tail"
        }
    } catch {
        $result.Reason = "encoder '$($result.ProbeEncoderName)' probe threw: $($_.Exception.Message)"
    }

    $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
    return $result
}
