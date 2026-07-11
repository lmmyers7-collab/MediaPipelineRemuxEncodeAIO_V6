# Extracted from ops/pipeline/engine/process/dynamic_hdr.ps1. Responsibility: x265 artifacts and output preservation validation

function ConvertTo-DynamicHdrX265RelativePath {
    param(
        [string] $ArtifactPath,
        [string] $BaseDirectory
    )

    if ([string]::IsNullOrWhiteSpace($ArtifactPath)) { return '' }
    if ([string]::IsNullOrWhiteSpace($BaseDirectory)) { return '' }

    $baseFull = [System.IO.Path]::GetFullPath($BaseDirectory)
    $artifactFull = [System.IO.Path]::GetFullPath($ArtifactPath)
    $relative = [System.IO.Path]::GetRelativePath($baseFull, $artifactFull)
    if ([string]::IsNullOrWhiteSpace($relative)) { return '' }
    return [string]$relative
}

function Resolve-DynamicHdrX265ArtifactPaths {
    [CmdletBinding()]
    param(
        $ExtractionResult,
        [string] $BaseDirectory = $(Get-Location).Path
    )

    $base = [ordered]@{
        schema_version          = 'dynamic_hdr_x265_artifact_paths.v1'
        ok                      = $false
        required                = $false
        reason                  = ''
        error_code              = ''
        base_directory          = [string]$BaseDirectory
        rpu_source_path         = ''
        hdr10plus_source_path   = ''
        dolby_vision_rpu_path   = ''
        hdr10plus_json_path     = ''
        target_dovi_profile     = ''
        rpu_frame_count         = 0
    }

    if ($null -eq $ExtractionResult) {
        $base.reason = 'dynamic HDR extraction result is required before x265 artifact path resolution'
        $base.error_code = 'DYNAMIC_HDR_EXTRACTION_RESULT_MISSING'
        return [pscustomobject]$base
    }

    if (-not [bool](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'ok')) {
        $base.reason = [string](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'reason')
        $base.error_code = [string](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'error_code')
        return [pscustomobject]$base
    }

    if ([string]::IsNullOrWhiteSpace($BaseDirectory)) {
        $base.reason = 'base directory is required to convert dynamic HDR artifact paths for x265'
        $base.error_code = 'DYNAMIC_HDR_X265_PATH_BASE_MISSING'
        return [pscustomobject]$base
    }

    $base.target_dovi_profile = [string](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'target_dovi_profile')
    $base.rpu_frame_count = [int](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'rpu_frame_count')
    $base.rpu_source_path = [string](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'rpu_path')
    $base.hdr10plus_source_path = [string](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'hdr10plus_json_path')

    $artifactSpecs = @(
        @{ Kind = 'dolby_vision_rpu'; Source = [string]$base.rpu_source_path; MissingCode = 'DOVI_RPU_EXTRACT_FAILED' },
        @{ Kind = 'hdr10plus_json'; Source = [string]$base.hdr10plus_source_path; MissingCode = 'HDR10PLUS_EXTRACT_FAILED' }
    )
    $requiredCount = 0
    foreach ($artifact in $artifactSpecs) {
        if ([string]::IsNullOrWhiteSpace([string]$artifact.Source)) { continue }
        $requiredCount++

        try {
            $relativePath = ConvertTo-DynamicHdrX265RelativePath -ArtifactPath ([string]$artifact.Source) -BaseDirectory $BaseDirectory
        } catch {
            $base.reason = "dynamic HDR artifact path '$($artifact.Source)' cannot be converted to a relative x265 path: $($_.Exception.Message)"
            $base.error_code = 'DYNAMIC_HDR_X265_PATH_UNREPRESENTABLE'
            return [pscustomobject]$base
        }

        if ([string]::IsNullOrWhiteSpace($relativePath) -or
            [System.IO.Path]::IsPathRooted($relativePath) -or
            $relativePath.Contains(':')) {
            $base.reason = "dynamic HDR artifact path '$($artifact.Source)' is not representable as a relative, colon-free x265 parameter path from '$BaseDirectory'"
            $base.error_code = 'DYNAMIC_HDR_X265_PATH_UNREPRESENTABLE'
            return [pscustomobject]$base
        }

        if (-not (Test-DynamicHdrArtifactPresent -Path ([string]$artifact.Source))) {
            $base.reason = "dynamic HDR artifact '$($artifact.Source)' is missing or empty before x265 path resolution"
            $base.error_code = [string]$artifact.MissingCode
            return [pscustomobject]$base
        }

        if ([string]$artifact.Kind -eq 'dolby_vision_rpu') {
            $base.dolby_vision_rpu_path = $relativePath
        } elseif ([string]$artifact.Kind -eq 'hdr10plus_json') {
            $base.hdr10plus_json_path = $relativePath
        }
    }

    $base.required = ($requiredCount -gt 0)
    $base.ok = $true
    $base.reason = if ($base.required) { 'dynamic HDR x265 artifact paths are ready' } else { 'no dynamic HDR x265 artifact paths are required' }
    return [pscustomobject]$base
}

