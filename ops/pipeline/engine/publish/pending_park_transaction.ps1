# ==============================================================================
# ops\pipeline\engine\publish\pending_park_transaction.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\publish\pending_transactions.ps1. Keep function names
# stable; pending_transactions.ps1 dot-sources this file as the public surface.
# ==============================================================================

function New-PendingParkSidecarEntries {
    param(
        [array] $SidecarFiles = @(),
        [Parameter(Mandatory)] [string] $LocalPendingPushPath,
        [Parameter(Mandatory)] [string] $Timestamp,
        [Parameter(Mandatory)] [string] $TransactionFileId
    )

    $entries = [System.Collections.Generic.List[object]]::new()
    $sidecarOrdinal = 0
    foreach ($sidecar in @($SidecarFiles)) {
        $sidecarLocal = [string](Get-PendingObjectProperty -Object $sidecar -Name 'LocalPath')
        $sidecarServer = [string](Get-PendingObjectProperty -Object $sidecar -Name 'DestinationPath')
        if ([string]::IsNullOrWhiteSpace($sidecarServer)) {
            $sidecarServer = [string](Get-PendingObjectProperty -Object $sidecar -Name 'ServerOut')
        }
        if ([string]::IsNullOrWhiteSpace($sidecarLocal) -or [string]::IsNullOrWhiteSpace($sidecarServer)) {
            continue
        }
        if (-not (Test-Path -LiteralPath $sidecarLocal -ErrorAction SilentlyContinue)) {
            throw "pending sidecar source is missing: $sidecarLocal"
        }
        $sidecarLeaf = Split-Path $sidecarServer -Leaf
        if ([string]::IsNullOrWhiteSpace($sidecarLeaf)) { $sidecarLeaf = "sidecar$sidecarOrdinal.srt" }
        $sidecarParked = Join-Path $LocalPendingPushPath "${Timestamp}__${TransactionFileId}__sidecar${sidecarOrdinal}__${sidecarLeaf}"
        $entries.Add([ordered]@{
            kind                = if (Get-PendingObjectProperty -Object $sidecar -Name 'Kind') { [string](Get-PendingObjectProperty -Object $sidecar -Name 'Kind') } else { 'sidecar' }
            local_file          = $sidecarParked
            original_local_file = $sidecarLocal
            parked_file         = $sidecarParked
            server_out          = $sidecarServer
            output_size         = Get-FileLengthOrNull $sidecarLocal
            preserve_existing   = [bool](Get-PendingObjectProperty -Object $sidecar -Name 'PreserveExisting')
            tx3g_record         = Get-PendingObjectProperty -Object $sidecar -Name 'Record'
        })
        $sidecarOrdinal++
    }
    return $entries
}

