Set-StrictMode -Version 2.0

function Normalize-MediaPipelineReleaseRelativePath {
    param([Parameter(Mandatory)][string]$RelativePath)
    return (($RelativePath -replace '/', '\').TrimStart('\'))
}

function Find-MediaPipelineReleaseContentFinding {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RelativePath,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Content
    )

    $checks = @(
        @{ Pattern = '(?i)[a-z]:[\\/]+users[\\/]'; Label = 'user-profile path' },
        @{ Pattern = '(?i)(?:%localappdata%|%appdata%|appdata[\\/]+local[\\/]+temp)'; Label = 'AppData or temp path' },
        @{ Pattern = '(?<!\\)\\\\[^\\\s]+\\[^\\\s]+'; Label = 'UNC path' },
        @{ Pattern = '(?i)authorization\s*:\s*bearer\s+(?![<{])[^\s"'']{8,}'; Label = 'bearer token' },
        @{ Pattern = '(?i)-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----'; Label = 'private key material' },
        @{ Pattern = '(?i)\b(?:password|credential|secret|workerauthtoken)\b\s*[:=]\s*["''][^"'']{8,}["'']'; Label = 'credential-like assignment' }
    )
    $opsRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $allowlistPath = Join-Path $opsRoot 'release\metadata\release_content_allowlist.json'
    $allowlist = @()
    if (Test-Path -LiteralPath $allowlistPath -PathType Leaf) {
        try { $allowlist = @((Get-Content -LiteralPath $allowlistPath -Raw | ConvertFrom-Json).entries) } catch { throw "Release content allowlist is invalid: $allowlistPath" }
    }
    foreach ($check in $checks) {
        $matches = [regex]::Matches($Content, $check.Pattern)
        foreach ($match in $matches) {
            $allowed = @($allowlist | Where-Object {
                $_.relative_path -eq $RelativePath -and
                $_.pattern -and
                $_.reason -and
                $_.expires_on -and
                [datetime]$_.expires_on -ge (Get-Date) -and
                [regex]::IsMatch([string]$match.Value, [string]$_.pattern)
            }).Count -gt 0
            if ($allowed) { continue }
            return "$($check.Label) in $RelativePath"
        }
    }
    return $null
}

function Test-MediaPipelineReleaseContentScanEligible {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$RelativePath)

    $relative = Normalize-MediaPipelineReleaseRelativePath -RelativePath $RelativePath
    if ($relative -like 'docs\*') { return $true }
    if ($relative -like 'ops\pipeline\config\*') { return $true }
    # Executable/runtime source is protected by the file-hash manifest. Text
    # privacy scanning is intentionally scoped to human/configuration content
    # where a literal live value is meaningful rather than a language example.
    return $false
}

function Test-MediaPipelineReleaseContentAllowed {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RelativePath,
        [Parameter(Mandatory)][string]$Content
    )

    return $null -eq (Find-MediaPipelineReleaseContentFinding -RelativePath $RelativePath -Content $Content)
}

