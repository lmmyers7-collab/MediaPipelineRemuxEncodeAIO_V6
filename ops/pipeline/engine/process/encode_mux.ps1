# ==============================================================================
# ops\pipeline\engine\process\encode_mux.ps1
# ==============================================================================
# Attachment-safe MKV encode finalization helpers. FFmpeg encodes media streams;
# MKVToolNix restores Matroska attachments without treating fonts as packet
# streams.
# ==============================================================================

function Get-EncodeMuxObjectValue {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if ($null -eq $Object) { return $Default }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $Default
}

function Get-EncodeMkvAttachmentInventory {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [string] $Context = ''
    )

    $inventory = [ordered]@{
        ok               = $false
        file_path        = $FilePath
        attachment_count = 0
        attachments      = @()
        reason           = ''
        error_code       = ''
        error_text       = ''
    }

    if ([string]::IsNullOrWhiteSpace($FilePath) -or -not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        $inventory.reason = "MKV attachment inventory target is missing: $FilePath"
        $inventory.error_code = Get-EncodeAttachmentMuxFailureCode -Stage 'inventory'
        return [pscustomobject]$inventory
    }

    try {
        $probeTimeoutSeconds = if (Get-Command -Name Get-SubtitleOperationTimeoutSeconds -ErrorAction SilentlyContinue) {
            Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'SubtitleProbeTimeoutSeconds' -DefaultSeconds 30
        } else {
            30
        }
        $result = Invoke-MkvmergeCommand -ArgumentList @('-J', $FilePath) -TimeoutSeconds $probeTimeoutSeconds -Stage 'encode-attachment-identify'
        if ([int]$result.ExitCode -ne 0) {
            $inventory.reason = "${Context}mkvmerge -J failed while reading attachment inventory for $([System.IO.Path]::GetFileName($FilePath))"
            $inventory.error_code = Get-EncodeAttachmentMuxFailureCode -Stage 'inventory'
            $inventory.error_text = [string]$result.Error
            return [pscustomobject]$inventory
        }

        $json = $result.Output | ConvertFrom-Json
        $records = [System.Collections.Generic.List[object]]::new()
        foreach ($attachment in @($json.attachments | Where-Object { $null -ne $_ })) {
            $properties = Get-EncodeMuxObjectValue -Object $attachment -Name 'properties' -Default $null
            $fileName = [string](Get-EncodeMuxObjectValue -Object $attachment -Name 'file_name' -Default (Get-EncodeMuxObjectValue -Object $properties -Name 'file_name' -Default ''))
            $contentType = [string](Get-EncodeMuxObjectValue -Object $attachment -Name 'content_type' -Default (Get-EncodeMuxObjectValue -Object $properties -Name 'content_type' -Default ''))
            $sizeValue = Get-EncodeMuxObjectValue -Object $attachment -Name 'size' -Default (Get-EncodeMuxObjectValue -Object $properties -Name 'size' -Default 0)
            $records.Add([pscustomobject][ordered]@{
                id           = Get-EncodeMuxObjectValue -Object $attachment -Name 'id' -Default $null
                file_name    = $fileName
                content_type = $contentType
                size         = [long]$sizeValue
            }) | Out-Null
        }

        $inventory.ok = $true
        $inventory.attachments = @($records | Sort-Object file_name, content_type, size)
        $inventory.attachment_count = @($inventory.attachments).Count
        return [pscustomobject]$inventory
    } catch {
        $inventory.reason = "${Context}failed to read MKV attachment inventory: $($_.Exception.Message)"
        $inventory.error_code = Get-EncodeAttachmentMuxFailureCode -Stage 'inventory'
        $inventory.error_text = [string]$_.Exception.Message
        return [pscustomobject]$inventory
    }
}

function Get-EncodeMkvAttachmentInventoryKey {
    param($Attachment)

    $name = ([string](Get-EncodeMuxObjectValue -Object $Attachment -Name 'file_name' -Default '')).ToLowerInvariant()
    $contentType = ([string](Get-EncodeMuxObjectValue -Object $Attachment -Name 'content_type' -Default '')).ToLowerInvariant()
    $size = [long](Get-EncodeMuxObjectValue -Object $Attachment -Name 'size' -Default 0)
    return "$name|$contentType|$size"
}

