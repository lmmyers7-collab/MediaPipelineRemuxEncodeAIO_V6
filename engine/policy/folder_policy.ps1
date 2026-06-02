# ==============================================================================
# engine\policy\folder_policy.ps1
# ==============================================================================
# Runtime reader for mediapipeline.folder.json sidecars. The desktop app owns
# authoring/validation; the pipeline consumes safe per-folder audio/subtitle
# overrides through the existing script:ActiveOverrides mechanism.
# ==============================================================================

$script:FolderPolicySidecarName = 'mediapipeline.folder.json'
$script:FolderPolicySchemaVersion = 'folder_policy.v1'

function Get-FolderPolicyProperty {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name
    )

    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    try {
        $prop = $Object.PSObject.Properties[$Name]
        if ($prop) { return $prop.Value }
    } catch {}
    return $null
}

function ConvertTo-FolderPolicyBool {
    param(
        $Value,
        [bool] $Default
    )

    if ($Value -is [bool]) { return [bool]$Value }
    if ($null -eq $Value) { return $Default }
    $text = ([string]$Value).Trim()
    if ($text -match '^(?i:true|1|yes|y|on)$') { return $true }
    if ($text -match '^(?i:false|0|no|n|off)$') { return $false }
    return $Default
}

function ConvertTo-FolderPolicyStringArray {
    param($Value)

    if ($null -eq $Value) { return @() }
    $items = if ($Value -is [array]) { @($Value) } else { @($Value) }
    return @(
        $items |
            ForEach-Object { [string]$_ } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            ForEach-Object { $_.Trim() } |
            Select-Object -Unique
    )
}

function ConvertTo-FolderPolicyLanguageArray {
    param($Value)

    return @(
        ConvertTo-FolderPolicyStringArray $Value |
            ForEach-Object {
                $text = ([string]$_).Trim().ToLowerInvariant()
                if ($text -in @('', 'und', 'unknown', 'undefined')) { 'und' } else { $text }
            } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Select-Object -Unique
    )
}

