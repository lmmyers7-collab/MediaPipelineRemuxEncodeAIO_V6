[CmdletBinding()]
param(
    [ValidateSet('Both', 'Codex', 'Claude')]
    [string]$Clients = 'Both',

    [switch]$Apply,
    [switch]$Remove,
    [switch]$Replace,
    [switch]$RemoveEnvironment
)

$ErrorActionPreference = 'Stop'

if ($Apply -and $Remove) {
    throw 'Choose either -Apply or -Remove, not both.'
}
if ($RemoveEnvironment -and -not $Remove) {
    throw '-RemoveEnvironment requires -Remove.'
}

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$ServerName = 'mediapipeline-code'
$ModuleName = 'mediapipeline.tools.dev.code_context_mcp'
$RequirementsPath = Join-Path $RepoRoot 'requirements\mcp.txt'
$RunnerPath = Join-Path $RepoRoot 'ops\scripts\dev\run-python-tool.py'
$BundledPython = Join-Path $RepoRoot 'apps\desktop\runtime\Python\python.exe'
$EnvironmentRoot = Join-Path $RepoRoot 'LocalBase\Tooling\code-context-mcp\.venv'
$EnvironmentPython = Join-Path $EnvironmentRoot 'Scripts\python.exe'

function Resolve-CodexCli {
    if ($env:CODEX_CLI_PATH -and (Test-Path -LiteralPath $env:CODEX_CLI_PATH -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $env:CODEX_CLI_PATH).Path
    }
    $binRoot = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin'
    if (Test-Path -LiteralPath $binRoot -PathType Container) {
        $candidate = Get-ChildItem -LiteralPath $binRoot -Filter codex.exe -File -Recurse |
            Sort-Object LastWriteTimeUtc -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }
    $command = Get-Command codex -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    return $null
}

function Resolve-ClaudeCli {
    $command = Get-Command claude -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    return $null
}

function Get-CodexRegistration {
    param([Parameter(Mandatory)][string]$CommandPath)

    $raw = & $CommandPath mcp get $ServerName --json 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $raw) {
        return $null
    }
    try {
        return ($raw | Out-String | ConvertFrom-Json)
    }
    catch {
        throw "Codex returned an unreadable MCP registration for $ServerName."
    }
}

function Test-CodexRegistrationMatches {
    param([Parameter(Mandatory)]$Registration)

    if ($Registration.transport.type -ne 'stdio') {
        return $false
    }
    $actualCommand = [string]$Registration.transport.command
    $actualArgs = @($Registration.transport.args | ForEach-Object { [string]$_ })
    $expectedArgs = @($RunnerPath, $ModuleName)
    return $actualCommand.Equals($EnvironmentPython, [StringComparison]::OrdinalIgnoreCase) -and
        (($actualArgs -join "`n").Equals(($expectedArgs -join "`n"), [StringComparison]::OrdinalIgnoreCase))
}

function Get-ClaudeRegistration {
    param([Parameter(Mandatory)][string]$CommandPath)

    $raw = & $CommandPath mcp get $ServerName 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $raw) {
        return $null
    }
    return ($raw | Out-String)
}

function Test-ClaudeRegistrationMatches {
    param([Parameter(Mandatory)][string]$RegistrationText)

    return $RegistrationText.Contains($EnvironmentPython, [StringComparison]::OrdinalIgnoreCase) -and
        $RegistrationText.Contains($RunnerPath, [StringComparison]::OrdinalIgnoreCase) -and
        $RegistrationText.Contains($ModuleName, [StringComparison]::OrdinalIgnoreCase)
}

function Install-McpEnvironment {
    if (-not (Test-Path -LiteralPath $BundledPython -PathType Leaf)) {
        throw "Bundled Python is missing: $BundledPython"
    }
    if (-not (Test-Path -LiteralPath $RequirementsPath -PathType Leaf)) {
        throw "MCP requirements file is missing: $RequirementsPath"
    }
    if (-not (Test-Path -LiteralPath $EnvironmentPython -PathType Leaf)) {
        & $BundledPython -m venv $EnvironmentRoot
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to create the isolated MCP Python environment.'
        }
    }
    & $EnvironmentPython -m pip install --disable-pip-version-check -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to install the MCP dependency.'
    }
}

