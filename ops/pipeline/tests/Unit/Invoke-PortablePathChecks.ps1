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
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}
$auditScript = Join-Path $pipelineRoot 'entrypoints\Audit-MediaLibrary.ps1'
$legacyGuiScript = Join-Path $pipelineRoot 'MediaPipelineRemuxEncodeAIO_LegacyGUI.ps1'
$configTemplate = Join-Path $pipelineRoot 'config\MediaPipeline_config_template.psd1'
$defaultProfile = Join-Path $pipelineRoot 'config\profiles\Default.psd1'

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
Assert-PowerShellParses -Path $configTemplate
Assert-PowerShellParses -Path $defaultProfile

$auditText = Get-Content -LiteralPath $auditScript -Raw
$configTemplateText = Get-Content -LiteralPath $configTemplate -Raw
$defaultProfileText = Get-Content -LiteralPath $defaultProfile -Raw
if (Test-Path -LiteralPath $legacyGuiScript -PathType Leaf) {
    Assert-PowerShellParses -Path $legacyGuiScript
    $legacyText = Get-Content -LiteralPath $legacyGuiScript -Raw
} else {
    $legacyText = ''
}

Assert-True ($auditText -notmatch "\[string\]\`$LibraryRoot\s*=\s*'\\\\LAYNE-SERVER\\Video'") 'Audit script must not default LibraryRoot to a local operator UNC path.'
Assert-True ($auditText -match "Get-AuditDefaultLibraryRootFromConfig") 'Audit script must derive the default library root from config when -LibraryRoot is omitted.'
Assert-True ($auditText -match "LibraryRoot was not provided") 'Audit script must fail clearly when no config-derived library root is available.'
Assert-True ($configTemplateText -notmatch 'LAYNE|Layne|LAYNE-SERVER|E:/Videos|//LAYNE|Users/Layne') 'Config template must not include local operator path defaults.'
Assert-True ($defaultProfileText -notmatch 'LAYNE|Layne|LAYNE-SERVER|E:/Videos|//LAYNE|Users/Layne') 'Default config profile must not include local operator path defaults.'

if ($legacyText) {
    Assert-True ($legacyText -notmatch "\`$txtAuditRoot\.Text\s*=\s*'\\\\LAYNE-SERVER\\Video'") 'Legacy GUI must not seed Audit root with a local operator UNC path.'
    Assert-True ($legacyText -match "Get-DefaultAuditRootFromUiState") 'Legacy GUI must derive the Audit root from loaded config state.'
    Assert-True ($legacyText -match "\`$txtAuditRoot\.Text\s*=\s*''") 'Legacy GUI Audit root should start blank until config is loaded.'
}

Write-Host 'Portable path checks passed.'