function Get-FolderPolicyFullPath {
    param([Parameter(Mandatory)] [string] $Path)

    if (Get-Command -Name Normalize-MediaPipelinePathForBoundary -ErrorAction SilentlyContinue) {
        return Normalize-MediaPipelinePathForBoundary -Path $Path
    }
    try {
        return [System.IO.Path]::GetFullPath($Path).TrimEnd('\','/')
    } catch {
        return ([string]$Path).TrimEnd('\','/')
    }
}

function Test-FolderPolicyPathWithinRoot {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Root
    )

    $pathText = Get-FolderPolicyFullPath $Path
    $rootText = Get-FolderPolicyFullPath $Root
    if ([string]::IsNullOrWhiteSpace($pathText) -or [string]::IsNullOrWhiteSpace($rootText)) { return $false }
    if (Get-Command -Name Test-MediaPipelinePathIsEqualOrChild -ErrorAction SilentlyContinue) {
        return Test-MediaPipelinePathIsEqualOrChild -Path $pathText -Root $rootText
    }
    if ($IsWindows -or $env:OS -eq 'Windows_NT') {
        $pathText = $pathText.ToLowerInvariant()
        $rootText = $rootText.ToLowerInvariant()
    }
    try {
        return ([System.IO.Path]::GetRelativePath($rootText, $pathText) -notmatch '^\.\.(\\|/|$)')
    } catch {
        return $pathText.Equals($rootText, [System.StringComparison]::OrdinalIgnoreCase) -or
            $pathText.StartsWith(($rootText.TrimEnd('\','/') + [System.IO.Path]::DirectorySeparatorChar), [System.StringComparison]::OrdinalIgnoreCase)
    }
}

function Get-FolderPolicySearchRoots {
    $roots = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
        (Get-Variable -Name SourceMovies -Scope Script -ErrorAction SilentlyContinue),
        (Get-Variable -Name SourceTV -Scope Script -ErrorAction SilentlyContinue)
    )) {
        if ($candidate -and -not [string]::IsNullOrWhiteSpace([string]$candidate.Value)) {
            $roots.Add((Get-FolderPolicyFullPath ([string]$candidate.Value)))
        }
    }
    return @($roots | Select-Object -Unique)
}

function Find-MediaPipelineFolderPolicy {
    param([Parameter(Mandatory)] $SourceFile)

    $sourcePath = if ($SourceFile -is [System.IO.FileInfo]) { $SourceFile.FullName } else { [string]$SourceFile }
    if ([string]::IsNullOrWhiteSpace($sourcePath)) { return $null }
    $current = try {
        if ((Test-Path -LiteralPath $sourcePath -PathType Leaf -ErrorAction SilentlyContinue)) {
            Split-Path -Parent (Resolve-Path -LiteralPath $sourcePath).Path
        } else {
            Split-Path -Parent (Get-FolderPolicyFullPath $sourcePath)
        }
    } catch {
        Split-Path -Parent (Get-FolderPolicyFullPath $sourcePath)
    }
    if ([string]::IsNullOrWhiteSpace($current)) { return $null }

    $roots = @(Get-FolderPolicySearchRoots)
    while (-not [string]::IsNullOrWhiteSpace($current)) {
        $candidate = Join-Path $current $script:FolderPolicySidecarName
        if (Test-Path -LiteralPath $candidate -PathType Leaf -ErrorAction SilentlyContinue) {
            return $candidate
        }

        if ($roots.Count -gt 0) {
            foreach ($root in $roots) {
                if ((Get-FolderPolicyFullPath $current) -eq (Get-FolderPolicyFullPath $root)) {
                    return $null
                }
            }
        }

        $parent = Split-Path -Parent $current
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $current) { break }
        if ($roots.Count -gt 0 -and -not (@($roots | Where-Object { Test-FolderPolicyPathWithinRoot -Path $parent -Root $_ }).Count -gt 0)) {
            break
        }
        $current = $parent
    }
    return $null
}

function Read-MediaPipelineFolderPolicy {
    param([Parameter(Mandatory)] [string] $Path)

    try {
        $payload = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        Write-Log "Folder policy sidecar could not be parsed: $Path — $($_.Exception.Message)" "WARN"
        return $null
    }
    $schemaVersion = [string](Get-FolderPolicyProperty -Object $payload -Name 'schema_version')
    if ($schemaVersion -ne $script:FolderPolicySchemaVersion) {
        Write-Log "Folder policy sidecar ignored due to schema_version '$schemaVersion': $Path" "WARN"
        return $null
    }
    return $payload
}

function ConvertTo-MediaPipelineFolderPolicyOverrides {
    param(
        [Parameter(Mandatory)] $Policy,
        [Parameter(Mandatory)] [string] $PolicyPath
    )

    $overrides = @{
        FolderPolicyPath = $PolicyPath
        FolderPolicyFolder = (Split-Path -Parent $PolicyPath)
    }

    $audio = Get-FolderPolicyProperty -Object $Policy -Name 'audio'
    if ($audio) {
        $passthroughProfile = ([string](Get-FolderPolicyProperty -Object $audio -Name 'passthrough_profile')).Trim().ToLowerInvariant()
        if ($passthroughProfile -in (Get-MediaPipelineAudioPassthroughProfileNames)) { $overrides.AudioPassthroughProfile = $passthroughProfile }

        $passthrough = @(ConvertTo-FolderPolicyStringArray (Get-FolderPolicyProperty -Object $audio -Name 'passthrough_codecs') | ForEach-Object { $_.ToLowerInvariant() })
        if ($passthrough.Count -gt 0) { $overrides.CompatibleAudioCodecs = @($passthrough) }

        $preferred = @(ConvertTo-FolderPolicyLanguageArray (Get-FolderPolicyProperty -Object $audio -Name 'preferred_default_languages'))
        if ($preferred.Count -gt 0) { $overrides.PreferredDefaultAudioLanguages = @($preferred) }

        $transcodeCodec = ([string](Get-FolderPolicyProperty -Object $audio -Name 'transcode_codec')).Trim().ToLowerInvariant()
        if ($transcodeCodec -in @('eac3','ac3','aac')) { $overrides.AudioTranscodeCodec = $transcodeCodec }

        $transcodeBitrate = ([string](Get-FolderPolicyProperty -Object $audio -Name 'transcode_bitrate')).Trim().ToLowerInvariant()
        if ($transcodeBitrate -match '^\d+k$') { $overrides.AudioTranscodeBitrate = $transcodeBitrate }

        $downmixMode = ([string](Get-FolderPolicyProperty -Object $audio -Name 'downmix_mode')).Trim().ToLowerInvariant()
        if ($downmixMode -in @('preserve','max_channels','stereo')) { $overrides.AudioDownmixMode = $downmixMode }

        $maxChannels = Get-FolderPolicyProperty -Object $audio -Name 'max_channels'
        if ($null -ne $maxChannels) {
            try {
                $channelCount = [int]$maxChannels
                if ($channelCount -ge 1 -and $channelCount -le 16) { $overrides.AudioMaxChannels = $channelCount }
            } catch {}
        }
    }

    $subtitles = Get-FolderPolicyProperty -Object $Policy -Name 'subtitles'
    if ($subtitles) {
        $ass = Get-FolderPolicyProperty -Object $subtitles -Name 'ass'
        if ($ass) {
            $overrides.ConvertAssToSrt = ConvertTo-FolderPolicyBool -Value (Get-FolderPolicyProperty -Object $ass -Name 'enabled') -Default $true
            $overrides.DropAssAfterConversion = ConvertTo-FolderPolicyBool -Value (Get-FolderPolicyProperty -Object $ass -Name 'drop_after_conversion') -Default $false
            $assLanguages = @(ConvertTo-FolderPolicyLanguageArray (Get-FolderPolicyProperty -Object $ass -Name 'languages'))
            if ($assLanguages.Count -gt 0) { $overrides.AssKeepLanguages = @($assLanguages) }
        }

        $tx3g = Get-FolderPolicyProperty -Object $subtitles -Name 'tx3g'
        if ($tx3g) {
            $overrides.ConvertTx3gToSrt = ConvertTo-FolderPolicyBool -Value (Get-FolderPolicyProperty -Object $tx3g -Name 'enabled') -Default $true
            $overrides.DropTx3gAfterConversion = ConvertTo-FolderPolicyBool -Value (Get-FolderPolicyProperty -Object $tx3g -Name 'drop_after_conversion') -Default $false
            $tx3gLanguages = @(ConvertTo-FolderPolicyLanguageArray (Get-FolderPolicyProperty -Object $tx3g -Name 'languages'))
            if ($tx3gLanguages.Count -gt 0) { $overrides.Tx3gExtractLanguages = @($tx3gLanguages) }
        }

        $bdpgs = Get-FolderPolicyProperty -Object $subtitles -Name 'bdpgs'
        if ($bdpgs) {
            $overrides.ConvertBdpgsToSrt = ConvertTo-FolderPolicyBool -Value (Get-FolderPolicyProperty -Object $bdpgs -Name 'enabled') -Default $false
            $overrides.DropBdpgsAfterConversion = ConvertTo-FolderPolicyBool -Value (Get-FolderPolicyProperty -Object $bdpgs -Name 'drop_after_conversion') -Default $false
            $bdpgsLanguages = @(ConvertTo-FolderPolicyLanguageArray (Get-FolderPolicyProperty -Object $bdpgs -Name 'languages'))
            if ($bdpgsLanguages.Count -gt 0) { $overrides.BdpgsExtractLanguages = @($bdpgsLanguages) }
        }
    }

    $routing = Get-FolderPolicyProperty -Object $Policy -Name 'routing'
    if ($routing) {
        $routingProfile = ([string](Get-FolderPolicyProperty -Object $routing -Name 'routing_profile')).Trim().ToLowerInvariant()
        if ($routingProfile -in @('plex_direct_stream','plex_direct_play','archive_shrink','archive_quality','manual')) {
            $overrides.RoutingProfile = $routingProfile
        }

        $sizeGuardMode = ([string](Get-FolderPolicyProperty -Object $routing -Name 'size_guard_mode')).Trim().ToLowerInvariant()
        if ($sizeGuardMode -in @('advisory','strict','off')) {
            $overrides.SizeGuardMode = $sizeGuardMode
        }

        $allowH264Remux = Get-FolderPolicyProperty -Object $routing -Name 'allow_h264_remux_if_plex_compatible'
        if ($null -ne $allowH264Remux) {
            $overrides.AllowH264RemuxIfPlexCompatible = ConvertTo-FolderPolicyBool -Value $allowH264Remux -Default $true
        }

        $h264MaxBitrate = Get-FolderPolicyProperty -Object $routing -Name 'h264_remux_max_bitrate_mbps'
        if ($null -ne $h264MaxBitrate) {
            try {
                $bitrate = [double]$h264MaxBitrate
                if ($bitrate -gt 0) { $overrides.H264RemuxMaxBitrateMbps = $bitrate }
            } catch {}
        }

        $h264MaxHeight = Get-FolderPolicyProperty -Object $routing -Name 'h264_remux_max_height'
        if ($null -ne $h264MaxHeight) {
            try {
                $height = [int]$h264MaxHeight
                if ($height -gt 0) { $overrides.H264RemuxMaxHeight = $height }
            } catch {}
        }

        $forceRoute = ([string](Get-FolderPolicyProperty -Object $routing -Name 'force_route')).Trim().ToLowerInvariant()
        if ($forceRoute -in @('auto','remux','encode')) { $overrides.RouteForce = $forceRoute }

        $preferRoute = ([string](Get-FolderPolicyProperty -Object $routing -Name 'prefer_route')).Trim().ToLowerInvariant()
        if ($preferRoute -in @('auto','remux','encode')) { $overrides.RoutePrefer = $preferRoute }

        $maxBitrate = Get-FolderPolicyProperty -Object $routing -Name 'max_video_bitrate_mbps'
        if ($null -ne $maxBitrate) {
            try {
                $bitrate = [double]$maxBitrate
                if ($bitrate -gt 0) { $overrides.RouteMaxVideoBitrateMbps = $bitrate }
            } catch {}
        }

        $maxHeight = Get-FolderPolicyProperty -Object $routing -Name 'max_resolution_height'
        if ($null -ne $maxHeight) {
            try {
                $height = [int]$maxHeight
                if ($height -gt 0) { $overrides.RouteMaxResolutionHeight = $height }
            } catch {}
        }

        $allowedCodecs = @(
            ConvertTo-FolderPolicyStringArray (Get-FolderPolicyProperty -Object $routing -Name 'allowed_video_codecs') |
                ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                Select-Object -Unique
        )
        if ($allowedCodecs.Count -gt 0) { $overrides.RouteAllowedVideoCodecs = @($allowedCodecs) }

        $strict = Get-FolderPolicyProperty -Object $routing -Name 'plex_strict_mode'
        if ($null -ne $strict) {
            $overrides.RoutePlexStrictMode = ConvertTo-FolderPolicyBool -Value $strict -Default $false
        }

        $allowUnsafeForcedRemux = Get-FolderPolicyProperty -Object $routing -Name 'allow_unsafe_forced_remux'
        if ($null -ne $allowUnsafeForcedRemux) {
            $overrides.RouteAllowUnsafeForcedRemux = ConvertTo-FolderPolicyBool -Value $allowUnsafeForcedRemux -Default $false
        }

        $routeReason = ([string](Get-FolderPolicyProperty -Object $routing -Name 'reason')).Trim()
        if (-not [string]::IsNullOrWhiteSpace($routeReason)) { $overrides.RoutePolicyReason = $routeReason }
    }

    $overrides.FolderPolicyKeys = @(
        $overrides.Keys |
            Where-Object { $_ -notin @('FolderPolicyPath', 'FolderPolicyFolder', 'FolderPolicyKeys') } |
            Sort-Object
    )
    return $overrides
}

function ConvertTo-FolderPolicyTopologyItemKey {
    param(
        $Item,
        [Parameter(Mandatory)] [string] $Kind
    )

    $values = @()
    if ($Item -is [System.Collections.IDictionary]) {
        $values = @($Item['codec'], $Item['language'], $Item['channels'])
    } elseif ($Item -is [System.Collections.IEnumerable] -and -not ($Item -is [string])) {
        $values = @($Item)
    } elseif ($Item) {
        $codec = if ($Item.PSObject.Properties['codec']) { [string]$Item.codec } else { '' }
        $language = if ($Item.PSObject.Properties['language']) { [string]$Item.language } else { '' }
        $channels = if ($Item.PSObject.Properties['channels']) { [string]$Item.channels } else { '' }
        $values = @($codec, $language, $channels)
    }

    $codecValue = if ($values.Count -gt 0) { ([string]$values[0]).Trim().ToLowerInvariant() } else { '' }
    $languageValue = if ($values.Count -gt 1 -and -not [string]::IsNullOrWhiteSpace([string]$values[1])) { ([string]$values[1]).Trim().ToLowerInvariant() } else { 'und' }
    if ($Kind -eq 'audio') {
        $channelsValue = 0
        try {
            if ($values.Count -gt 2) { $channelsValue = [int]$values[2] }
        } catch {
            $channelsValue = 0
        }
        return "$codecValue|$languageValue|$channelsValue"
    }
    return "$codecValue|$languageValue"
}

function Get-FolderPolicyTopologyItems {
    param($Value)

    if ($null -eq $Value) { return @() }
    if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
        $items = @($Value)
        if ($items.Count -gt 0 -and ($items[0] -is [string] -or $items[0] -is [ValueType])) {
            return @(,$Value)
        }
        return @($items)
    }
    return @(,$Value)
}

