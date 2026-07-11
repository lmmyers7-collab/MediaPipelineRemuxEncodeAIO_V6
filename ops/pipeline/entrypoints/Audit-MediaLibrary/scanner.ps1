function Get-AuditMediaFilesBounded {
    param(
        [Parameter(Mandatory)] [string] $RootPath,
        [int] $TimeoutSeconds = 1800
    )

    $job = Start-Job -ScriptBlock {
        param($root, $validExtensions)
        Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction Stop |
            Where-Object { $validExtensions -contains $_.Extension.ToLowerInvariant() } |
            Sort-Object FullName |
            Select-Object FullName, Name, DirectoryName, Extension, Length, LastWriteTimeUtc
    } -ArgumentList $RootPath, @($script:ValidExtensions)

    $startedAt = Get-Date
    try {
        while ($true) {
            $completed = Wait-Job $job -Timeout 1
            if ($completed) {
                return @(Receive-Job $job -ErrorAction Stop)
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