function Test-DynamicHdrOutputPreservation {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] $SourceEvidence,
        [Parameter(Mandatory)] [string] $OutputPath,
        [int] $ExpectedRpuFrameCount = 0
    )

    $expectedDovi = [bool](Get-DynamicHdrResultValue -Result $SourceEvidence -Name 'dovi_present')
    $expectedHdr10Plus = [bool](Get-DynamicHdrResultValue -Result $SourceEvidence -Name 'hdr10plus_present')
    $expectedProfile = ''
    $x265Artifacts = Get-DynamicHdrResultValue -Result $SourceEvidence -Name 'x265_artifacts'
    if ($null -ne $x265Artifacts) {
        $expectedProfile = [string](Get-DynamicHdrResultValue -Result $x265Artifacts -Name 'target_dovi_profile')
    }

    $base = [ordered]@{
        schema_version             = 'dynamic_hdr_output_verification.v1'
        checked                    = $true
        ok                         = $false
        reason                     = ''
        error_code                 = ''
        output_path                = [string]$OutputPath
        expected_dovi_present      = [bool]$expectedDovi
        expected_hdr10plus_present = [bool]$expectedHdr10Plus
        expected_dovi_profile      = [string]$expectedProfile
        output_dovi_present        = $false
        output_dovi_profile        = 0
        output_dovi_bl_compat_id   = -1
        output_hdr10plus_present   = $false
        expected_frame_count       = [int]$ExpectedRpuFrameCount
        rpu_frame_count            = 0
        dovi_state                 = $null
        hdr10plus_state            = $null
    }

    if (-not $expectedDovi -and -not $expectedHdr10Plus) {
        $base.ok = $true
        $base.reason = 'no Dynamic HDR metadata was expected in output'
        return [pscustomobject]$base
    }
    if ([string]::IsNullOrWhiteSpace($OutputPath) -or -not (Test-Path -LiteralPath $OutputPath -PathType Leaf)) {
        $base.reason = 'output path is missing for Dynamic HDR verification'
        $base.error_code = 'DYNAMIC_HDR_OUTPUT_VERIFY_FAILED'
        return [pscustomobject]$base
    }
    if (-not (Get-Command Get-DolbyVisionState -ErrorAction SilentlyContinue) -or
        -not (Get-Command Test-Hdr10PlusPresence -ErrorAction SilentlyContinue)) {
        $base.reason = 'Dynamic HDR output probe helpers are unavailable'
        $base.error_code = 'DYNAMIC_HDR_OUTPUT_VERIFY_UNKNOWN'
        return [pscustomobject]$base
    }

    $doviState = Get-DolbyVisionState -FilePath $OutputPath
    $hdr10PlusState = Test-Hdr10PlusPresence -FilePath $OutputPath
    $base.dovi_state = $doviState
    $base.hdr10plus_state = $hdr10PlusState
    $base.output_dovi_present = [bool](Get-DynamicHdrResultValue -Result $doviState -Name 'DoviPresent')
    $base.output_dovi_profile = [int](Get-DynamicHdrResultValue -Result $doviState -Name 'DoviProfile')
    $base.output_dovi_bl_compat_id = [int](Get-DynamicHdrResultValue -Result $doviState -Name 'DoviBlCompatId')
    $base.output_hdr10plus_present = [bool](Get-DynamicHdrResultValue -Result $hdr10PlusState -Name 'Hdr10PlusPresent')

    if ($expectedDovi -and -not [bool](Get-DynamicHdrResultValue -Result $doviState -Name 'Known')) {
        $base.reason = "Dolby Vision output verification was inconclusive: $([string](Get-DynamicHdrResultValue -Result $doviState -Name 'Reason'))"
        $base.error_code = 'DYNAMIC_HDR_OUTPUT_VERIFY_UNKNOWN'
        return [pscustomobject]$base
    }
    if ($expectedHdr10Plus -and -not [bool](Get-DynamicHdrResultValue -Result $hdr10PlusState -Name 'Known')) {
        $base.reason = "HDR10+ output verification was inconclusive: $([string](Get-DynamicHdrResultValue -Result $hdr10PlusState -Name 'Reason'))"
        $base.error_code = 'DYNAMIC_HDR_OUTPUT_VERIFY_UNKNOWN'
        return [pscustomobject]$base
    }
    if ($expectedDovi -and -not [bool]$base.output_dovi_present) {
        $base.reason = 'expected Dolby Vision metadata was not detected in encoded output'
        $base.error_code = 'DYNAMIC_HDR_OUTPUT_METADATA_MISSING'
        return [pscustomobject]$base
    }
    if ($expectedProfile -eq '8.1' -and ([int]$base.output_dovi_profile -ne 8 -or [int]$base.output_dovi_bl_compat_id -ne 1)) {
        $base.reason = "expected Dolby Vision profile 8.1 output, got profile $($base.output_dovi_profile) BL compatibility $($base.output_dovi_bl_compat_id)"
        $base.error_code = 'DYNAMIC_HDR_OUTPUT_METADATA_MISSING'
        return [pscustomobject]$base
    }
    if ($expectedHdr10Plus -and -not [bool]$base.output_hdr10plus_present) {
        $base.reason = 'expected HDR10+ metadata was not detected in encoded output'
        $base.error_code = 'DYNAMIC_HDR_OUTPUT_METADATA_MISSING'
        return [pscustomobject]$base
    }

    $base.ok = $true
    $base.reason = 'expected Dynamic HDR metadata was detected in encoded output'
    return [pscustomobject]$base
}