function ConvertTo-FolderPolicyTopologyKey {
    param($Topology)

    $audio = @()
    $subtitles = @()
    if ($Topology) {
        $audioValue = Get-FolderPolicyProperty -Object $Topology -Name 'audio'
        $subtitleValue = Get-FolderPolicyProperty -Object $Topology -Name 'subtitles'
        $audio = @(Get-FolderPolicyTopologyItems -Value $audioValue | Where-Object { $null -ne $_ } | ForEach-Object { ConvertTo-FolderPolicyTopologyItemKey -Item $_ -Kind 'audio' })
        $subtitles = @(Get-FolderPolicyTopologyItems -Value $subtitleValue | Where-Object { $null -ne $_ } | ForEach-Object { ConvertTo-FolderPolicyTopologyItemKey -Item $_ -Kind 'subtitle' })
    }
    return [ordered]@{
        audio     = @($audio)
        subtitles = @($subtitles)
    }
}

function Get-FolderPolicyRuntimeStreamTopology {
    param([Parameter(Mandatory)] [string] $SourcePath)

    $probe = Invoke-FFprobeCommand -ArgumentList @(
        '-v', 'error',
        '-show_entries', 'stream=index,codec_type,codec_name,channels:stream_tags=language',
        '-of', 'json',
        '--', $SourcePath
    ) -TimeoutSeconds 30 -Stage 'folder-policy-topology'

    if ($probe.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace([string]$probe.Output)) {
        return $null
    }

    try {
        $json = $probe.Output | ConvertFrom-Json -ErrorAction Stop
        $audio = [System.Collections.Generic.List[object]]::new()
        $subtitles = [System.Collections.Generic.List[object]]::new()
        foreach ($stream in @($json.streams)) {
            if (-not $stream) { continue }
            $type = ([string]$stream.codec_type).Trim().ToLowerInvariant()
            $codec = ([string]$stream.codec_name).Trim().ToLowerInvariant()
            $language = 'und'
            try {
                if ($stream.tags -and $stream.tags.language) {
                    $language = ([string]$stream.tags.language).Trim().ToLowerInvariant()
                }
            } catch {}
            if ([string]::IsNullOrWhiteSpace($language)) { $language = 'und' }
            if ($type -eq 'audio') {
                $channels = 0
                try { $channels = [int]$stream.channels } catch { $channels = 0 }
                $audio.Add(@($codec, $language, $channels)) | Out-Null
            } elseif ($type -eq 'subtitle') {
                $subtitles.Add(@($codec, $language)) | Out-Null
            }
        }
        return [ordered]@{
            audio     = @($audio)
            subtitles = @($subtitles)
        }
    } catch {
        Write-Log "Folder policy topology probe output could not be parsed for $SourcePath : $($_.Exception.Message)" "WARN"
        return $null
    }
}