function Compare-EncodeMkvAttachmentInventory {
    param(
        [Parameter(Mandatory)] $SourceInventory,
        [Parameter(Mandatory)] $OutputInventory
    )

    if (-not [bool]$SourceInventory.ok) {
        return [pscustomobject][ordered]@{ ok = $false; reason = [string]$SourceInventory.reason; error_code = [string]$SourceInventory.error_code }
    }
    if (-not [bool]$OutputInventory.ok) {
        return [pscustomobject][ordered]@{ ok = $false; reason = [string]$OutputInventory.reason; error_code = [string]$OutputInventory.error_code }
    }

    $sourceKeys = @($SourceInventory.attachments | ForEach-Object { Get-EncodeMkvAttachmentInventoryKey -Attachment $_ } | Sort-Object)
    $outputKeys = @($OutputInventory.attachments | ForEach-Object { Get-EncodeMkvAttachmentInventoryKey -Attachment $_ } | Sort-Object)
    if ($sourceKeys.Count -ne $outputKeys.Count) {
        return [pscustomobject][ordered]@{
            ok = $false
            reason = "encoded MKV attachment count mismatch: source=$($sourceKeys.Count), output=$($outputKeys.Count)"
            error_code = Get-EncodeAttachmentMuxFailureCode -Stage 'verify'
        }
    }
    for ($idx = 0; $idx -lt $sourceKeys.Count; $idx++) {
        if ([string]$sourceKeys[$idx] -ne [string]$outputKeys[$idx]) {
            return [pscustomobject][ordered]@{
                ok = $false
                reason = "encoded MKV attachment inventory mismatch at index $idx"
                error_code = Get-EncodeAttachmentMuxFailureCode -Stage 'verify'
            }
        }
    }
    return [pscustomobject][ordered]@{ ok = $true; reason = 'attachment inventory preserved'; error_code = '' }
}

function Test-EncodeMkvAttachmentMuxApplies {
    param(
        [Parameter(Mandatory)] [string] $SourcePath,
        [Parameter(Mandatory)] [string] $OutputPath
    )

    $muxerName = Get-MediaEncodeOutputMuxerName -OutputPath $OutputPath
    if ($muxerName -ne 'matroska') { return $false }
    $sourceExtension = [System.IO.Path]::GetExtension($SourcePath).TrimStart('.').ToLowerInvariant()
    return ($sourceExtension -in @('mkv','matroska'))
}

function New-EncodeMkvAttachmentMuxArgumentList {
    param(
        [Parameter(Mandatory)] [string] $EncodedInputPath,
        [Parameter(Mandatory)] [string] $SourcePath,
        [Parameter(Mandatory)] [string] $OutputPath,
        [string] $GlobalTitle = ''
    )

    $args = [System.Collections.Generic.List[string]]::new()
    $args.AddRange([string[]]@('--output', $OutputPath))
    if (-not [string]::IsNullOrWhiteSpace($GlobalTitle)) {
        $args.AddRange([string[]]@('--title', $GlobalTitle))
    }
    $args.Add($EncodedInputPath)
    $args.AddRange([string[]]@(
        '--no-video',
        '--no-audio',
        '--no-subtitles',
        '--no-buttons',
        '--no-chapters',
        '--no-track-tags',
        '--no-global-tags',
        $SourcePath
    ))
    return @($args.ToArray())
}

