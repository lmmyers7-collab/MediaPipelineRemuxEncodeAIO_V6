function Get-AuditMediaFilesBounded {
    param(
        [Parameter(Mandatory)] [string] $RootPath,
        [int] $TimeoutSeconds = 1800
    )

    $job = Start-Job -ScriptBlock {
        param($root)
        Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction Stop |
            ForEach-Object { $_.FullName }
    } -ArgumentList $RootPath

    $startedAt = Get-Date
    try {
        while ($true) {
            $completed = Wait-Job $job -Timeout 1
            if ($completed) {
                $paths = @(Receive-Job $job -ErrorAction Stop)
                $files = foreach ($path in $paths) {
                    if ([string]::IsNullOrWhiteSpace([string]$path)) { continue }
                    $ext = [System.IO.Path]::GetExtension([string]$path).ToLowerInvariant()
                    if ($script:ValidExtensions -notcontains $ext) { continue }
                    try { Get-Item -LiteralPath ([string]$path) -ErrorAction Stop } catch { $null }
                }
                return @($files | Where-Object { $null -ne $_ } | Sort-Object FullName)
            }

            if ($TimeoutSeconds -gt 0 -and ((Get-Date) - $startedAt).TotalSeconds -ge $TimeoutSeconds) {
                Stop-Job $job -ErrorAction SilentlyContinue
                throw "Audit media enumeration timed out after ${TimeoutSeconds}s for $RootPath"
            }
        }
    } finally {
        Remove-Job $job -Force -ErrorAction SilentlyContinue
    }
}
