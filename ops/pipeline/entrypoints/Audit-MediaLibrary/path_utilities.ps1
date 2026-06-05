function Resolve-ExistingPath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    if (Test-IsUncPath $Path) { return $Path }
    try {
        if (Test-Path -LiteralPath $Path) {
            $resolved = Resolve-Path -LiteralPath $Path | Select-Object -First 1
            if ($resolved -and $resolved.ProviderPath) {
                return $resolved.ProviderPath
            }
            if ($resolved) {
                return $resolved.Path
            }
        }
    } catch {}
    return $Path
}

function Test-IsUncPath {
    param([string]$Path)
    return (-not [string]::IsNullOrWhiteSpace($Path) -and ($Path.StartsWith('\\') -or $Path.StartsWith('//')))
}

function Get-AuditConfigString {
    param(
        [object]$Config,
        [string]$Name
    )

    if ($null -eq $Config -or [string]::IsNullOrWhiteSpace($Name)) { return $null }
    try {
        if ($Config.ContainsKey($Name) -and $Config[$Name]) { return [string]$Config[$Name] }
    } catch {}
    try {
        if ($Config.Contains($Name) -and $Config[$Name]) { return [string]$Config[$Name] }
    } catch {}
    try {
        $property = $Config.PSObject.Properties[$Name]
        if ($property -and $property.Value) { return [string]$property.Value }
    } catch {}
    return $null
}

function Get-AuditDefaultLibraryRootFromConfig {
    param([object]$Config)

    $sourcePaths = @(@('SourceMovies', 'SourceTV') |
        ForEach-Object { Get-AuditConfigString -Config $Config -Name $_ } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

    if ($sourcePaths.Count -eq 0) { return $null }
    if ($sourcePaths.Count -eq 1) { return $sourcePaths[0] }

    $parents = @($sourcePaths | ForEach-Object {
        try { Split-Path -Parent $_ } catch { $null }
    } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

    if ($parents.Count -eq 0) { return $sourcePaths[0] }
    $firstParent = $parents[0]
    foreach ($parent in $parents) {
        if (-not [string]::Equals($parent, $firstParent, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $null
        }
    }
    return $firstParent
}

function New-AtomicTempPath {
    param([string]$Path)

    $dir = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($dir) -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $leaf = Split-Path -Leaf $Path
    return (Join-Path $dir ('.' + $leaf + '.' + [System.IO.Path]::GetRandomFileName() + '.tmp'))
}

function Write-Utf8NoBomFile {
    param(
        [string]$Path,
        [string]$Content
    )

    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function Write-AtomicTextFile {
    param(
        [string]$Path,
        [object[]]$Lines
    )

    $tempPath = New-AtomicTempPath -Path $Path
    try {
        $content = [string]::Join([Environment]::NewLine, @($Lines))
        if ($content.Length -gt 0) {
            $content += [Environment]::NewLine
        }
        Write-Utf8NoBomFile -Path $tempPath -Content $content
        Move-Item -LiteralPath $tempPath -Destination $Path -Force
    } catch {
        try {
            if (Test-Path -LiteralPath $tempPath) {
                Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
            }
        } catch {}
        throw
    }
}

function Write-AtomicJsonFile {
    param(
        [string]$Path,
        $InputObject,
        [int]$Depth = 8
    )

    $tempPath = New-AtomicTempPath -Path $Path
    try {
        $json = $InputObject | ConvertTo-Json -Depth $Depth
        Write-Utf8NoBomFile -Path $tempPath -Content $json
        Move-Item -LiteralPath $tempPath -Destination $Path -Force
    } catch {
        try {
            if (Test-Path -LiteralPath $tempPath) {
                Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
            }
        } catch {}
        throw
    }
}

function Compare-PipelineVersion {
    param([string]$A, [string]$B)

    $pa = ($A -split '\.') + @('0','0','0') | Select-Object -First 3 | ForEach-Object { [int]$_ }
    $pb = ($B -split '\.') + @('0','0','0') | Select-Object -First 3 | ForEach-Object { [int]$_ }
    for ($i = 0; $i -lt 3; $i++) {
        if ($pa[$i] -lt $pb[$i]) { return $true }
        if ($pa[$i] -gt $pb[$i]) { return $false }
    }
    return $false
}

function Test-PipelineVersionString {
    param([string]$Value)

    return ($Value -match '^\d+(\.\d+){0,2}$')
}

function Try-ParseDoubleInvariant {
    param([object]$Value)

    $parsed = 0.0
    if ([double]::TryParse([string]$Value, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsed)) {
        return $parsed
    }
    return 0.0
}

function Get-SidecarPath {
    param([string]$OutputPath)

    $dir  = Split-Path $OutputPath -Parent
    $base = [System.IO.Path]::GetFileNameWithoutExtension($OutputPath)
    return (Join-Path $dir ($base + '.pipeline.json'))
}

function Get-RelativePathSafe {
    param(
        [string]$RootPath,
        [string]$FullPath
    )

    if ([string]::IsNullOrWhiteSpace($RootPath) -or [string]::IsNullOrWhiteSpace($FullPath)) {
        return $FullPath
    }

    $rootTrimmed = $RootPath.TrimEnd('\')
    if ($FullPath.StartsWith($rootTrimmed, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $FullPath.Substring($rootTrimmed.Length).TrimStart('\')
        if ($relative) { return $relative }
    }
    return $FullPath
}