function Test-FolderPolicyTopologyMatches {
    param(
        [Parameter(Mandatory)] $Expected,
        [Parameter(Mandatory)] $Actual
    )

    $expectedKey = ConvertTo-FolderPolicyTopologyKey $Expected
    $actualKey = ConvertTo-FolderPolicyTopologyKey $Actual
    return ((@($expectedKey.audio) -join '||') -eq (@($actualKey.audio) -join '||') -and
            (@($expectedKey.subtitles) -join '||') -eq (@($actualKey.subtitles) -join '||'))
}

function Test-FolderPolicyValidationAllowsSource {
    param(
        [Parameter(Mandatory)] $Policy,
        [Parameter(Mandatory)] [string] $PolicyPath,
        [Parameter(Mandatory)] $SourceFile
    )

    $validation = Get-FolderPolicyProperty -Object $Policy -Name 'validation'
    if (-not $validation) { return $true }
    $requireUniform = ConvertTo-FolderPolicyBool -Value (Get-FolderPolicyProperty -Object $validation -Name 'require_uniform_stream_topology') -Default $false
    if (-not $requireUniform) { return $true }

    $expected = Get-FolderPolicyProperty -Object $validation -Name 'expected_topology'
    if (-not $expected) {
        Write-Log "FOLDER POLICY: $PolicyPath requires uniform topology but has no expected_topology; run Validate Folder Policy to make runtime enforcement deterministic." "WARN"
        return $true
    }

    $sourcePath = if ($SourceFile -is [string]) { [string]$SourceFile } else { [string]$SourceFile.FullName }
    $actual = Get-FolderPolicyRuntimeStreamTopology -SourcePath $sourcePath
    if (-not $actual) {
        Write-Log "FOLDER POLICY: ignoring $PolicyPath for $(Split-Path $sourcePath -Leaf) because runtime topology probe failed." "WARN"
        return $false
    }
    if (-not (Test-FolderPolicyTopologyMatches -Expected $expected -Actual $actual)) {
        Write-Log "FOLDER POLICY: ignoring $PolicyPath for $(Split-Path $sourcePath -Leaf) because stream topology differs from the validated sample." "WARN"
        return $false
    }
    return $true
}