function Clear-DynamicHdrCapabilityProbe {
    $script:X265DynamicHdrCapabilityCache = $null
}

function Test-X265DynamicHdrCapability {
    [CmdletBinding()]
    param(
        [string] $FfmpegPath = $(Get-Variable -Name ffmpegPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [string] $DoviRpuFixturePath = '',
        [string] $Hdr10PlusJsonFixturePath = '',
        [switch] $Force
    )

    if (-not $Force -and $script:X265DynamicHdrCapabilityCache) {
        return $script:X265DynamicHdrCapabilityCache
    }

    $reasonParts = [System.Collections.Generic.List[string]]::new()
    $probed = $false
    $dolbyVision = $false
    $hdr10Plus = $false
    $doviProbe = $null
    $hdr10PlusProbe = $null
    if ([string]::IsNullOrWhiteSpace($FfmpegPath) -or -not (Test-Path -LiteralPath $FfmpegPath -PathType Leaf)) {
        $reasonParts.Add("ffmpeg not found: $FfmpegPath")
    } else {
        $probeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-x265-dhdr-capability-{0}" -f ([guid]::NewGuid().ToString('N')))
        [System.IO.Directory]::CreateDirectory($probeRoot) | Out-Null
        try {
            function Invoke-X265DolbyVisionCapabilityProbe {
                $result = [ordered]@{
                    feature      = 'dovi'
                    supplied     = -not [string]::IsNullOrWhiteSpace($DoviRpuFixturePath)
                    probed       = $false
                    ok           = $false
                    exit_code    = -1
                    reason       = ''
                    fixture_leaf = ''
                    probe_type   = 'ffmpeg_encoder_help'
                    output_tail  = ''
                }

                $helpOutput = & $FfmpegPath @('-hide_banner', '-h', 'encoder=libx265') 2>&1
                $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
                $outputText = (@($helpOutput) | ForEach-Object { [string]$_ }) -join "`n"
                $result.probed = $true
                $result.exit_code = $exitCode
                $result.output_tail = (($outputText -split '\r?\n') | Where-Object { $_ -match '\S' } | Select-Object -Last 8) -join "`n"
                if ($exitCode -ne 0) {
                    $result.reason = "ffmpeg libx265 help probe failed with exit $exitCode"
                    return [pscustomobject]$result
                }
                if ($outputText -match '(?im)^\s*-dolbyvision\b') {
                    $result.ok = $true
                    $result.reason = 'ffmpeg libx265 exposes native Dolby Vision coding'
                    return [pscustomobject]$result
                }

                $result.reason = 'ffmpeg libx265 does not expose native Dolby Vision coding'
                return [pscustomobject]$result
            }

            function Invoke-X265DynamicHdrCapabilityProbe {
                param(
                    [Parameter(Mandatory)] [string] $Feature,
                    [string] $FixturePath,
                    [Parameter(Mandatory)] [string] $FixtureLeaf,
                    [Parameter(Mandatory)] [array] $DynamicParams
                )

                $result = [ordered]@{
                    feature      = $Feature
                    supplied     = -not [string]::IsNullOrWhiteSpace($FixturePath)
                    probed       = $false
                    ok           = $false
                    exit_code    = -1
                    reason       = ''
                    fixture_leaf = $FixtureLeaf
                    output_tail  = ''
                }
                if ([string]::IsNullOrWhiteSpace($FixturePath)) {
                    $result.reason = 'fixture was not supplied'
                    return [pscustomobject]$result
                }
                if (-not (Test-Path -LiteralPath $FixturePath -PathType Leaf)) {
                    $result.reason = "fixture not found: $FixturePath"
                    return [pscustomobject]$result
                }

                Copy-Item -LiteralPath $FixturePath -Destination (Join-Path $probeRoot $FixtureLeaf) -Force
                $probeOutput = Join-Path $probeRoot ("{0}.hevc" -f $Feature)
                $x265Params = @(
                    'log-level=error',
                    'hdr10=1',
                    'repeat-headers=1',
                    'colorprim=bt2020',
                    'transfer=smpte2084',
                    'colormatrix=bt2020nc'
                ) + @($DynamicParams)
                $arguments = @(
                    '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'lavfi', '-i', 'testsrc2=duration=1:size=64x64:rate=1',
                    '-frames:v', '1',
                    '-pix_fmt', 'yuv420p10le',
                    '-c:v', 'libx265',
                    '-preset', 'ultrafast',
                    '-x265-params', ($x265Params -join ':'),
                    '-f', 'hevc',
                    $probeOutput
                )
                Push-Location $probeRoot
                try {
                    $nativeOutput = & $FfmpegPath @arguments 2>&1
                    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
                } finally {
                    Pop-Location
                }
                $outputText = (@($nativeOutput) | ForEach-Object { [string]$_ }) -join "`n"
                $result.probed = $true
                $result.exit_code = $exitCode
                $result.ok = ($exitCode -eq 0 -and (Test-Path -LiteralPath $probeOutput -PathType Leaf))
                $result.reason = if ([bool]$result.ok) { 'probe encode succeeded' } else { "probe encode failed with exit $exitCode" }
                $result.output_tail = (($outputText -split '\r?\n') | Where-Object { $_ -match '\S' } | Select-Object -Last 8) -join "`n"
                return [pscustomobject]$result
            }

            $doviProbe = Invoke-X265DolbyVisionCapabilityProbe
            $hdr10PlusProbe = Invoke-X265DynamicHdrCapabilityProbe `
                -Feature 'hdr10plus' `
                -FixturePath $Hdr10PlusJsonFixturePath `
                -FixtureLeaf 'hdr10plus_probe.json' `
                -DynamicParams @('dhdr10-info=hdr10plus_probe.json')

            $probed = ([bool]$doviProbe.probed -or [bool]$hdr10PlusProbe.probed)
            $dolbyVision = [bool]$doviProbe.ok
            $hdr10Plus = [bool]$hdr10PlusProbe.ok
            foreach ($probe in @($doviProbe, $hdr10PlusProbe)) {
                if ($probe -and ([bool]$probe.supplied -or [string]$probe.feature -eq 'dovi')) {
                    $state = if ([bool]$probe.ok) { 'available' } else { [string]$probe.reason }
                    $reasonParts.Add("$($probe.feature): $state")
                }
            }
        } finally {
            Remove-Item -LiteralPath $probeRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    $reason = if ($reasonParts.Count -gt 0) { ($reasonParts.ToArray() -join '; ') } else { 'dynamic HDR x265 capability probe completed' }
    $script:X265DynamicHdrCapabilityCache = [pscustomobject][ordered]@{
        Probed      = $probed
        DolbyVision = $dolbyVision
        Hdr10Plus   = $hdr10Plus
        FfmpegPath  = [string]$FfmpegPath
        Reason      = $reason
        CheckedAt   = (Get-Date).ToString('o')
        DoviProbe   = $doviProbe
        Hdr10PlusProbe = $hdr10PlusProbe
    }
    return $script:X265DynamicHdrCapabilityCache
}