function Get-MediaPipelineReleaseExclusionReason {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RelativePath,
        [bool]$IncludeTests = $false,
        [bool]$IncludeDevDocs = $false,
        [bool]$IncludeOptionalTools = $false,
        [bool]$IncludeToolDocs = $false,
        [bool]$KeepPersonalConfig = $false
    )

    $relative = Normalize-MediaPipelineReleaseRelativePath -RelativePath $RelativePath
    $name = Split-Path -Leaf $relative
    $segments = @($relative -split '\\' | Where-Object { $_ })
    $reservedDeviceNames = @('CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9')
    foreach ($segment in $segments) {
        $deviceCandidate = [System.IO.Path]::GetFileNameWithoutExtension($segment).ToUpperInvariant()
        if ($reservedDeviceNames -contains $deviceCandidate) { return 'windows reserved device name' }
    }

    if ($segments -contains '.git') { return 'git metadata' }
    if ($segments -contains '.github') { return 'source-control metadata' }
    if ($segments -contains '.claude' -or $segments -contains '.codex' -or $segments -contains '.codex-plugin') { return 'local assistant metadata' }
    if ($segments -contains '__pycache__') { return 'python bytecode cache' }
    if ($segments -contains '.pytest_cache' -or $segments -contains '.mypy_cache' -or $segments -contains '.ruff_cache') { return 'test/tool cache' }
    if ($name -like '*.pyc' -or $name -like '*.pyo') { return 'python bytecode cache' }
    if ($relative -like 'CodexVerification\*') { return 'local verification evidence' }
    if ($relative -like 'LocalBase\*') { return 'local runtime state' }
    if ($relative -like 'RunLogs\*') { return 'root runtime logs' }
    if ($relative -like 'artifacts\*') { return 'generated proof artifact' }
    if ($segments.Count -eq 1 -and $name -eq '.release_in_progress.json') { return 'partial release build marker' }
    if ($segments.Count -eq 1 -and $name -like '*.log') { return 'root runtime log' }
    if ($segments.Count -eq 1 -and $name -like '*.state.json') { return 'root runtime state' }
    if ($segments.Count -eq 1 -and $name -like '*_AUDIT.md') { return 'generated audit/report artifact' }
    if ($segments.Count -eq 1 -and $name -like '*_REPORT.md') { return 'generated audit/report artifact' }
    if ($relative -in @(
        'CODE_REVIEW_WEBVIEW_TAURI_AUDIT.md',
        'DOCS_HOUSEKEEPING_AUDIT.md',
        'DOCS_HOUSEKEEPING_MOVE_PLAN_BLOCKED.md',
        'DOCS_HOUSEKEEPING_POST_MOVE_REPORT.md'
    )) { return 'generated audit/report artifact' }
    if ($relative -like 'docs_housekeeping_catalog.*') { return 'generated documentation housekeeping catalog' }
    if ($relative -like 'apps\desktop\tauri\node_modules\*') { return 'tauri node modules omitted' }
    if ($segments -contains 'node_modules') { return 'node modules omitted' }
    if ($relative -like 'apps\desktop\tauri\src-tauri\gen\*') { return 'tauri generated schema output omitted' }
    if ($relative -like 'apps\desktop\tauri\src-tauri\target\*') { return 'tauri rust build output omitted' }
    if ($name -like '~$*') { return 'Office lock/temp file' }
    if ($name -match '\.(doc|docx|docm|dotx|xlsx|xlsm|pptx|pptm)$') { return 'local Office working document' }
    if ($name -in @('.gitignore', '.gitattributes')) { return 'source-control metadata' }

    if (-not $IncludeOptionalTools) {
        if ($relative -eq 'ops\pipeline\tools\ffmpeg\bin\ffplay.exe') { return 'optional media playback tool omitted' }
        if ($relative -match '^ops\\pipeline\\tools\\MKVToolNix\\(mkvtoolnix-gui|mkvextract|mkvinfo|mkvpropedit|uninst)\.exe$') { return 'optional MKVToolNix tool omitted' }
        if ($relative -eq 'ops\pipeline\tools\MKVToolNix\MKVToolNix.url') { return 'optional MKVToolNix shortcut omitted' }
        if ($relative -like 'ops\pipeline\tools\MKVToolNix\tools\*') { return 'optional MKVToolNix diagnostic tool omitted' }
        if ($relative -like 'ops\pipeline\tools\MKVToolNix\data\*') { return 'optional MKVToolNix GUI asset omitted' }
        if ($relative -like 'ops\pipeline\tools\MKVToolNix\locale\libqt\*') { return 'optional MKVToolNix GUI locale omitted' }
    }

    if (-not $IncludeToolDocs) {
        if ($relative -like 'ops\pipeline\tools\MKVToolNix\doc\*') { return 'bundled tool documentation omitted' }
        if ($relative -like 'ops\pipeline\tools\MKVToolNix\examples\*') { return 'bundled tool examples omitted' }
    }

    if ($relative -like 'apps\desktop\runlogs\*') { return 'desktop run logs' }
    if ($relative -like 'apps\desktop\*.log') { return 'desktop runtime log' }
    if ($relative -like 'apps\desktop\*.state.json') { return 'desktop local state' }
    if ($relative -eq 'apps\desktop\encode_speed_history.json') { return 'desktop local telemetry' }
    if ($relative -like 'DesktopApp\*.log') { return 'desktop runtime log' }
    if ($relative -like 'DesktopApp\*.state.json') { return 'desktop local state' }
    if ($relative -eq 'DesktopApp\encode_speed_history.json') { return 'desktop local telemetry' }

    if ($relative -like 'docs\RealMediaValidationRuns\*' -and $name -ne 'README.md') { return 'operator real-media validation evidence omitted' }
    if ($relative -like 'docs\PG3CleanMachineReports\*') { return 'operator clean-machine validation evidence omitted' }
    if ($relative -like 'docs\reviews\*') { return 'active review/audit ledger omitted' }
    if ($relative -like 'ops\release\changes\unreleased\*') { return 'unreleased change record omitted' }
    if ($relative -like 'docs\generated\summaries\ops\release\changes\unreleased\*') { return 'unreleased change record summary omitted' }
    if ($relative -like 'ops\release\changes\archived\*') { return 'archived unreleased change record omitted' }
    if ($relative -like 'docs\generated\summaries\ops\release\changes\archived\*') { return 'archived unreleased change record summary omitted' }
    if ($relative -like 'docs\archive\remediation-changelog\*') { return 'historical remediation ledger segment omitted' }
    if ($relative -eq 'docs\REMEDIATION_CHANGELOG.md') { return 'historical remediation ledger omitted' }
    if ($relative -eq 'docs\CURRENT_PROJECT_STATE.md') { return 'volatile project status omitted' }
    if ($relative -eq 'docs\OPEN_WORK_CHECKLIST.md') { return 'developer backlog omitted' }
    if ($relative -eq 'docs\inventories\TEST_SUITE_SUBSYSTEM_INVENTORY.md') { return 'developer test inventory omitted' }
    if ($relative -like 'docs\archive\root-artifacts\*') { return 'local assistant root artifact' }

    if ($relative -like 'Pipeline\*.log' -or $relative -like 'Pipeline\*.tmp' -or $relative -like 'Pipeline\*.bak') { return 'pipeline runtime artifact' }
    if ($relative -like 'ops\pipeline\*.log' -or $relative -like 'ops\pipeline\*.tmp' -or $relative -like 'ops\pipeline\*.bak') { return 'pipeline runtime artifact' }
    if ($relative -like 'Pipeline\*_progress.json' -or $relative -eq 'Pipeline\pipeline_progress.json' -or $relative -eq 'Pipeline\audit_progress.json') { return 'pipeline runtime state' }
    if ($relative -like 'ops\pipeline\*_progress.json') { return 'pipeline runtime state' }
    if ($relative -like 'Pipeline\MediaPipeline_config.backup_*.psd1' -or $relative -like 'ops\pipeline\config\MediaPipeline_config.backup_*.psd1' -or $relative -like 'ops\pipeline\config\MediaPipeline_config.psd1.bak.*') { return 'generated config backup' }
    if ($relative -like 'Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1' -or $relative -like 'ops\pipeline\config\MediaPipeline_config_chatgpt.backup_*.psd1' -or $relative -like 'ops\pipeline\config\MediaPipeline_config_chatgpt.psd1.bak.*') { return 'generated config backup (legacy)' }
    if ($relative -like 'ops\pipeline\config\backups\*.psd1') { return 'generated config backup' }
    if ((-not $KeepPersonalConfig) -and $relative -eq 'ops\pipeline\config\MediaPipeline_config.psd1') { return 'personal live config' }
    if ((-not $KeepPersonalConfig) -and $relative -eq 'ops\pipeline\config\MediaPipeline_config_chatgpt.psd1') { return 'personal live config (legacy)' }
    if ($relative -like 'src\*.log') { return 'python source-tree runtime log' }
    if ($relative -like 'src\*.egg-info\*') { return 'python packaging metadata' }

    if (-not $IncludeTests) {
        if ($relative -like 'ops\pipeline\tests\*') { return 'test suite omitted' }
        if ($relative -like 'tests\*') { return 'test suite omitted' }
    }

    if (-not $IncludeDevDocs) {
        if ($relative -like 'docs\archive\docs-housekeeping\*') { return 'documentation housekeeping quarantine omitted' }
        if ($name -in @(
            'CODE_CLEANUP_CHECKLIST.md',
            'CONTROL_SURFACE_HARDENING_CHECKLIST.md',
            'DEPLOYABILITY_CHECKLIST.md',
            'NETWORK_MODE_CHECKLIST.md',
            'UI_CHECKLIST.md',
            'UI_CHECKLIST_2.md',
            'UI_CHECKLIST_3.md',
            'UI_IMPROVEMENT_CHECKLIST.md',
            'V4_MIGRATION_NOTES.md'
        )) { return 'development checklist/doc omitted' }
    }

    return $null
}