function Resolve-FolderPolicyOverrides {
    param([Parameter(Mandatory)] $SourceFile)

    $policyPath = Find-MediaPipelineFolderPolicy -SourceFile $SourceFile
    if (-not $policyPath) { return $null }
    $policy = Read-MediaPipelineFolderPolicy -Path $policyPath
    if (-not $policy) { return $null }
    if (-not (Test-FolderPolicyValidationAllowsSource -Policy $policy -PolicyPath $policyPath -SourceFile $SourceFile)) { return $null }
    $overrides = ConvertTo-MediaPipelineFolderPolicyOverrides -Policy $policy -PolicyPath $policyPath
    Write-Log "FOLDER POLICY: applying $policyPath" "DEBUG"
    return $overrides
}

function Merge-MediaPipelineActiveOverrides {
    param(
        $Base,
        $Override
    )

    $merged = @{}
    foreach ($source in @($Base, $Override)) {
        if (-not $source) { continue }
        if ($source -is [System.Collections.IDictionary]) {
            foreach ($key in $source.Keys) { $merged[$key] = $source[$key] }
        } else {
            foreach ($prop in @($source.PSObject.Properties)) { $merged[$prop.Name] = $prop.Value }
        }
    }
    if ($merged.Count -eq 0) { return $null }
    return $merged
}