function Invoke-EncodeMkvAttachmentMuxIfNeeded {
    param(
        [Parameter(Mandatory)] [string] $SourcePath,
        [Parameter(Mandatory)] [string] $EncodedPath,
        [Parameter(Mandatory)] [string] $ProcessingDirectory,
        [string] $GlobalTitle = '',
        [string] $ProgressRoute = 'encode'
    )

    $result = [ordered]@{
        ok = $false
        muxed = $false
        output_path = $EncodedPath
        stage = 'encode-mkvmerge'
        reason = ''
        error_code = ''
        repro_path = ''
        source_attachment_inventory = $null
        output_attachment_inventory = $null
    }

    if (-not (Test-EncodeMkvAttachmentMuxApplies -SourcePath $SourcePath -OutputPath $EncodedPath)) {
        $result.ok = $true
        $result.reason = 'attachment mux not applicable for output container'
        return [pscustomobject]$result
    }

    $sourceInventory = Get-EncodeMkvAttachmentInventory -FilePath $SourcePath -Context 'ENCODE: '
    $result.source_attachment_inventory = $sourceInventory
    if (-not [bool]$sourceInventory.ok) {
        $result.reason = [string]$sourceInventory.reason
        $result.error_code = if ([string]::IsNullOrWhiteSpace([string]$sourceInventory.error_code)) { Get-EncodeAttachmentMuxFailureCode -Stage 'inventory' } else { [string]$sourceInventory.error_code }
        return [pscustomobject]$result
    }
    if ([int]$sourceInventory.attachment_count -le 0) {
        $result.ok = $true
        $result.reason = 'source has no MKV attachments to restore'
        return [pscustomobject]$result
    }

    if (-not (Test-EstimatedOutputSpace -SourcePath $SourcePath -Label 'ENCODE-MUX' -RemuxFinalStage)) {
        $result.reason = 'Insufficient scratch space for encode MKV attachment mux'
        $result.error_code = Get-EncodeAttachmentMuxFailureCode -Stage 'insufficient-space'
        return [pscustomobject]$result
    }

    $muxedPath = Join-Path $ProcessingDirectory "encode_mux_$([guid]::NewGuid().ToString('N')).mkv"
    $args = New-EncodeMkvAttachmentMuxArgumentList -EncodedInputPath $EncodedPath -SourcePath $SourcePath -OutputPath $muxedPath -GlobalTitle $GlobalTitle
    Set-ProgressStage -Stage 'encode_mux' -Status 'Muxing encoded MKV attachments' -Route $ProgressRoute -Percent 0 -SaveNow
    $mkv = Invoke-MkvmergeWithProgress -ArgumentList @($args) -Label 'ENCODE-MUX' -TimeoutSeconds $script:MkvmergeRemuxTimeoutSeconds -Stage 'encode-mkvmerge' -ProgressStage 'encode_mux' -ProgressRoute $ProgressRoute -SaveReproOnFailure
    $mkvExitCode = [int]$mkv.ExitCode
    $mkvFailed = ([bool]$mkv.TimedOut -or [bool]$mkv.Stopped -or $mkvExitCode -lt 0 -or $mkvExitCode -ge 2 -or [bool]$mkv.MkvmergeWarningBlocking)
    if ($mkvFailed) {
        if (Test-Path -LiteralPath $muxedPath -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $muxedPath -Force -ErrorAction SilentlyContinue
        }
        $summary = if ($mkv.Error) { Get-ErrorTextSummary -ErrorText $mkv.Error } else { '' }
        $result.reason = if ($summary) { "encode mkvmerge attachment mux failed with exit ${mkvExitCode}: $summary" } else { "encode mkvmerge attachment mux failed with exit ${mkvExitCode}" }
        $result.error_code = Get-EncodeMkvmergeFailureCode -ErrorText $mkv.Error -ExitCode $mkvExitCode -TimedOut:([bool]$mkv.TimedOut) -Stopped:([bool]$mkv.Stopped)
        $result.repro_path = [string]$mkv.ReproPath
        return [pscustomobject]$result
    }

    $outputInventory = Get-EncodeMkvAttachmentInventory -FilePath $muxedPath -Context 'ENCODE: '
    $result.output_attachment_inventory = $outputInventory
    $comparison = Compare-EncodeMkvAttachmentInventory -SourceInventory $sourceInventory -OutputInventory $outputInventory
    if (-not [bool]$comparison.ok) {
        if (Test-Path -LiteralPath $muxedPath -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $muxedPath -Force -ErrorAction SilentlyContinue
        }
        $result.reason = [string]$comparison.reason
        $result.error_code = if ([string]::IsNullOrWhiteSpace([string]$comparison.error_code)) { Get-EncodeAttachmentMuxFailureCode -Stage 'verify' } else { [string]$comparison.error_code }
        $result.stage = 'encode-attachment-verify'
        return [pscustomobject]$result
    }

    $result.ok = $true
    $result.muxed = $true
    $result.output_path = $muxedPath
    $result.reason = "restored $($sourceInventory.attachment_count) MKV attachment(s)"
    return [pscustomobject]$result
}