function Set-CodexRegistration {
    param([Parameter(Mandatory)][string]$CommandPath)

    $existing = Get-CodexRegistration -CommandPath $CommandPath
    if ($existing -and (Test-CodexRegistrationMatches -Registration $existing)) {
        Write-Host "Codex registration already matches: $ServerName"
        return
    }
    if ($existing -and -not $Replace) {
        throw "Codex already has a different '$ServerName' registration. Re-run with -Replace to replace it."
    }
    if ($existing) {
        & $CommandPath mcp remove $ServerName
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to remove the existing Codex MCP registration.'
        }
    }
    & $CommandPath mcp add $ServerName -- $EnvironmentPython $RunnerPath $ModuleName
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to add the Codex MCP registration.'
    }
}

function Set-ClaudeRegistration {
    param([Parameter(Mandatory)][string]$CommandPath)

    $existing = Get-ClaudeRegistration -CommandPath $CommandPath
    if ($existing -and (Test-ClaudeRegistrationMatches -RegistrationText $existing)) {
        Write-Host "Claude registration already matches: $ServerName"
        return
    }
    if ($existing -and -not $Replace) {
        throw "Claude already has a different '$ServerName' registration. Re-run with -Replace to replace it."
    }
    if ($existing) {
        & $CommandPath mcp remove --scope local $ServerName
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to remove the existing Claude MCP registration.'
        }
    }
    & $CommandPath mcp add --scope local $ServerName -- $EnvironmentPython $RunnerPath $ModuleName
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to add the Claude MCP registration.'
    }
}

function Remove-CodexRegistration {
    param([Parameter(Mandatory)][string]$CommandPath)

    $existing = Get-CodexRegistration -CommandPath $CommandPath
    if (-not $existing) {
        Write-Host "Codex registration is already absent: $ServerName"
        return
    }
    if (-not (Test-CodexRegistrationMatches -Registration $existing)) {
        throw "Refusing to remove a Codex '$ServerName' registration that does not point to this repository."
    }
    & $CommandPath mcp remove $ServerName
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to remove the Codex MCP registration.'
    }
}

function Remove-ClaudeRegistration {
    param([Parameter(Mandatory)][string]$CommandPath)

    $existing = Get-ClaudeRegistration -CommandPath $CommandPath
    if (-not $existing) {
        Write-Host "Claude registration is already absent: $ServerName"
        return
    }
    if (-not (Test-ClaudeRegistrationMatches -RegistrationText $existing)) {
        throw "Refusing to remove a Claude '$ServerName' registration that does not point to this repository."
    }
    & $CommandPath mcp remove --scope local $ServerName
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to remove the Claude MCP registration.'
    }
}

$CodexCli = if ($Clients -in @('Both', 'Codex')) { Resolve-CodexCli } else { $null }
$ClaudeCli = if ($Clients -in @('Both', 'Claude')) { Resolve-ClaudeCli } else { $null }

if ($Clients -in @('Both', 'Codex') -and -not $CodexCli) {
    throw 'Codex CLI was not found.'
}
if ($Clients -in @('Both', 'Claude') -and -not $ClaudeCli) {
    throw 'Claude CLI was not found.'
}

if (-not $Apply -and -not $Remove) {
    [ordered]@{
        action = 'preview'
        server_name = $ServerName
        clients = $Clients
        environment_python = $EnvironmentPython
        runner = $RunnerPath
        module = $ModuleName
        codex_cli = $CodexCli
        claude_cli = $ClaudeCli
    } | ConvertTo-Json -Depth 4
    exit 0
}

if ($Apply) {
    Install-McpEnvironment
    if ($CodexCli) {
        Set-CodexRegistration -CommandPath $CodexCli
    }
    if ($ClaudeCli) {
        Set-ClaudeRegistration -CommandPath $ClaudeCli
    }
    Write-Host "Configured $ServerName for $Clients. Restart clients or open a new session to load it."
    exit 0
}

if ($CodexCli) {
    Remove-CodexRegistration -CommandPath $CodexCli
}
if ($ClaudeCli) {
    Remove-ClaudeRegistration -CommandPath $ClaudeCli
}
if ($RemoveEnvironment -and (Test-Path -LiteralPath $EnvironmentRoot)) {
    $expectedRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'LocalBase\Tooling\code-context-mcp\.venv'))
    $actualRoot = [IO.Path]::GetFullPath($EnvironmentRoot)
    if (-not $actualRoot.Equals($expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove unexpected environment path: $actualRoot"
    }
    Remove-Item -LiteralPath $actualRoot -Recurse -Force
    Write-Host "Removed isolated MCP environment: $actualRoot"
}
