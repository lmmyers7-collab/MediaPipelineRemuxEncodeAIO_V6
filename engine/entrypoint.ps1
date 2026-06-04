param(
    [Parameter(Mandatory = $true)]
    [string] $Stage,

    [Parameter(Mandatory = $true)]
    [string] $PayloadJson
)

$ErrorActionPreference = 'Stop'
$script:StageSchemaVersion = 'v1'

function Get-UtcNow {
    return [DateTime]::UtcNow
}

function ConvertTo-JsonText {
    param($Value)
    return ($Value | ConvertTo-Json -Depth 50 -Compress)
}

function New-StageError {
    param(
        [Parameter(Mandatory = $true)] [string] $Code,
        [Parameter(Mandatory = $true)] [string] $Message,
        $Details = $null
    )

    $errorDetails = if ($null -eq $Details) { [ordered]@{} } else { $Details }
    return [ordered]@{
        code    = $Code
        message = $Message
        details = $errorDetails
    }
}

function Write-StageResult {
    param(
        [Parameter(Mandatory = $true)] [string] $StageName,
        [Parameter(Mandatory = $true)] [bool] $Ok,
        [Parameter(Mandatory = $true)] [DateTime] $StartedAt,
        $Data = $null,
        $ErrorRecord = $null
    )

    $finishedAt = Get-UtcNow
    $durationMs = [Math]::Max(0, [int][Math]::Round(($finishedAt - $StartedAt).TotalMilliseconds))
    $eventType = if ($StageName -in @('ingest','probe','decide','transcode','subtitle-convert','audio-mix','publish','drain','rename')) {
        'pipeline.stage.' + ($StageName -replace '-', '_')
    } else {
        'pipeline.stage.unknown'
    }
    $result = [ordered]@{
        schema_version     = $script:StageSchemaVersion
        stage              = $StageName
        ok                 = [bool]$Ok
        started_at         = $StartedAt.ToString('o')
        finished_at        = $finishedAt.ToString('o')
        duration_ms        = $durationMs
        journal_event_type = $eventType
    }
    if ($Ok) {
        $result['data'] = if ($null -eq $Data) { [ordered]@{} } else { $Data }
    } else {
        $result['error'] = if ($null -eq $ErrorRecord) {
            New-StageError -Code 'stage.failed' -Message 'Stage failed.'
        } else {
            $ErrorRecord
        }
    }
    [Console]::Out.WriteLine((ConvertTo-JsonText $result))
}

function Read-PayloadDocument {
    param([Parameter(Mandatory = $true)] [string] $RawPayload)

    $text = $RawPayload
    try {
        if (Test-Path -LiteralPath $RawPayload -PathType Leaf) {
            $text = Get-Content -LiteralPath $RawPayload -Raw -Encoding UTF8
        }
    } catch {
        $text = $RawPayload
    }
    return ($text | ConvertFrom-Json -Depth 100 -ErrorAction Stop)
}

function Get-ObjectValue {
    param(
        [Parameter(Mandatory = $true)] $Object,
        [Parameter(Mandatory = $true)] [string] $Name,
        $Default = $null
    )

    if ($null -eq $Object) { return $Default }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $Default
}

function Test-ObjectHasProperty {
    param(
        [Parameter(Mandatory = $true)] $Object,
        [Parameter(Mandatory = $true)] [string] $Name
    )

    if ($null -eq $Object) { return $false }
    if ($Object -is [System.Collections.IDictionary]) {
        return $Object.Contains($Name)
    }
    return ($null -ne $Object.PSObject.Properties[$Name])
}

function Get-ObjectPropertyNames {
    param($Object)

    if ($null -eq $Object) { return @() }
    if ($Object -is [System.Collections.IDictionary]) {
        return @($Object.Keys | ForEach-Object { [string]$_ })
    }
    return @($Object.PSObject.Properties | ForEach-Object { [string]$_.Name })
}

function Assert-AllowedObjectProperties {
    param(
        [Parameter(Mandatory = $true)] $Object,
        [Parameter(Mandatory = $true)] [string[]] $Allowed,
        [Parameter(Mandatory = $true)] [string] $Context
    )

    foreach ($name in Get-ObjectPropertyNames $Object) {
        if ($name -notin $Allowed) {
            throw "unknown $Context field '$name'"
        }
    }
}

