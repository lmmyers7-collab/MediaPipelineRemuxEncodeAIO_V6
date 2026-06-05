function Initialize-ProbeModuleScope {
    $script:StopRequested = $false
    $script:ConsoleLogLevel = 'ERROR'
    $script:FileLogLevel = 'ERROR'
    $script:LocalFailureReports = Join-Path ([System.IO.Path]::GetTempPath()) 'mediapipeline-stage-repro'
    $script:StopFlag = Join-Path ([System.IO.Path]::GetTempPath()) 'mediapipeline-stage-runner.stop'
    $script:ffprobePath = Resolve-StageExecutable -ToolName 'ffprobe' -BundledRelativePath 'ops\pipeline\tools\ffmpeg\bin\ffprobe.exe'

    if (-not (Get-Command -Name Write-Log -ErrorAction SilentlyContinue)) {
        function global:Write-Log { param([string]$Message, [string]$Level = 'INFO') }
    }
    if (-not (Get-Command -Name DebugLog -ErrorAction SilentlyContinue)) {
        function global:DebugLog { param([string]$Message) }
    }
    if (-not (Get-Command -Name Set-ProgressStage -ErrorAction SilentlyContinue)) {
        function global:Set-ProgressStage { param([string]$Stage, [string]$Status, $Percent, [switch]$SaveNow) }
    }
}

function ConvertTo-StreamSummary {
    param($Stream)

    $kind = [string](Get-ObjectValue -Object $Stream -Name 'codec_type' -Default 'data')
    if ($kind -notin @('video','audio','subtitle','data','attachment')) {
        $kind = 'data'
    }
    $tags = Get-ObjectValue -Object $Stream -Name 'tags' -Default $null
    $disposition = Get-ObjectValue -Object $Stream -Name 'disposition' -Default $null

    return [ordered]@{
        index       = ConvertTo-IntValue (Get-ObjectValue -Object $Stream -Name 'index' -Default 0)
        kind        = $kind
        codec       = [string](Get-ObjectValue -Object $Stream -Name 'codec_name' -Default '')
        language    = [string](Get-ObjectValue -Object $tags -Name 'language' -Default '')
        bitrate_bps = ConvertTo-IntValue (Get-ObjectValue -Object $Stream -Name 'bit_rate' -Default 0)
        width       = ConvertTo-IntValue (Get-ObjectValue -Object $Stream -Name 'width' -Default 0)
        height      = ConvertTo-IntValue (Get-ObjectValue -Object $Stream -Name 'height' -Default 0)
        channels    = ConvertTo-IntValue (Get-ObjectValue -Object $Stream -Name 'channels' -Default 0)
        title       = [string](Get-ObjectValue -Object $tags -Name 'title' -Default '')
        default     = ((ConvertTo-IntValue (Get-ObjectValue -Object $disposition -Name 'default' -Default 0)) -eq 1)
        forced      = ((ConvertTo-IntValue (Get-ObjectValue -Object $disposition -Name 'forced' -Default 0)) -eq 1)
    }
}

function Invoke-ProbeStage {
    param([Parameter(Mandatory = $true)] $Payload)

    $scratchPath = [string](Require-ObjectValue -Object $Payload -Name 'scratch_path')
    Initialize-ProbeModuleScope
    $ffprobePath = $script:ffprobePath
    $StopFlag = $script:StopFlag
    $LocalFailureReports = $script:LocalFailureReports

    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'shared\failure_codes.ps1')

    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'shared\path_helpers.ps1')
    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'shared\native.ps1')
    . (Join-Path $PSScriptRoot 'media_probe.ps1')

    $profile = Get-SourceMediaRouteProfile -FilePath $scratchPath
    $container = ''
    $bitrateBps = 0
    $streams = @()

    if (Test-Path -LiteralPath $scratchPath -PathType Leaf) {
        $probe = Invoke-FFprobeCommand -ArgumentList @(
            '-v', 'error',
            '-show_entries', 'format=format_name,bit_rate:stream=index,codec_type,codec_name,width,height,channels,bit_rate:stream_tags=language,title:stream_disposition=default,forced',
            '-of', 'json',
            '--', $scratchPath
        ) -TimeoutSeconds 45 -Stage 'stage-probe'

        if ($probe.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace([string]$probe.Output)) {
            try {
                $probeJson = $probe.Output | ConvertFrom-Json -ErrorAction Stop
                if ($probeJson.format) {
                    $container = [string](Get-ObjectValue -Object $probeJson.format -Name 'format_name' -Default '')
                    $bitrateBps = ConvertTo-IntValue (Get-ObjectValue -Object $probeJson.format -Name 'bit_rate' -Default 0)
                }
                $streams = @($probeJson.streams | ForEach-Object { ConvertTo-StreamSummary $_ })
            } catch {
                if ([string]::IsNullOrWhiteSpace([string]$profile.probe_error)) {
                    $profile.probe_error = 'ffprobe_stream_json_invalid'
                }
            }
        } elseif ([string]::IsNullOrWhiteSpace([string]$profile.probe_error)) {
            $profile.probe_error = 'ffprobe_stream_probe_failed'
        }
    }

    return [ordered]@{
        probe_ok                = [bool]$profile.probe_ok
        probe_error             = [string]$profile.probe_error
        tool_path               = [string]$ffprobePath
        container               = $container
        duration_seconds        = ConvertTo-DoubleValue (Get-ObjectValue -Object $profile -Name 'duration_seconds' -Default 0)
        bitrate_bps             = $bitrateBps
        video_codec             = [string]$profile.video_codec
        width                   = ConvertTo-IntValue (Get-ObjectValue -Object $profile -Name 'width' -Default 0)
        height                  = ConvertTo-IntValue (Get-ObjectValue -Object $profile -Name 'height' -Default 0)
        is_hdr                  = [bool]$profile.is_hdr
        color_transfer          = [string]$profile.color_transfer
        container_bitrate_mbps  = ConvertTo-DoubleValue (Get-ObjectValue -Object $profile -Name 'container_bitrate_mbps' -Default 0)
        estimated_bitrate_mbps  = ConvertTo-DoubleValue (Get-ObjectValue -Object $profile -Name 'estimated_bitrate_mbps' -Default 0)
        size_bytes              = ConvertTo-LongValue (Get-ObjectValue -Object $profile -Name 'size_bytes' -Default 0)
        streams                 = @($streams)
    }
}