function Get-ActiveFolderPolicyMetadata {
    if (-not $script:ActiveOverrides -or -not $script:ActiveOverrides.ContainsKey('FolderPolicyPath')) {
        return $null
    }

    $folderKeys = @()
    if ($script:ActiveOverrides.ContainsKey('FolderPolicyKeys')) {
        $folderKeys = @($script:ActiveOverrides['FolderPolicyKeys'] | ForEach-Object { [string]$_ })
    }

    $overrides = [ordered]@{}
    foreach ($entry in @(
        @{ Key = 'AudioPassthroughProfile'; Name = 'audio_passthrough_profile' },
        @{ Key = 'CompatibleAudioCodecs'; Name = 'compatible_audio_codecs'; Array = $true },
        @{ Key = 'PreferredDefaultAudioLanguages'; Name = 'preferred_default_audio_languages'; Array = $true },
        @{ Key = 'AudioTranscodeCodec'; Name = 'audio_transcode_codec' },
        @{ Key = 'AudioTranscodeBitrate'; Name = 'audio_transcode_bitrate' },
        @{ Key = 'AudioDownmixMode'; Name = 'audio_downmix_mode' },
        @{ Key = 'AudioMaxChannels'; Name = 'audio_max_channels' },
        @{ Key = 'ConvertAssToSrt'; Name = 'convert_ass_to_srt' },
        @{ Key = 'DropAssAfterConversion'; Name = 'drop_ass_after_conversion' },
        @{ Key = 'AssKeepLanguages'; Name = 'ass_languages'; Array = $true },
        @{ Key = 'ConvertTx3gToSrt'; Name = 'convert_tx3g_to_srt' },
        @{ Key = 'DropTx3gAfterConversion'; Name = 'drop_tx3g_after_conversion' },
        @{ Key = 'Tx3gExtractLanguages'; Name = 'tx3g_languages'; Array = $true },
        @{ Key = 'ConvertBdpgsToSrt'; Name = 'convert_bdpgs_to_srt' },
        @{ Key = 'DropBdpgsAfterConversion'; Name = 'drop_bdpgs_after_conversion' },
        @{ Key = 'BdpgsExtractLanguages'; Name = 'bdpgs_languages'; Array = $true },
        @{ Key = 'RoutingProfile'; Name = 'routing_profile' },
        @{ Key = 'SizeGuardMode'; Name = 'size_guard_mode' },
        @{ Key = 'AllowH264RemuxIfPlexCompatible'; Name = 'allow_h264_remux_if_plex_compatible' },
        @{ Key = 'H264RemuxMaxBitrateMbps'; Name = 'h264_remux_max_bitrate_mbps' },
        @{ Key = 'H264RemuxMaxHeight'; Name = 'h264_remux_max_height' },
        @{ Key = 'RouteForce'; Name = 'routing_force_route' },
        @{ Key = 'RoutePrefer'; Name = 'routing_prefer_route' },
        @{ Key = 'RouteMaxVideoBitrateMbps'; Name = 'routing_max_video_bitrate_mbps' },
        @{ Key = 'RouteMaxResolutionHeight'; Name = 'routing_max_resolution_height' },
        @{ Key = 'RouteAllowedVideoCodecs'; Name = 'routing_allowed_video_codecs'; Array = $true },
        @{ Key = 'RoutePlexStrictMode'; Name = 'routing_plex_strict_mode' },
        @{ Key = 'RouteAllowUnsafeForcedRemux'; Name = 'routing_allow_unsafe_forced_remux' },
        @{ Key = 'RoutePolicyReason'; Name = 'routing_reason' }
    )) {
        $key = [string]$entry['Key']
        if ($folderKeys.Count -gt 0 -and $folderKeys -notcontains $key) { continue }
        if (-not $script:ActiveOverrides.ContainsKey($key)) { continue }
        $overrides[[string]$entry['Name']] = if ($entry['Array']) {
            @($script:ActiveOverrides[$key])
        } else {
            $script:ActiveOverrides[$key]
        }
    }

    return [ordered]@{
        applied        = $true
        schema_version = $script:FolderPolicySchemaVersion
        path           = [string]$script:ActiveOverrides['FolderPolicyPath']
        folder         = if ($script:ActiveOverrides.ContainsKey('FolderPolicyFolder')) { [string]$script:ActiveOverrides['FolderPolicyFolder'] } else { '' }
        keys           = @($folderKeys)
        overrides      = $overrides
    }
}
