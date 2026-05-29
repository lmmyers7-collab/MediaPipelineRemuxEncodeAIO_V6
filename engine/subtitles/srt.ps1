# ==============================================================================
# engine\subtitles\srt.ps1
# ==============================================================================
# SRT validation, atomic SRT writes, safe copies, and cue merging.
# Dot-sourced by engine\subtitles\subtitles.ps1; preserves script-scope configuration.
# ==============================================================================

function Test-SrtFileUsable {
    param([string]$Path)

    $result = [ordered]@{
        Ok            = $false
        CueCount      = 0
        TextLineCount = 0
        Reason        = ''
    }

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)) {
        $result.Reason = 'SRT file is missing'
        return [pscustomobject]$result
    }

    try {
        $item = Get-Item -LiteralPath $Path -ErrorAction Stop
        if ($item.Length -le 0) {
            $result.Reason = 'SRT file is empty'
            return [pscustomobject]$result
        }

        $raw = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
        if ([string]::IsNullOrWhiteSpace($raw)) {
            $result.Reason = 'SRT text is blank'
            return [pscustomobject]$result
        }

        $timePattern = '(?m)^\s*\d{1,2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{1,2}:\d{2}:\d{2},\d{3}'
        $cueCount = [regex]::Matches($raw, $timePattern).Count
        $textLineCount = @(
            $raw -split '\r?\n' |
                ForEach-Object { ([string]$_).Trim() } |
                Where-Object {
                    $_ -match '\S' -and
                    $_ -notmatch '^\d+$' -and
                    $_ -notmatch '^\d{1,2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{1,2}:\d{2}:\d{2},\d{3}'
                }
        ).Count

        $result.CueCount = $cueCount
        $result.TextLineCount = $textLineCount

        if ($cueCount -le 0) {
            $result.Reason = 'SRT has no cue timing lines'
            return [pscustomobject]$result
        }
        if ($textLineCount -le 0) {
            $result.Reason = 'SRT has no cue text'
            return [pscustomobject]$result
        }

        $result.Ok = $true
        $result.Reason = 'ok'
        return [pscustomobject]$result
    } catch {
        $result.Reason = "SRT validation failed: $($_.Exception.Message)"
        return [pscustomobject]$result
    }
}

function New-SrtAtomicTempPath {
    param([string]$DestinationPath)

    $dir = Split-Path -Parent $DestinationPath
    if ([string]::IsNullOrWhiteSpace($dir)) {
        $dir = (Get-Location).Path
    }
    if (-not (Test-Path -LiteralPath $dir -ErrorAction SilentlyContinue)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
    }
    $leaf = Split-Path -Leaf $DestinationPath
    return (Join-Path $dir (".{0}.{1}.tmp.srt" -f $leaf, [guid]::NewGuid().ToString("N")))
}

function Complete-AtomicSrtWrite {
    param(
        [Parameter(Mandatory)] [string]$TempPath,
        [Parameter(Mandatory)] [string]$DestinationPath
    )

    $validation = Test-SrtFileUsable -Path $TempPath
    if (-not $validation.Ok) {
        throw $validation.Reason
    }

    $destDir = Split-Path -Parent $DestinationPath
    if ($destDir -and -not (Test-Path -LiteralPath $destDir -ErrorAction SilentlyContinue)) {
        [System.IO.Directory]::CreateDirectory($destDir) | Out-Null
    }

    if (Test-Path -LiteralPath $DestinationPath -ErrorAction SilentlyContinue) {
        $backup = Join-Path $destDir (".{0}.{1}.bak" -f (Split-Path -Leaf $DestinationPath), [guid]::NewGuid().ToString("N"))
        [System.IO.File]::Replace($TempPath, $DestinationPath, $backup, $true)
        Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
    } else {
        [System.IO.File]::Move($TempPath, $DestinationPath)
    }

    $finalValidation = Test-SrtFileUsable -Path $DestinationPath
    if (-not $finalValidation.Ok) {
        throw "SRT failed validation after atomic move: $($finalValidation.Reason)"
    }
    return $finalValidation
}

