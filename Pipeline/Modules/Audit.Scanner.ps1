# Audit media-file scanning loop.

function Invoke-AuditFileScan {
    param(
        [array]$MediaFiles = @(),
        [Parameter(Mandatory)] [string]$LibraryRoot
    )

    $results = [System.Collections.Generic.List[object]]::new()
    $total = $MediaFiles.Count
    $index = 0
    $script:AuditProgressTotal = $total
    $script:AuditProgressProcessed = 0

    foreach ($file in $MediaFiles) {
        $index++
        Write-AuditScanProgress -Index $index -Total $total -FileInfo $file
        try {
            $results.Add((Get-AuditResultForFile -FileInfo $file)) | Out-Null
        } catch {
            $failedResult = New-AuditResult -FileInfo $file -RelativePath (Get-RelativePathSafe -RootPath $LibraryRoot -FullPath $file.FullName)
            $lineNumber = $null
            if ($_.InvocationInfo -and $_.InvocationInfo.ScriptLineNumber) {
                $lineNumber = $_.InvocationInfo.ScriptLineNumber
            }
            $detail = if ($lineNumber) {
                "Audit failed while processing '$($file.FullName)' at line ${lineNumber}: $($_.Exception.Message)"
            } else {
                "Audit failed while processing '$($file.FullName)': $($_.Exception.Message)"
            }
            Write-AuditLog $detail 'ERROR'
            Add-AuditIssue -Result $failedResult -Bucket 'REVIEW' -Code 'audit-internal-error' -Message $detail -SuggestedAction 'Keep the file for review and inspect the audit script or rerun against this file after the next patch.'
            $results.Add($failedResult) | Out-Null
        }
        $script:AuditProgressProcessed = $index
    }

    Complete-AuditConsoleProgress
    return @($results)
}