function New-PendingParkManifest {
    param(
        [Parameter(Mandatory)] [string] $LocalOut,
        [Parameter(Mandatory)] [string] $ParkedPath,
        [Parameter(Mandatory)] [string] $ServerOut,
        [Parameter(Mandatory)] [string] $Route,
        [string] $RouteReasonCode = '',
        [string] $RouteReason = '',
        [string] $SourceIdentity,
        [string] $SourceIdentityV2,
        [string] $SourcePath,
        [object] $SourceSize,
        [string] $SourceMTimeUtc,
        [Parameter(Mandatory)] [string] $PublishTransactionId,
        [string] $PublishMode = 'retry',
        [array] $SidecarManifestEntries = @(),
        [array] $Tx3gSrtTracks = @(),
        [array] $Tx3gSrtFailures = @(),
        [array] $BdpgsSrtFailures = @(),
        [array] $VobSubSrtFailures = @(),
        [array] $Tx3gEmbeddedSrtTracks = @(),
        [array] $BdpgsEmbeddedSrtTracks = @(),
        [array] $VobSubEmbeddedSrtTracks = @(),
        [bool] $Tx3gSrtConversionEnabled = $false,
        [bool] $Tx3gExternalSrtSidecarsEnabled = $false,
        [bool] $DropTx3gAfterConversion = $false,
        [bool] $BdpgsSrtConversionEnabled = $false,
        [bool] $DropBdpgsAfterConversion = $false,
        [bool] $VobSubSrtConversionEnabled = $false,
        [bool] $DropVobSubAfterConversion = $false,
        [object] $FolderPolicyMetadata = $null,
        [object] $RoutePlanMetadata = $null,
        # S9 — carry MediaType through park so the deferred-publish
        # sidecar can stamp the same media_type field that immediate
        # publish does.  Without this, movies parked-and-drained come
        # back blank in the Completed tab on the desktop UI.  Lower-cased
        # 'movie' / 'tv' to match Complete-PipelineOutputPublish.
        [string] $MediaType = ''
    )

    $manifest = [ordered]@{
        schema_version         = 'pending_push_manifest.v1'
        parked_at              = (Get-Date -Format 'o')
        product_version         = if ($script:ProductVersion) { [string]$script:ProductVersion } else { '' }
        pipeline_version       = $script:PipelineVersion
        publish_transaction_id = $PublishTransactionId
        manifest_state         = 'pending_move'
        local_file             = $ParkedPath
        original_local_file    = $LocalOut
        parked_file            = $ParkedPath
        server_out             = $ServerOut
        route                  = $Route
        route_reason_code      = $RouteReasonCode
        route_reason           = $RouteReason
        media_type             = if ([string]::IsNullOrWhiteSpace($MediaType)) { '' } else { $MediaType.Trim().ToLowerInvariant() }
        source_identity        = $SourceIdentity
        source_identity_v2     = $SourceIdentityV2
        source_identity_v2_algorithm = $script:SourceIdentityV2Algorithm
        source_path            = $SourcePath
        source_size            = $SourceSize
        source_mtime_utc       = $SourceMTimeUtc
        output_size            = Get-FileLengthOrNull $LocalOut
        publish_mode           = $PublishMode
        sidecar_files          = @($SidecarManifestEntries)
        tx3g_srt_tracks        = @($Tx3gSrtTracks)
        tx3g_srt_failures      = @($Tx3gSrtFailures)
        bdpgs_srt_failures     = @($BdpgsSrtFailures)
        vobsub_srt_failures    = @($VobSubSrtFailures)
        tx3g_embedded_srt_tracks = @($Tx3gEmbeddedSrtTracks)
        bdpgs_embedded_srt_tracks = @($BdpgsEmbeddedSrtTracks)
        vobsub_embedded_srt_tracks = @($VobSubEmbeddedSrtTracks)
        tx3g_srt_conversion_enabled = [bool]$Tx3gSrtConversionEnabled
        tx3g_external_srt_sidecars_enabled = [bool]$Tx3gExternalSrtSidecarsEnabled
        drop_tx3g_after_conversion = [bool]$DropTx3gAfterConversion
        bdpgs_srt_conversion_enabled = [bool]$BdpgsSrtConversionEnabled
        drop_bdpgs_after_conversion = [bool]$DropBdpgsAfterConversion
        vobsub_srt_conversion_enabled = [bool]$VobSubSrtConversionEnabled
        drop_vobsub_after_conversion = [bool]$DropVobSubAfterConversion
    }
    if ($FolderPolicyMetadata) {
        $manifest['folder_policy'] = $FolderPolicyMetadata
    }
    if ($RoutePlanMetadata) {
        $manifest['route_plan'] = $RoutePlanMetadata
    }
    return $manifest
}