function New-MediaPipelineReleaseHygieneRule {
    param(
        [Parameter(Mandatory)][ValidateSet('path_absent', 'pattern_absent', 'path_present')][string]$Kind,
        [string]$RelativePath = '',
        [string]$RelativePattern = '',
        [Parameter(Mandatory)][string]$Label
    )

    return [pscustomobject]@{
        kind = $Kind
        relative_path = $RelativePath
        relative_pattern = $RelativePattern
        label = $Label
    }
}

function Get-MediaPipelineReleaseHygieneRules {
    [CmdletBinding()]
    param(
        [bool]$PersonalConfigIncluded = $false,
        [bool]$DevDocsIncluded = $false,
        [bool]$OptionalToolsIncluded = $false,
        [bool]$ToolDocsIncluded = $false,
        [bool]$TauriPreviewBinaryIncluded = $false
    )

    $rules = [System.Collections.Generic.List[object]]::new()
    foreach ($rule in @(
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath '.git' -Label 'git metadata'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath '.github' -Label 'source-control metadata'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath '.gitignore' -Label 'source-control metadata'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath '.gitattributes' -Label 'source-control metadata'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath '.claude' -Label 'local assistant metadata'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath '.codex' -Label 'local assistant metadata'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath '.codex-plugin' -Label 'local assistant metadata'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'CodexVerification' -Label 'local verification evidence'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'LocalBase' -Label 'local runtime state'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'RunLogs' -Label 'root runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath '.release_in_progress.json' -Label 'partial release build marker'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'artifacts' -Label 'generated proof artifacts'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern '*.log' -Label 'root runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern '*.state.json' -Label 'root runtime state files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern '*_AUDIT.md' -Label 'root generated audit documents'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern '*_REPORT.md' -Label 'root generated report documents'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'CODE_REVIEW_WEBVIEW_TAURI_AUDIT.md' -Label 'generated code review audit'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DOCS_HOUSEKEEPING_AUDIT.md' -Label 'generated docs housekeeping audit'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DOCS_HOUSEKEEPING_MOVE_PLAN_BLOCKED.md' -Label 'generated docs housekeeping move plan'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DOCS_HOUSEKEEPING_POST_MOVE_REPORT.md' -Label 'generated docs housekeeping post-move report'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'docs_housekeeping_catalog.*' -Label 'generated docs housekeeping catalog'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'apps\desktop\runlogs' -Label 'desktop run logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'apps\desktop\*.log' -Label 'desktop runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'apps\desktop\*.state.json' -Label 'desktop local state files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'apps\desktop\encode_speed_history.json' -Label 'desktop local telemetry'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DesktopApp' -Label 'legacy desktop source root'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'DesktopApp\*.log' -Label 'desktop runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'DesktopApp\*.state.json' -Label 'desktop local state files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DesktopApp\encode_speed_history.json' -Label 'desktop local telemetry'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'node_modules' -Label 'root Node.js packages'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'apps\desktop\tauri\node_modules' -Label 'Tauri node modules'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'apps\desktop\tauri\src-tauri\gen' -Label 'Tauri generated schemas'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'apps\desktop\tauri\src-tauri\target' -Label 'Tauri Rust build output'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'docs\PG3CleanMachineReports' -Label 'PG-3 clean-machine operator reports'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'docs\reviews' -Label 'active review/audit ledgers'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'docs\archive\root-artifacts' -Label 'local assistant root artifacts'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\MediaPipeline_config.backup_*.psd1' -Label 'generated config backups'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1' -Label 'generated config backups (legacy)'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'ops\pipeline\config\MediaPipeline_config.backup_*.psd1' -Label 'generated config backups'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'ops\pipeline\config\MediaPipeline_config_chatgpt.backup_*.psd1' -Label 'generated config backups (legacy)'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'ops\pipeline\config\backups' -Label 'generated config backup folder'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'ops\pipeline\config\backups\*.psd1' -Label 'generated config backups'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\*.log' -Label 'pipeline runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\*.tmp' -Label 'pipeline runtime temp files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\*.bak' -Label 'pipeline runtime backup files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\*_progress.json' -Label 'pipeline runtime progress files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'ops\pipeline\*.log' -Label 'pipeline runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'ops\pipeline\*.tmp' -Label 'pipeline runtime temp files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'ops\pipeline\*.bak' -Label 'pipeline runtime backup files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'ops\pipeline\*_progress.json' -Label 'pipeline runtime progress files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'src\*.log' -Label 'python source-tree runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'src\*.egg-info\*' -Label 'python packaging metadata'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern '~$*' -Label 'Office lock/temp files')
    )) {
        [void]$rules.Add($rule)
    }

    foreach ($pattern in @('*.doc', '*.docx', '*.docm', '*.dotx', '*.xlsx', '*.xlsm', '*.pptx', '*.pptm')) {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern $pattern -Label 'local Office working documents'))
    }

    if (-not $DevDocsIncluded) {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'docs\archive\docs-housekeeping' -Label 'docs housekeeping quarantine'))
    }

    if ($TauriPreviewBinaryIncluded) {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_present' -RelativePath 'apps\desktop\tauri\mediapipeline-tauri-shell.exe' -Label 'Tauri preview packaged executable'))
    } else {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'apps\desktop\tauri\mediapipeline-tauri-shell.exe' -Label 'Tauri preview packaged executable'))
    }

    if (-not $PersonalConfigIncluded) {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'ops\pipeline\config\MediaPipeline_config.psd1' -Label 'personal live config'))
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'ops\pipeline\config\MediaPipeline_config_chatgpt.psd1' -Label 'personal live config (legacy)'))
    }

    if (-not $OptionalToolsIncluded) {
        foreach ($relative in @(
            'ops\pipeline\tools\ffmpeg\bin\ffplay.exe',
            'ops\pipeline\tools\MKVToolNix\mkvtoolnix-gui.exe',
            'ops\pipeline\tools\MKVToolNix\mkvextract.exe',
            'ops\pipeline\tools\MKVToolNix\mkvinfo.exe',
            'ops\pipeline\tools\MKVToolNix\mkvpropedit.exe',
            'ops\pipeline\tools\MKVToolNix\uninst.exe',
            'ops\pipeline\tools\MKVToolNix\MKVToolNix.url',
            'ops\pipeline\tools\MKVToolNix\tools',
            'ops\pipeline\tools\MKVToolNix\data',
            'ops\pipeline\tools\MKVToolNix\locale\libqt'
        )) {
            [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath $relative -Label 'optional tool bulk'))
        }
    }

    if (-not $ToolDocsIncluded) {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'ops\pipeline\tools\MKVToolNix\doc' -Label 'bundled tool documentation'))
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'ops\pipeline\tools\MKVToolNix\examples' -Label 'bundled tool examples'))
    }

    return @($rules.ToArray())
}

