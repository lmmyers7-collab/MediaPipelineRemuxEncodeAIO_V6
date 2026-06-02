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
        $message -match '^payload stage ') {
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