function Require-ObjectValue {
    param(
        [Parameter(Mandatory = $true)] $Object,
        [Parameter(Mandatory = $true)] [string] $Name
    )

    $property = $Object.PSObject.Properties[$Name]
    if (-not $property -or $null -eq $property.Value) {
        throw "missing required payload field '$Name'"
    }
    return $property.Value
}

function Get-StagePayload {
    param(
        [Parameter(Mandatory = $true)] $Document,
        [Parameter(Mandatory = $true)] [string] $StageName
    )

    $hasEnvelopeShape = (
        (Test-ObjectHasProperty -Object $Document -Name 'schema_version') -or
        (Test-ObjectHasProperty -Object $Document -Name 'stage') -or
        (Test-ObjectHasProperty -Object $Document -Name 'payload')
    )
    if ($hasEnvelopeShape) {
        Assert-AllowedObjectProperties `
            -Object $Document `
            -Allowed @('schema_version','stage','payload') `
            -Context 'stage request envelope'
    }

    $schemaVersion = [string](Get-ObjectValue -Object $Document -Name 'schema_version' -Default '')
    if ([string]::IsNullOrWhiteSpace($schemaVersion)) {
        $schemaVersion = [string](Get-ObjectValue -Object (Get-ObjectValue -Object $Document -Name 'payload' -Default $Document) -Name 'schema_version' -Default $script:StageSchemaVersion)
    }
    if ($schemaVersion -ne $script:StageSchemaVersion) {
        throw "unsupported schema_version '$schemaVersion'"
    }
    $documentStage = [string](Get-ObjectValue -Object $Document -Name 'stage' -Default $StageName)
    if ($documentStage -and $documentStage -ne $StageName) {
        throw "payload stage '$documentStage' does not match requested stage '$StageName'"
    }
    return (Get-ObjectValue -Object $Document -Name 'payload' -Default $Document)
}

function ConvertTo-OrderedMap {
    param($Object)

    $map = [ordered]@{}
    if ($null -eq $Object) { return $map }
    if ($Object -is [System.Collections.IDictionary]) {
        foreach ($key in $Object.Keys) { $map[[string]$key] = $Object[$key] }
        return $map
    }
    foreach ($property in $Object.PSObject.Properties) {
        $map[$property.Name] = $property.Value
    }
    return $map
}

function ConvertTo-IntValue {
    param($Value, [int] $Default = 0)
    if ($null -eq $Value) { return $Default }
    try { return [int]$Value } catch { return $Default }
}

function ConvertTo-LongValue {
    param($Value, [long] $Default = 0)
    if ($null -eq $Value) { return $Default }
    try { return [long]$Value } catch { return $Default }
}

function ConvertTo-DoubleValue {
    param($Value, [double] $Default = 0.0)
    if ($null -eq $Value) { return $Default }
    try {
        return [double]::Parse([string]$Value, [System.Globalization.CultureInfo]::InvariantCulture)
    } catch {
        try { return [double]$Value } catch { return $Default }
    }
}

function Test-JsonBooleanValue {
    param($Value)
    return ($Value -is [bool])
}

function Test-JsonIntegerValue {
    param($Value)
    if ($Value -is [bool] -or $null -eq $Value) { return $false }
    return ($Value -is [byte] -or
        $Value -is [sbyte] -or
        $Value -is [int16] -or
        $Value -is [uint16] -or
        $Value -is [int] -or
        $Value -is [uint32] -or
        $Value -is [long] -or
        $Value -is [uint64])
}

function Test-JsonNumberValue {
    param($Value)
    if ($Value -is [bool] -or $null -eq $Value) { return $false }
    return ((Test-JsonIntegerValue $Value) -or
        $Value -is [float] -or
        $Value -is [double] -or
        $Value -is [decimal])
}

function Test-JsonObjectValue {
    param($Value)
    if ($null -eq $Value) { return $false }
    return ($Value -is [System.Collections.IDictionary] -or $Value -is [pscustomobject])
}

function Assert-StageStringField {
    param(
        [Parameter(Mandatory = $true)] $Payload,
        [Parameter(Mandatory = $true)] [string] $Name,
        [switch] $Required,
        [string[]] $AllowedValues = @()
    )

    $exists = Test-ObjectHasProperty -Object $Payload -Name $Name
    if (-not $exists) {
        if ($Required) { throw "missing required payload field '$Name'" }
        return
    }
    $value = Get-ObjectValue -Object $Payload -Name $Name
    if ($null -eq $value) { throw "payload field '$Name' must be a JSON string" }
    if ($value -isnot [string]) { throw "payload field '$Name' must be a JSON string" }
    if ($Required -and [string]::IsNullOrWhiteSpace($value)) {
        throw "missing required payload field '$Name'"
    }
    if ($AllowedValues.Count -gt 0 -and $value -notin $AllowedValues) {
        throw "payload field '$Name' must be one of: $($AllowedValues -join ', ')"
    }
}

function Assert-StageBooleanField {
    param(
        [Parameter(Mandatory = $true)] $Payload,
        [Parameter(Mandatory = $true)] [string] $Name
    )

    if (-not (Test-ObjectHasProperty -Object $Payload -Name $Name)) { return }
    $value = Get-ObjectValue -Object $Payload -Name $Name
    if (-not (Test-JsonBooleanValue $value)) {
        throw "payload field '$Name' must be a JSON boolean"
    }
}

function Assert-StageIntegerField {
    param(
        [Parameter(Mandatory = $true)] $Payload,
        [Parameter(Mandatory = $true)] [string] $Name,
        [switch] $Required,
        [long] $Minimum = [long]::MinValue,
        [long] $Maximum = [long]::MaxValue
    )

    $exists = Test-ObjectHasProperty -Object $Payload -Name $Name
    if (-not $exists) {
        if ($Required) { throw "missing required payload field '$Name'" }
        return
    }
    $value = Get-ObjectValue -Object $Payload -Name $Name
    if (-not (Test-JsonIntegerValue $value)) {
        throw "payload field '$Name' must be a JSON integer"
    }
    $typed = [decimal]$value
    if ($typed -lt $Minimum) { throw "payload field '$Name' must be >= $Minimum" }
    if ($typed -gt $Maximum) { throw "payload field '$Name' must be <= $Maximum" }
}

function Assert-StageNumberField {
    param(
        [Parameter(Mandatory = $true)] $Payload,
        [Parameter(Mandatory = $true)] [string] $Name,
        [double] $Minimum = [double]::NegativeInfinity,
        [double] $Maximum = [double]::PositiveInfinity,
        [switch] $ExclusiveMinimum
    )

    if (-not (Test-ObjectHasProperty -Object $Payload -Name $Name)) { return }
    $value = Get-ObjectValue -Object $Payload -Name $Name
    if (-not (Test-JsonNumberValue $value)) {
        throw "payload field '$Name' must be a JSON number"
    }
    $typed = [double]$value
    if ($ExclusiveMinimum) {
        if ($typed -le $Minimum) { throw "payload field '$Name' must be > $Minimum" }
    } elseif ($typed -lt $Minimum) {
        throw "payload field '$Name' must be >= $Minimum"
    }
    if ($typed -gt $Maximum) { throw "payload field '$Name' must be <= $Maximum" }
}

function Assert-StageObjectField {
    param(
        [Parameter(Mandatory = $true)] $Payload,
        [Parameter(Mandatory = $true)] [string] $Name
    )

    if (-not (Test-ObjectHasProperty -Object $Payload -Name $Name)) { return }
    $value = Get-ObjectValue -Object $Payload -Name $Name
    if (-not (Test-JsonObjectValue $value)) {
        throw "payload field '$Name' must be a JSON object"
    }
}

function Assert-StagePayloadContract {
    param(
        [Parameter(Mandatory = $true)] [string] $StageName,
        [Parameter(Mandatory = $true)] $Payload
    )

    switch ($StageName) {
        'probe' {
            Assert-AllowedObjectProperties `
                -Object $Payload `
                -Allowed @('run_id','job_id','scratch_path') `
                -Context 'probe payload'
            Assert-StageStringField -Payload $Payload -Name 'run_id'
            Assert-StageStringField -Payload $Payload -Name 'job_id'
            Assert-StageStringField -Payload $Payload -Name 'scratch_path' -Required
        }
        'decide' {
            Assert-AllowedObjectProperties `
                -Object $Payload `
                -Allowed @(
                    'run_id',
                    'job_id',
                    'file_size_bytes',
                    'is_tv',
                    'duration_seconds',
                    'video_codec',
                    'video_height',
                    'is_hdr',
                    'routing_profile',
                    'route_threshold_mode',
                    'size_guard_mode',
                    'encode_threshold_gb',
                    'tv_encode_threshold_gb',
                    'movie_route_max_video_bitrate_mbps',
                    'tv_route_max_video_bitrate_mbps',
                    'route_1080p_bucket_max_height',
                    'route_1080p_max_video_bitrate_mbps',
                    'route_4k_bucket_min_height',
                    'route_4k_max_video_bitrate_mbps',
                    'allow_h264_remux_if_plex_compatible',
                    'h264_remux_max_bitrate_mbps',
                    'h264_remux_max_height',
                    'route_hints',
                    'source_media_profile'
                ) `
                -Context 'decide payload'
            Assert-StageStringField -Payload $Payload -Name 'run_id'
            Assert-StageStringField -Payload $Payload -Name 'job_id'
            Assert-StageIntegerField -Payload $Payload -Name 'file_size_bytes' -Required -Minimum 0
            Assert-StageBooleanField -Payload $Payload -Name 'is_tv'
            Assert-StageNumberField -Payload $Payload -Name 'duration_seconds' -Minimum 0
            Assert-StageStringField -Payload $Payload -Name 'video_codec'
            Assert-StageIntegerField -Payload $Payload -Name 'video_height' -Minimum 0 -Maximum 4320
            Assert-StageBooleanField -Payload $Payload -Name 'is_hdr'
            Assert-StageStringField `
                -Payload $Payload `
                -Name 'routing_profile' `
                -AllowedValues @('plex_direct_stream','plex_direct_play','archive_shrink','archive_quality','manual')
            Assert-StageStringField `
                -Payload $Payload `
                -Name 'route_threshold_mode' `
                -AllowedValues @('compatibility_advisory','size','bitrate','size_or_bitrate')
            Assert-StageStringField `
                -Payload $Payload `
                -Name 'size_guard_mode' `
                -AllowedValues @('advisory','strict','off')
            Assert-StageNumberField -Payload $Payload -Name 'encode_threshold_gb' -Minimum 0 -ExclusiveMinimum
            Assert-StageNumberField -Payload $Payload -Name 'tv_encode_threshold_gb' -Minimum 0 -ExclusiveMinimum
            Assert-StageNumberField -Payload $Payload -Name 'movie_route_max_video_bitrate_mbps' -Minimum 0 -Maximum 500 -ExclusiveMinimum
            Assert-StageNumberField -Payload $Payload -Name 'tv_route_max_video_bitrate_mbps' -Minimum 0 -Maximum 500 -ExclusiveMinimum
            Assert-StageIntegerField -Payload $Payload -Name 'route_1080p_bucket_max_height' -Minimum 1 -Maximum 4320
            Assert-StageNumberField -Payload $Payload -Name 'route_1080p_max_video_bitrate_mbps' -Minimum 0 -Maximum 500 -ExclusiveMinimum
            Assert-StageIntegerField -Payload $Payload -Name 'route_4k_bucket_min_height' -Minimum 1 -Maximum 4320
            Assert-StageNumberField -Payload $Payload -Name 'route_4k_max_video_bitrate_mbps' -Minimum 0 -Maximum 500 -ExclusiveMinimum
            if ((Test-ObjectHasProperty -Object $Payload -Name 'route_1080p_bucket_max_height') -and
                (Test-ObjectHasProperty -Object $Payload -Name 'route_4k_bucket_min_height')) {
                $route1080pMaxHeight = [int](Get-ObjectValue -Object $Payload -Name 'route_1080p_bucket_max_height' -Default 1200)
                $route4kMinHeight = [int](Get-ObjectValue -Object $Payload -Name 'route_4k_bucket_min_height' -Default 1800)
                if ($route1080pMaxHeight -ge $route4kMinHeight) {
                    throw "route_1080p_bucket_max_height must be lower than route_4k_bucket_min_height"
                }
            }
            Assert-StageBooleanField -Payload $Payload -Name 'allow_h264_remux_if_plex_compatible'
            Assert-StageNumberField -Payload $Payload -Name 'h264_remux_max_bitrate_mbps' -Minimum 0 -ExclusiveMinimum
            Assert-StageIntegerField -Payload $Payload -Name 'h264_remux_max_height' -Minimum 1 -Maximum 4320
            Assert-StageObjectField -Payload $Payload -Name 'route_hints'
            Assert-StageObjectField -Payload $Payload -Name 'source_media_profile'
        }
    }
}

