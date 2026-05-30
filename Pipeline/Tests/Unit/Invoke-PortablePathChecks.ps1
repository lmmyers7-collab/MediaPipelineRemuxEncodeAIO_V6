[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Portable path checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$auditScript = Join-Path $pipelineRoot 'Audit-MediaLibrary.ps1'
$legacyGuiScript = Join-Path $pipelineRoot 'MediaPipelineRemuxEncodeAIO_LegacyGUI.ps1'

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-PowerShellParses {
    param([string]$Path)

    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors -and $errors.Count -gt 0) {
        $details = ($errors | ForEach-Object { "$($_.Extent.StartLineNumber):$($_.Message)" }) -join '; '
        throw "PowerShell parser errors in ${Path}: $details"
    }
}

Assert-PowerShellParses -Path $auditScript

$auditText = Get-Content -LiteralPath $auditScript -Raw
if (Test-Path -LiteralPath $legacyGuiScript -PathType Leaf) {
    Assert-PowerShellParses -Path $legacyGuiScript
    $legacyText = Get-Content -LiteralPath $legacyGuiScript -Raw
} else {
    $legacyText = ''
}

Assert-True ($auditText -notmatch "\[string\]\`$LibraryRoot\s*=\s*'\\\\LAYNE-SERVER\\Video'") 'Audit script must not default LibraryRoot to a local operator UNC path.'
Assert-True ($auditText -match "Get-AuditDefaultLibraryRootFromConfig") 'Audit script must derive the default library root from config when -LibraryRoot is omitted.'
Assert-True ($auditText -match "LibraryRoot was not provided") 'Audit script must fail clearly when no config-derived library root is available.'

if ($legacyText) {
    Assert-True ($legacyText -notmatch "\`$txtAuditRoot\.Text\s*=\s*'\\\\LAYNE-SERVER\\Video'") 'Legacy GUI must not seed Audit root with a local operator UNC path.'
    Assert-True ($legacyText -match "Get-DefaultAuditRootFromUiState") 'Legacy GUI must derive the Audit root from loaded config state.'
    Assert-True ($legacyText -match "\`$txtAuditRoot\.Text\s*=\s*''") 'Legacy GUI Audit root should start blank until config is loaded.'
}

Write-Host 'Portable path checks passed.'