function Get-MediaPipelineReleasePolicyManifest {
    [CmdletBinding()]
    param(
        [bool]$IncludeTests = $false,
        [bool]$IncludeDevDocs = $false,
        [bool]$IncludeOptionalTools = $false,
        [bool]$IncludeToolDocs = $false,
        [bool]$IncludeTauriPreviewBinary = $false,
        [bool]$KeepPersonalConfig = $false
    )

    $rules = @(
        Get-MediaPipelineReleaseHygieneRules `
            -PersonalConfigIncluded:$KeepPersonalConfig `
            -DevDocsIncluded:$IncludeDevDocs `
            -OptionalToolsIncluded:$IncludeOptionalTools `
            -ToolDocsIncluded:$IncludeToolDocs `
            -TauriPreviewBinaryIncluded:$IncludeTauriPreviewBinary
    )

    return [ordered]@{
        schema_version = 'mediapipeline_release_policy.v1'
        policy_module = 'ops\scripts\release\release_policy.ps1'
        include_tests = [bool]$IncludeTests
        include_dev_docs = [bool]$IncludeDevDocs
        include_optional_tools = [bool]$IncludeOptionalTools
        include_tool_docs = [bool]$IncludeToolDocs
        include_tauri_preview_binary = [bool]$IncludeTauriPreviewBinary
        keep_personal_config = [bool]$KeepPersonalConfig
        hygiene_rule_count = $rules.Count
    }
}