function Resolve-StageExecutable {
    param(
        [Parameter(Mandatory = $true)] [string] $ToolName,
        [Parameter(Mandatory = $true)] [string] $BundledRelativePath
    )

    $repoRoot = Split-Path -Parent $PSScriptRoot
    $bundled = Join-Path $repoRoot $BundledRelativePath
    if (Test-Path -LiteralPath $bundled -PathType Leaf) { return $bundled }

    if ($env:MEDIAPIPELINE_ALLOW_SYSTEM_STAGE_TOOLS -ne '1') {
        throw "$ToolName bundled executable not found at '$bundled'. Set MEDIAPIPELINE_ALLOW_SYSTEM_STAGE_TOOLS=1 to allow system PATH fallback for development only."
    }

    $command = Get-Command -Name $ToolName -ErrorAction SilentlyContinue
    if ($command -and $command.Source) { return [string]$command.Source }

    $exeCommand = Get-Command -Name "$ToolName.exe" -ErrorAction SilentlyContinue
    if ($exeCommand -and $exeCommand.Source) { return [string]$exeCommand.Source }

    throw "$ToolName executable not found in bundled path or system PATH."
}

function New-StageErrorFromException {
    param(
        [Parameter(Mandatory = $true)] [System.Management.Automation.ErrorRecord] $CaughtError
    )

    $message = [string]$CaughtError.Exception.Message
    $code = 'stage.runtime_error'
    if ($message -match '^missing required payload field ' -or
        $message -match '^unsupported schema_version ' -or
        $message -match '^payload stage ' -or
        $message -match '^unknown .* field ' -or
        $message -match '^payload field ') {
        $code = 'stage.invalid_payload'
    } elseif ($message -match 'bundled executable not found|executable not found') {
        $code = 'stage.tool_missing'
    }

    return New-StageError -Code $code -Message $message -Details ([ordered]@{
        exception_type = $CaughtError.Exception.GetType().FullName
    })
}