function Copy-SrtAtomic {
    param(
        [Parameter(Mandatory)] [string]$SourcePath,
        [Parameter(Mandatory)] [string]$DestinationPath
    )

    $tempSrt = New-SrtAtomicTempPath -DestinationPath $DestinationPath
    try {
        $sourceValidation = Test-SrtFileUsable -Path $SourcePath
        if (-not $sourceValidation.Ok) {
            throw "source SRT is not usable: $($sourceValidation.Reason)"
        }
        [System.IO.File]::Copy($SourcePath, $tempSrt, $true)
        $validation = Complete-AtomicSrtWrite -TempPath $tempSrt -DestinationPath $DestinationPath
        return [pscustomobject]@{
            Ok        = $true
            Path      = $DestinationPath
            CueCount  = $validation.CueCount
            Reason    = 'ok'
            ErrorCode = 'OK'
        }
    } catch {
        return [pscustomobject]@{
            Ok        = $false
            Path      = $null
            CueCount  = 0
            Reason    = $_.Exception.Message
            ErrorCode = 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED'
        }
    } finally {
        if ($tempSrt -and (Test-Path -LiteralPath $tempSrt -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tempSrt -Force -ErrorAction SilentlyContinue
        }
    }
}

function Merge-AdjacentIdenticalCues {
    param([string]$SrtPath, [double]$ThresholdMs = 150)

    if (-not (Test-Path -LiteralPath $SrtPath)) { return }
    $raw = [System.IO.File]::ReadAllText($SrtPath, [System.Text.Encoding]::UTF8)
    if ([string]::IsNullOrWhiteSpace($raw)) { return }

    $cues         = [System.Collections.Generic.List[PSCustomObject]]::new()
    $currentStart = $null
    $currentEnd   = $null
    $currentText  = [System.Collections.Generic.List[string]]::new()
    $cueCounter   = 1

    foreach ($line in ($raw -split '\r?\n')) {
        $t = $line.Trim()
        if ($t -match '^\d+$') {
            if ($null -ne $currentStart -and $currentText.Count -gt 0) {
                $ft = ($currentText -join "`n").Trim()
                if ($ft.Length -gt 0) {
                    $cues.Add([PSCustomObject]@{
                        Index=$cueCounter++; Start=$currentStart; End=$currentEnd; Text=$ft })
                }
            }
            $currentStart=$null; $currentEnd=$null; $currentText.Clear(); continue
        }
        if ($t -match '^(\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3})') {
            if ($null -ne $currentStart -and $currentText.Count -gt 0) {
                $ft = ($currentText -join "`n").Trim()
                if ($ft.Length -gt 0) {
                    $cues.Add([PSCustomObject]@{
                        Index=$cueCounter++; Start=$currentStart; End=$currentEnd; Text=$ft })
                }
            }
            $currentText.Clear()
            $currentStart = $Matches[1] -replace '\.', ','
            $currentEnd   = $Matches[2] -replace '\.', ','
            continue
        }
        if ($t -ne '' -and $null -ne $currentStart) { $currentText.Add($line) }
    }
    if ($null -ne $currentStart -and $currentText.Count -gt 0) {
        $ft = ($currentText -join "`n").Trim()
        if ($ft.Length -gt 0) {
            $cues.Add([PSCustomObject]@{
                Index=$cueCounter++; Start=$currentStart; End=$currentEnd; Text=$ft })
        }
    }

    if ($cues.Count -le 1) { return }

    $merged = [System.Collections.Generic.List[PSCustomObject]]::new()
    $prev   = $cues[0]
    for ($i = 1; $i -lt $cues.Count; $i++) {
        $curr     = $cues[$i]
        $gap      = (ConvertTo-Milliseconds $curr.Start) - (ConvertTo-Milliseconds $prev.End)
        $sameText = ($prev.Text.Trim() -eq $curr.Text.Trim())
        if ($gap -ge 0 -and $gap -le $ThresholdMs -and $sameText) {
            $prev.End = $curr.End
        } else {
            $merged.Add($prev); $prev = $curr
        }
    }
    $merged.Add($prev)

    if ($merged.Count -eq $cues.Count) { return }

    Write-Log "MERGE: $($cues.Count) -> $($merged.Count) cues (collapsed $($cues.Count - $merged.Count) identical adjacent)" "DEBUG"

    $sb = [System.Text.StringBuilder]::new()
    for ($i = 0; $i -lt $merged.Count; $i++) {
        $c = $merged[$i]
        [void]$sb.AppendLine(($i+1).ToString())
        [void]$sb.AppendLine("$($c.Start) --> $($c.End)")
        [void]$sb.AppendLine($c.Text.Trim())
        [void]$sb.AppendLine("")
    }
    $tempSrt = New-SrtAtomicTempPath -DestinationPath $SrtPath
    try {
        [System.IO.File]::WriteAllText($tempSrt, $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
        [void](Complete-AtomicSrtWrite -TempPath $tempSrt -DestinationPath $SrtPath)
    } finally {
        if ($tempSrt -and (Test-Path -LiteralPath $tempSrt -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tempSrt -Force -ErrorAction SilentlyContinue
        }
    }
}
