# Dot-sourced helper slice for Setup-MediaPipeline.ps1. Keep CLI orchestration in the parent script.

function Test-IsRealPython {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $false }
    if ($Path -match '\\WindowsApps\\') { return $false }
    try {
        $out = & $Path -c "import sys; print(sys.version_info[0])" 2>&1
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -match '^\d+$')
    } catch {
        return $false
    }
}

function Get-BundleSearchRoots {
    $roots = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
            $script:ScriptDir,
            $PSScriptRoot
        )) {
        if (-not $candidate) { continue }
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
        if (-not $roots.Contains($resolved)) {
            [void]$roots.Add($resolved)
        }
    }
    return @($roots)
}

function Resolve-BundledPath {
    param([string[]]$RelativeCandidates)
    foreach ($root in Get-BundleSearchRoots) {
        foreach ($relative in $RelativeCandidates) {
            $candidate = Join-Path $root $relative
            if (Test-Path -LiteralPath $candidate) {
                return (Resolve-Path -LiteralPath $candidate).Path
            }
        }
    }
    return $null
}

function Resolve-ToolPath {
    param(
        [Parameter(Mandatory = $true)][string]$ToolName,
        [string[]]$RelativeCandidates = @()
    )

    $bundled = Resolve-BundledPath -RelativeCandidates $RelativeCandidates
    if ($bundled) { return $bundled }

    $cmd = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }

    return $null
}

function Resolve-PythonPath {
    $bundledCandidates = @(
        'Runtime\Python\python.exe',
        'Tools\Python\python.exe',
        '..\DesktopApp\Runtime\Python\python.exe'
    )
    foreach ($candidate in $bundledCandidates) {
        $resolved = Resolve-BundledPath -RelativeCandidates @($candidate)
        if ($resolved -and (Test-IsRealPython $resolved)) {
            return $resolved
        }
    }
    foreach ($candidate in @('python3','python')) {
        foreach ($cmd in @(Get-Command $candidate -All -ErrorAction SilentlyContinue)) {
            if ($cmd -and (Test-IsRealPython $cmd.Source)) {
                return $cmd.Source
            }
        }
    }
    return $null
}

function Test-Pysubs2Import {
    param([string]$PythonPath)
    if (-not $PythonPath) { return $false }
    try {
        $null = & $PythonPath -c "import pysubs2" 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-PwshPath {
    if ($PSVersionTable.PSVersion.Major -ge 7) {
        return (Get-Process -Id $PID).Path
    }

    $candidates = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
            (Join-Path $script:ScriptDir 'pwsh.exe'),
            (Join-Path $script:ScriptDir 'PowerShell-7.6.0-win-x64\pwsh.exe')
        )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            [void]$candidates.Add($candidate)
        }
    }

    Get-ChildItem -LiteralPath $script:ScriptDir -Directory -Filter 'PowerShell-*' -ErrorAction SilentlyContinue |
        ForEach-Object {
            $candidate = Join-Path $_.FullName 'pwsh.exe'
            if (Test-Path -LiteralPath $candidate) {
                [void]$candidates.Add($candidate)
            }
        }

    $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        [void]$candidates.Add($cmd.Source)
    }

    return ($candidates | Select-Object -Unique | Select-Object -First 1)
}

function Resolve-CurrentPowerShellPath {
    try {
        $currentProcess = Get-Process -Id $PID -ErrorAction Stop
        if ($currentProcess.Path) { return $currentProcess.Path }
    } catch { }

    $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    return $null
}