. (Join-Path $PSScriptRoot 'probe\stage.ps1')
. (Join-Path $PSScriptRoot 'decide\stage.ps1')

$startedAt = Get-UtcNow
$stageName = ([string]$Stage).Trim().ToLowerInvariant()

try {
    $knownStages = @('ingest','probe','decide','transcode','subtitle-convert','audio-mix','publish','drain','rename')
    if ($stageName -notin $knownStages) {
        Write-StageResult -StageName $stageName -Ok:$false -StartedAt $startedAt -ErrorRecord (
            New-StageError -Code 'stage.unknown' -Message "Unknown stage '$stageName'."
        )
        exit 2
    }

    $document = Read-PayloadDocument -RawPayload $PayloadJson
    $payload = Get-StagePayload -Document $document -StageName $stageName
    Assert-StagePayloadContract -StageName $stageName -Payload $payload

    switch ($stageName) {
        'probe' {
            $data = Invoke-ProbeStage -Payload $payload
            Write-StageResult -StageName $stageName -Ok:$true -StartedAt $startedAt -Data $data
            exit 0
        }
        'decide' {
            $data = Invoke-DecideStage -Payload $payload
            Write-StageResult -StageName $stageName -Ok:$true -StartedAt $startedAt -Data $data
            exit 0
        }
        default {
            Write-StageResult -StageName $stageName -Ok:$false -StartedAt $startedAt -ErrorRecord (
                New-StageError `
                    -Code 'stage.not_enabled' `
                    -Message "Stage '$stageName' is declared but is not enabled in engine/entrypoint.ps1 during this additive Phase 3 slice."
            )
            exit 2
        }
    }
} catch {
    Write-StageResult -StageName $stageName -Ok:$false -StartedAt $startedAt -ErrorRecord (New-StageErrorFromException -CaughtError $_)
    exit 1
}
