Set-StrictMode -Version 2.0

function Normalize-MediaPipelineReleaseRelativePath {
    param([Parameter(Mandatory)][string]$RelativePath)
    return (($RelativePath -replace '/', '\').TrimStart('\'))
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

    if ($segments -contains '.git') { return 'git metadata' }
    if ($segments -contains '.claude') { return 'local assistant metadata' }
    if ($segments -contains '__pycache__') { return 'python bytecode cache' }
    if ($segments -contains '.pytest_cache' -or $segments -contains '.mypy_cache' -or $segments -contains '.ruff_cache') { return 'test/tool cache' }
    if ($name -like '*.pyc' -or $name -like '*.pyo') { return 'python bytecode cache' }
    if ($relative -like 'CodexVerification\*') { return 'local verification evidence' }
    if ($relative -like 'LocalBase\*') { return 'local runtime state' }
    if ($relative -like 'RunLogs\*') { return 'root runtime logs' }
    if ($segments.Count -eq 1 -and $name -like '*.log') { return 'root runtime log' }
    if ($segments.Count -eq 1 -and $name -like '*.state.json') { return 'root runtime state' }
    if ($segments.Count -eq 1 -and $name -like '*_AUDIT.md') { return 'generated audit/report artifact' }
    if ($segments.Count -eq 1 -and $name -like '*_REPORT.md') { return 'generated audit/report artifact' }
    if ($relative -in @(
        'CODE_REVIEW_V5_WEBVIEW_TAURI_AUDIT.md',
        'DOCS_HOUSEKEEPING_AUDIT.md',
        'DOCS_HOUSEKEEPING_MOVE_PLAN_BLOCKED.md',
        'DOCS_HOUSEKEEPING_POST_MOVE_REPORT.md'
    )) { return 'generated audit/report artifact' }
    if ($relative -like 'docs_housekeeping_catalog.*') { return 'generated documentation housekeeping catalog' }
    if ($relative -like 'DesktopApp\tauri_shell\node_modules\*') { return 'tauri node modules omitted' }
    if ($segments -contains 'node_modules') { return 'node modules omitted' }
    if ($relative -like 'DesktopApp\tauri_shell\src-tauri\gen\*') { return 'tauri generated schema output omitted' }
    if ($relative -like 'DesktopApp\tauri_shell\src-tauri\target\*') { return 'tauri rust build output omitted' }
    if ($name -like '~$*') { return 'Office lock/temp file' }
    if ($name -match '\.(doc|docx|docm|dotx|xlsx|xlsm|pptx|pptm)$') { return 'local Office working document' }
    if ($name -eq '.gitignore') { return 'source-control metadata' }

    if (-not $IncludeOptionalTools) {
        if ($relative -eq 'Pipeline\Tools\ffmpeg\bin\ffplay.exe') { return 'optional media playback tool omitted' }
        if ($relative -match '^Pipeline\\Tools\\MKVToolNix\\(mkvtoolnix-gui|mkvextract|mkvinfo|mkvpropedit|uninst)\.exe$') { return 'optional MKVToolNix tool omitted' }
        if ($relative -eq 'Pipeline\Tools\MKVToolNix\MKVToolNix.url') { return 'optional MKVToolNix shortcut omitted' }
        if ($relative -like 'Pipeline\Tools\MKVToolNix\tools\*') { return 'optional MKVToolNix diagnostic tool omitted' }
        if ($relative -like 'Pipeline\Tools\MKVToolNix\data\*') { return 'optional MKVToolNix GUI asset omitted' }
        if ($relative -like 'Pipeline\Tools\MKVToolNix\locale\libqt\*') { return 'optional MKVToolNix GUI locale omitted' }
    }

    if (-not $IncludeToolDocs) {
        if ($relative -like 'Pipeline\Tools\MKVToolNix\doc\*') { return 'bundled tool documentation omitted' }
        if ($relative -like 'Pipeline\Tools\MKVToolNix\examples\*') { return 'bundled tool examples omitted' }
    }

    if ($relative -like 'DesktopApp\RunLogs\*') { return 'desktop run logs' }
    if ($relative -like 'DesktopApp\*.log') { return 'desktop runtime log' }
    if ($relative -like 'DesktopApp\*.state.json') { return 'desktop local state' }
    if ($relative -eq 'DesktopApp\encode_speed_history.json') { return 'desktop local telemetry' }

    if ($relative -like 'Docs\RealMediaValidationRuns\*' -and $name -ne 'README.md') { return 'operator real-media validation evidence omitted' }
    if ($relative -like 'Docs\PG3CleanMachineReports\*') { return 'operator clean-machine validation evidence omitted' }

    if ($relative -like 'Pipeline\*.log' -or $relative -like 'Pipeline\*.tmp' -or $relative -like 'Pipeline\*.bak') { return 'pipeline runtime artifact' }
    if ($relative -like 'Pipeline\*_progress.json' -or $relative -eq 'Pipeline\pipeline_progress.json' -or $relative -eq 'Pipeline\audit_progress.json') { return 'pipeline runtime state' }
    if ($relative -like 'Pipeline\MediaPipeline_config.backup_*.psd1' -or $relative -like 'Pipeline\MediaPipeline_config.psd1.bak.*') { return 'generated config backup' }
    if ($relative -like 'Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1' -or $relative -like 'Pipeline\MediaPipeline_config_chatgpt.psd1.bak.*') { return 'generated config backup (legacy)' }
    if ((-not $KeepPersonalConfig) -and $relative -eq 'Pipeline\MediaPipeline_config.psd1') { return 'personal live config' }
    if ((-not $KeepPersonalConfig) -and $relative -eq 'Pipeline\MediaPipeline_config_chatgpt.psd1') { return 'personal live config (legacy)' }

    if (-not $IncludeTests) {
        if ($relative -like 'Pipeline\Tests\*') { return 'test suite omitted' }
        if ($relative -like 'DesktopApp\tests\*') { return 'test suite omitted' }
    }

    if (-not $IncludeDevDocs) {
        if ($relative -like 'Docs\archive\docs-housekeeping\*') { return 'documentation housekeeping quarantine omitted' }
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
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'CodexVerification' -Label 'local verification evidence'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'LocalBase' -Label 'local runtime state'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'RunLogs' -Label 'root runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern '*.log' -Label 'root runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern '*.state.json' -Label 'root runtime state files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern '*_AUDIT.md' -Label 'root generated audit documents'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern '*_REPORT.md' -Label 'root generated report documents'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'CODE_REVIEW_V5_WEBVIEW_TAURI_AUDIT.md' -Label 'generated code review audit'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DOCS_HOUSEKEEPING_AUDIT.md' -Label 'generated docs housekeeping audit'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DOCS_HOUSEKEEPING_MOVE_PLAN_BLOCKED.md' -Label 'generated docs housekeeping move plan'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DOCS_HOUSEKEEPING_POST_MOVE_REPORT.md' -Label 'generated docs housekeeping post-move report'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'docs_housekeeping_catalog.*' -Label 'generated docs housekeeping catalog'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DesktopApp\RunLogs' -Label 'desktop run logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'DesktopApp\*.log' -Label 'desktop runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'DesktopApp\*.state.json' -Label 'desktop local state files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DesktopApp\encode_speed_history.json' -Label 'desktop local telemetry'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'node_modules' -Label 'root Node.js packages'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DesktopApp\tauri_shell\node_modules' -Label 'Tauri node modules'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DesktopApp\tauri_shell\src-tauri\gen' -Label 'Tauri generated schemas'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DesktopApp\tauri_shell\src-tauri\target' -Label 'Tauri Rust build output'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'Docs\PG3CleanMachineReports' -Label 'PG-3 clean-machine operator reports'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\MediaPipeline_config.backup_*.psd1' -Label 'generated config backups'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1' -Label 'generated config backups (legacy)'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\*.log' -Label 'pipeline runtime logs'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\*.tmp' -Label 'pipeline runtime temp files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\*.bak' -Label 'pipeline runtime backup files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern 'Pipeline\*_progress.json' -Label 'pipeline runtime progress files'),
        (New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern '~$*' -Label 'Office lock/temp files')
    )) {
        [void]$rules.Add($rule)
    }

    foreach ($pattern in @('*.doc', '*.docx', '*.docm', '*.dotx', '*.xlsx', '*.xlsm', '*.pptx', '*.pptm')) {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'pattern_absent' -RelativePattern $pattern -Label 'local Office working documents'))
    }

    if (-not $DevDocsIncluded) {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'Docs\archive\docs-housekeeping' -Label 'docs housekeeping quarantine'))
    }

    if ($TauriPreviewBinaryIncluded) {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_present' -RelativePath 'DesktopApp\tauri_shell\mediapipeline-tauri-shell.exe' -Label 'Tauri preview packaged executable'))
    } else {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'DesktopApp\tauri_shell\mediapipeline-tauri-shell.exe' -Label 'Tauri preview packaged executable'))
    }

    if (-not $PersonalConfigIncluded) {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'Pipeline\MediaPipeline_config.psd1' -Label 'personal live config'))
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'Pipeline\MediaPipeline_config_chatgpt.psd1' -Label 'personal live config (legacy)'))
    }

    if (-not $OptionalToolsIncluded) {
        foreach ($relative in @(
            'Pipeline\Tools\ffmpeg\bin\ffplay.exe',
            'Pipeline\Tools\MKVToolNix\mkvtoolnix-gui.exe',
            'Pipeline\Tools\MKVToolNix\mkvextract.exe',
            'Pipeline\Tools\MKVToolNix\mkvinfo.exe',
            'Pipeline\Tools\MKVToolNix\mkvpropedit.exe',
            'Pipeline\Tools\MKVToolNix\uninst.exe',
            'Pipeline\Tools\MKVToolNix\MKVToolNix.url',
            'Pipeline\Tools\MKVToolNix\tools',
            'Pipeline\Tools\MKVToolNix\data',
            'Pipeline\Tools\MKVToolNix\locale\libqt'
        )) {
            [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath $relative -Label 'optional tool bulk'))
        }
    }

    if (-not $ToolDocsIncluded) {
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'Pipeline\Tools\MKVToolNix\doc' -Label 'bundled tool documentation'))
        [void]$rules.Add((New-MediaPipelineReleaseHygieneRule -Kind 'path_absent' -RelativePath 'Pipeline\Tools\MKVToolNix\examples' -Label 'bundled tool examples'))
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
        policy_module = 'scripts\release\release_policy.ps1'
        include_tests = [bool]$IncludeTests
        include_dev_docs = [bool]$IncludeDevDocs
        include_optional_tools = [bool]$IncludeOptionalTools
        include_tool_docs = [bool]$IncludeToolDocs
        include_tauri_preview_binary = [bool]$IncludeTauriPreviewBinary
        keep_personal_config = [bool]$KeepPersonalConfig
        hygiene_rule_count = $rules.Count
    }
}