function Get-DependencyStatus {
    $statuses = [System.Collections.Generic.List[pscustomobject]]::new()

    $pwshPath = Resolve-PwshPath
    $statuses.Add([pscustomobject]@{
        Name    = 'PowerShell 7'
        Ok      = [bool]$pwshPath
        Details = if ($pwshPath) { $pwshPath } else { 'Not found next to the bundle or on PATH.' }
        Suggest = 'Bundle PowerShell 7 or install it so pwsh is available.'
    })

    $toolCandidates = @{
        ffmpeg   = @('Tools\ffmpeg\bin\ffmpeg.exe')
        ffprobe  = @('Tools\ffmpeg\bin\ffprobe.exe')
        mkvmerge = @('Tools\MKVToolNix\mkvmerge.exe')
    }
    foreach ($toolName in @('ffmpeg','ffprobe','mkvmerge')) {
        $toolPath = Resolve-ToolPath -ToolName $toolName -RelativeCandidates $toolCandidates[$toolName]
        $statuses.Add([pscustomobject]@{
            Name    = $toolName
            Ok      = [bool]$toolPath
            Details = if ($toolPath) { $toolPath } else { 'Not found in bundle drop-in folders or on PATH.' }
            Suggest = switch ($toolName) {
                'mkvmerge' { 'Install MKVToolNix or place mkvmerge.exe under Tools\MKVToolNix.' }
                default    { 'Install ffmpeg or place ffmpeg.exe and ffprobe.exe under Tools\ffmpeg\bin.' }
            }
        })
    }

    $pythonPath = Resolve-PythonPath
    $statuses.Add([pscustomobject]@{
        Name    = 'Python'
        Ok      = [bool]$pythonPath
        Details = if ($pythonPath) { $pythonPath } else { 'A real Python interpreter was not found.' }
        Suggest = 'Install Python 3 or place python.exe under Runtime\Python or DesktopApp\Runtime\Python.'
    })
    $statuses.Add([pscustomobject]@{
        Name    = 'pysubs2'
        Ok      = [bool]($pythonPath -and (Test-Pysubs2Import $pythonPath))
        Details = if ($pythonPath) {
            if (Test-Pysubs2Import $pythonPath) { 'Import succeeded.' } else { 'Python found, but pysubs2 is missing.' }
        } else {
            'Python is missing, so pysubs2 could not be checked.'
        }
        Suggest = 'Run: python -m pip install pysubs2'
    })
    $statuses.Add([pscustomobject]@{
        Name    = 'Pipeline script'
        Ok      = (Test-Path -LiteralPath $script:PipelinePath)
        Details = $script:PipelinePath
        Suggest = 'Keep MediaPipeline.ps1 in the same deployment folder.'
    })
    $statuses.Add([pscustomobject]@{
        Name    = 'Subtitle converter'
        Ok      = (Test-Path -LiteralPath $script:SubtitlePath)
        Details = $script:SubtitlePath
        Suggest = 'Keep ass_to_srt.py in the same deployment folder.'
    })

    return @($statuses)
}

function Get-DetectedGpu {
    $result = @{ Vendor = 'None'; Name = 'Unknown' }

    $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($nvidiaSmi) {
        try {
            $out = & $nvidiaSmi.Source --query-gpu=name --format=csv,noheader 2>&1 | Select-Object -First 1
            if ($LASTEXITCODE -eq 0 -and $out) {
                return @{ Vendor = 'NVIDIA'; Name = "$out".Trim() }
            }
        } catch { }
    }

    try {
        $gpus = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue)
        foreach ($gpu in $gpus) {
            if (-not $gpu.Name) { continue }
            if ($gpu.Name -match 'NVIDIA|GeForce|\bRTX\b|\bGTX\b|Quadro') {
                return @{ Vendor = 'NVIDIA'; Name = $gpu.Name }
            }
            if ($gpu.Name -match 'AMD|Radeon|\bRX\s*\d') {
                return @{ Vendor = 'AMD'; Name = $gpu.Name }
            }
            if ($gpu.Name -match 'Intel|\bArc\b|Iris|\bUHD\b|\bHD Graphics\b') {
                return @{ Vendor = 'Intel'; Name = $gpu.Name }
            }
        }
        if ($gpus.Count -gt 0 -and $gpus[0].Name) {
            $result.Name = $gpus[0].Name
        }
    } catch { }

    return $result
}

function Get-ExtraVideoFlagsForCodec {
    param([string]$Codec)
    Get-MediaPipelineConfigExtraVideoFlagsDefault -Codec $Codec
}

function Test-VideoPresetCompatibility {
    param([hashtable]$Config)

    if (-not $Config.ContainsKey('VideoCodec') -or -not $Config.ContainsKey('VideoPreset')) {
        return $true
    }

    $codec = [string]$Config['VideoCodec']
    $preset = [string]$Config['VideoPreset']
    $allowed = if ($codec -eq 'libx265') {
        @('ultrafast','superfast','veryfast','faster','fast','medium','slow','slower','veryslow','placebo')
    } else {
        @('p1','p2','p3','p4','p5','p6','p7')
    }

    return ($allowed -contains $preset)
}