function Invoke-PendingParkTransaction {
    param(
        [Parameter(Mandatory)] [string] $LocalOut,
        [Parameter(Mandatory)] [string] $ServerOut,
        [Parameter(Mandatory)] [string] $Route,
        [string] $RouteReasonCode = '',
        [string] $RouteReason = '',
        [string] $SourceIdentity,
        [string] $SourceIdentityV2,
        [string] $SourcePath,
        [object] $SourceSize,
        [string] $SourceMTimeUtc,
        [string] $PublishTransactionId,
        [string] $PublishMode = 'retry',
        [array] $SidecarFiles = @(),
        [array] $Tx3gSrtTracks = @(),
        [array] $Tx3gSrtFailures = @(),
        [array] $BdpgsSrtFailures = @(),
        [array] $VobSubSrtFailures = @(),
        [array] $Tx3gEmbeddedSrtTracks = @(),
        [array] $BdpgsEmbeddedSrtTracks = @(),
        [array] $VobSubEmbeddedSrtTracks = @(),
        [bool] $Tx3gSrtConversionEnabled = $false,
        [bool] $Tx3gExternalSrtSidecarsEnabled = $false,
        [bool] $DropTx3gAfterConversion = $false,
        [bool] $BdpgsSrtConversionEnabled = $false,
        [bool] $DropBdpgsAfterConversion = $false,
        [bool] $VobSubSrtConversionEnabled = $false,
        [bool] $DropVobSubAfterConversion = $false,
        [object] $FolderPolicyMetadata = $null,
        [object] $RoutePlanMetadata = $null,
        [string] $MediaType = ''
    )

    $parked = ''
    $manifestPath = ''
    $sidecarManifestEntries = @()
    $leaf = Split-Path $LocalOut -Leaf
    try {
        if (-not (Test-Path -LiteralPath $LocalOut)) {
            return [pscustomobject]@{
                Ok = $false; Error = "local output vanished at $LocalOut"; LocalFile = ''; OriginalLocalFile = $LocalOut
                ServerOut = $ServerOut; ManifestPath = ''; PublishTransactionId = $PublishTransactionId; SidecarEntries = @()
                OutputSize = $null; Leaf = $leaf; MediaMoved = $false
            }
        }
        if (-not (Test-Path -LiteralPath $LocalPendingPush)) {
            [System.IO.Directory]::CreateDirectory($LocalPendingPush) | Out-Null
        }
        $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
        $id = [guid]::NewGuid().ToString("N")
        $parked = Join-Path $LocalPendingPush "${ts}__${id}__${leaf}"
        if ([string]::IsNullOrWhiteSpace($PublishTransactionId)) { $PublishTransactionId = New-PublishTransactionId }
        $sidecarManifestEntries = @(New-PendingParkSidecarEntries -SidecarFiles $SidecarFiles -LocalPendingPushPath $LocalPendingPush -Timestamp $ts -TransactionFileId $id)

        foreach ($sidecar in @($sidecarManifestEntries)) {
            $sidecarOriginal = [string]$sidecar.original_local_file
            $sidecarParked = [string]$sidecar.local_file
            $sidecarDir = Split-Path $sidecarParked -Parent
            if ($sidecarDir -and -not (Test-Path -LiteralPath $sidecarDir)) {
                [System.IO.Directory]::CreateDirectory($sidecarDir) | Out-Null
            }
            $sidecarCopy = Copy-SrtAtomic -SourcePath $sidecarOriginal -DestinationPath $sidecarParked
            if (-not $sidecarCopy.Ok) {
                throw "pending sidecar park failed for $sidecarOriginal : $($sidecarCopy.Reason)"
            }
        }

        $manifest = New-PendingParkManifest `
            -LocalOut $LocalOut `
            -ParkedPath $parked `
            -ServerOut $ServerOut `
            -Route $Route `
            -RouteReasonCode $RouteReasonCode `
            -RouteReason $RouteReason `
            -SourceIdentity $SourceIdentity `
            -SourceIdentityV2 $SourceIdentityV2 `
            -SourcePath $SourcePath `
            -SourceSize $SourceSize `
            -SourceMTimeUtc $SourceMTimeUtc `
            -PublishTransactionId $PublishTransactionId `
            -PublishMode $PublishMode `
            -SidecarManifestEntries @($sidecarManifestEntries) `
            -Tx3gSrtTracks @($Tx3gSrtTracks) `
            -Tx3gSrtFailures @($Tx3gSrtFailures) `
            -BdpgsSrtFailures @($BdpgsSrtFailures) `
            -VobSubSrtFailures @($VobSubSrtFailures) `
            -Tx3gEmbeddedSrtTracks @($Tx3gEmbeddedSrtTracks) `
            -BdpgsEmbeddedSrtTracks @($BdpgsEmbeddedSrtTracks) `
            -VobSubEmbeddedSrtTracks @($VobSubEmbeddedSrtTracks) `
            -Tx3gSrtConversionEnabled:$Tx3gSrtConversionEnabled `
            -Tx3gExternalSrtSidecarsEnabled:$Tx3gExternalSrtSidecarsEnabled `
            -DropTx3gAfterConversion:$DropTx3gAfterConversion `
            -BdpgsSrtConversionEnabled:$BdpgsSrtConversionEnabled `
            -DropBdpgsAfterConversion:$DropBdpgsAfterConversion `
            -VobSubSrtConversionEnabled:$VobSubSrtConversionEnabled `
            -DropVobSubAfterConversion:$DropVobSubAfterConversion `
            -FolderPolicyMetadata $FolderPolicyMetadata `
            -RoutePlanMetadata $RoutePlanMetadata `
            -MediaType $MediaType

        $manifestPath = "$parked.manifest.json"
        Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null
        $roundTrip = Read-PendingManifestFile -Path $manifestPath
        if ([string]$roundTrip.local_file -ne $parked -or [string]$roundTrip.server_out -ne $ServerOut -or [string]$roundTrip.manifest_state -ne 'pending_move') {
            throw "pending manifest validation failed before park"
        }

        [System.IO.File]::Move($LocalOut, $parked, $true)
        $stateUpdateOk = $true
        try {
            $manifest['manifest_state'] = 'parked'
            $manifest['parked_at'] = (Get-Date -Format 'o')
            Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null
        } catch {
            $stateUpdateOk = $false
            Write-Log "Park: manifest state update failed after moving output; pending intent remains retryable: $manifestPath : $_" "WARN"
        }

        return [pscustomobject]@{
            Ok = $true; Error = ''; LocalFile = $parked; OriginalLocalFile = $LocalOut; ServerOut = $ServerOut
            ManifestPath = $manifestPath; PublishTransactionId = $PublishTransactionId; SidecarEntries = @($sidecarManifestEntries)
            OutputSize = Get-FileLengthOrNull $parked; Leaf = $leaf; MediaMoved = $true; ManifestStateUpdateOk = $stateUpdateOk
        }
    } catch {
        $mediaParked = $parked -and (Test-Path -LiteralPath $parked -ErrorAction SilentlyContinue)
        if (-not $mediaParked) {
            foreach ($sidecar in @($sidecarManifestEntries)) {
                $sidecarParked = [string]$sidecar.local_file
                if ($sidecarParked -and (Test-Path -LiteralPath $sidecarParked -ErrorAction SilentlyContinue)) {
                    Remove-Item -LiteralPath $sidecarParked -Force -ErrorAction SilentlyContinue
                }
            }
            if ($manifestPath -and (Test-Path -LiteralPath $manifestPath -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $manifestPath -Force -ErrorAction SilentlyContinue
            }
        }
        return [pscustomobject]@{
            Ok = $false; Error = [string]$_; LocalFile = $parked; OriginalLocalFile = $LocalOut; ServerOut = $ServerOut
            ManifestPath = $manifestPath; PublishTransactionId = $PublishTransactionId; SidecarEntries = @($sidecarManifestEntries)
            OutputSize = Get-FileLengthOrNull $LocalOut; Leaf = $leaf; MediaMoved = $mediaParked
        }
    }
}

# Crash recovery for manifest_state='pending_move'. If the manifest exists
# but local_file doesn't, recover sidecars first and then complete the media move
# from original_local_file when possible.
