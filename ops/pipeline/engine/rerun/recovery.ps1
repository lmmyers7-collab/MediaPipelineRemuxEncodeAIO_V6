# CSV rerun recovery state, typed source health, and safe-resume helpers.

$script:RerunRecoveryIdentityModulePath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\audit\rerun_source_identity.ps1'))

function Get-RerunRecoveryValue {
    param($Object, [string]$Name, $Default = $null)
    if ($null -eq $Object) { return $Default }
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) { return $Object[$Name] }
        return $Default
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $Default
}

function Set-RerunRecoveryValue {
    param($Object, [string]$Name, $Value)
    if ($null -eq $Object) { return }
    if ($Object -is [System.Collections.IDictionary]) {
        $Object[$Name] = $Value
        return
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) {
        $property.Value = $Value
    } else {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Add-RerunLifecycleTransition {
    param(
        [Parameter(Mandatory)] $Target,
        [Parameter(Mandatory)] [string]$State,
        [Parameter(Mandatory)] [string]$What,
        [Parameter(Mandatory)] [string]$Why,
        [Parameter(Mandatory)] [string]$Next,
        [string]$ReasonCode = '',
        [switch]$AllowTerminalRecovery
    )

    $previousState = [string](Get-RerunRecoveryValue -Object $Target -Name 'lifecycle_state' -Default '')
    if ($previousState -eq 'terminal' -and $State -ne 'terminal' -and -not $AllowTerminalRecovery) {
        throw "CSV rerun lifecycle regression rejected: terminal -> $State"
    }

    $sequence = 0
    try { $sequence = [int](Get-RerunRecoveryValue -Object $Target -Name 'transition_sequence' -Default 0) } catch {}
    $sequence += 1
    $at = [datetime]::UtcNow.ToString('o')
    $transition = [pscustomobject][ordered]@{
        sequence = $sequence
        state = $State
        at = $at
        reason_code = $ReasonCode
        what = $What
        why = $Why
        when = $at
        next = $Next
    }
    $timeline = @((Get-RerunRecoveryValue -Object $Target -Name 'timeline' -Default @())) + @($transition)
    Set-RerunRecoveryValue -Object $Target -Name 'timeline' -Value $timeline
    Set-RerunRecoveryValue -Object $Target -Name 'transition_sequence' -Value $sequence
    Set-RerunRecoveryValue -Object $Target -Name 'lifecycle_state' -Value $State
    Set-RerunRecoveryValue -Object $Target -Name 'last_transition_at' -Value $at
    Set-RerunRecoveryValue -Object $Target -Name 'what' -Value $What
    Set-RerunRecoveryValue -Object $Target -Name 'why' -Value $Why
    Set-RerunRecoveryValue -Object $Target -Name 'when' -Value $at
    Set-RerunRecoveryValue -Object $Target -Name 'next' -Value $Next
    Set-RerunRecoveryValue -Object $Target -Name 'automatic_next_action' -Value $Next
}

function Set-RerunManifestLifecycle {
    param(
        [Parameter(Mandatory)] $Manifest,
        [Parameter(Mandatory)] [string]$State,
        [Parameter(Mandatory)] [string]$What,
        [Parameter(Mandatory)] [string]$Why,
        [Parameter(Mandatory)] [string]$Next,
        [string]$Status = '',
        [string]$Phase = '',
        [string]$ReasonCode = '',
        [Nullable[int]]$CurrentRowIndex = $null,
        [string]$ManifestPath = '',
        [switch]$Persist,
        [switch]$AllowTerminalRecovery
    )
    Add-RerunLifecycleTransition -Target $Manifest -State $State -What $What -Why $Why -Next $Next -ReasonCode $ReasonCode -AllowTerminalRecovery:$AllowTerminalRecovery
    if ([string]::IsNullOrWhiteSpace($Status)) { $Status = $State }
    if ([string]::IsNullOrWhiteSpace($Phase)) { $Phase = $State }
    Set-RerunRecoveryValue -Object $Manifest -Name 'status' -Value $Status
    Set-RerunRecoveryValue -Object $Manifest -Name 'current_phase' -Value $Phase
    if ($null -ne $CurrentRowIndex) {
        Set-RerunRecoveryValue -Object $Manifest -Name 'current_row_index' -Value ([int]$CurrentRowIndex)
    }
    if ($State -eq 'accepted' -and [string]::IsNullOrWhiteSpace([string](Get-RerunRecoveryValue -Object $Manifest -Name 'started_at' -Default ''))) {
        Set-RerunRecoveryValue -Object $Manifest -Name 'started_at' -Value ([datetime]::UtcNow.ToString('o'))
    }
    if ($State -eq 'terminal') {
        Set-RerunRecoveryValue -Object $Manifest -Name 'completed_at' -Value ([datetime]::UtcNow.ToString('o'))
    }
    if ($Persist) {
        if ([string]::IsNullOrWhiteSpace($ManifestPath)) { throw 'ManifestPath is required to persist a rerun lifecycle transition.' }
        Write-RerunManifest -Path $ManifestPath -Payload $Manifest
    }
}

function Set-RerunPlanLifecycle {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string]$State,
        [Parameter(Mandatory)] [string]$What,
        [Parameter(Mandatory)] [string]$Why,
        [Parameter(Mandatory)] [string]$Next,
        [string]$Status = '',
        [string]$ReasonCode = '',
        [Nullable[bool]]$Retryable = $null,
        [Nullable[bool]]$OperatorActionRequired = $null,
        [string]$AvailableOperatorAction = '',
        $Manifest = $null,
        [string]$ManifestPath = '',
        [switch]$Persist,
        [switch]$AllowTerminalRecovery
    )
    Add-RerunLifecycleTransition -Target $Plan -State $State -What $What -Why $Why -Next $Next -ReasonCode $ReasonCode -AllowTerminalRecovery:$AllowTerminalRecovery
    if ([string]::IsNullOrWhiteSpace($Status)) { $Status = $State }
    Set-RerunRecoveryValue -Object $Plan -Name 'status' -Value $Status
    Set-RerunRecoveryValue -Object $Plan -Name 'reason' -Value $Why
    Set-RerunRecoveryValue -Object $Plan -Name 'reason_code' -Value $ReasonCode
    if ($Status -in @('failed','review','retry_exhausted') -or $State -in @('failed','review','retry_exhausted')) {
        Set-RerunRecoveryValue -Object $Plan -Name 'failure_code' -Value $ReasonCode
    } elseif ($State -in @('accepted','staging','staged','processing','destination_policy','terminal')) {
        Set-RerunRecoveryValue -Object $Plan -Name 'failure_code' -Value ''
    }
    if ($null -ne $Retryable) { Set-RerunRecoveryValue -Object $Plan -Name 'retryable' -Value ([bool]$Retryable) }
    if ($null -ne $OperatorActionRequired) { Set-RerunRecoveryValue -Object $Plan -Name 'operator_action_required' -Value ([bool]$OperatorActionRequired) }
    if (-not [string]::IsNullOrWhiteSpace($AvailableOperatorAction)) {
        Set-RerunRecoveryValue -Object $Plan -Name 'available_operator_action' -Value $AvailableOperatorAction
    }

    if ($null -ne $Manifest) {
        $rowIndex = 0
        try { $rowIndex = [int](Get-RerunRecoveryValue -Object $Plan -Name 'row_index' -Default 0) } catch {}
        $manifestState = if ($State -eq 'terminal') { 'destination_policy' } else { $State }
        $manifestStatus = if ($State -eq 'terminal') { 'destination_policy' } else { $Status }
        Add-RerunLifecycleTransition `
            -Target $Manifest `
            -State $manifestState `
            -What "Row ${rowIndex}: $What" `
            -Why $Why `
            -Next $Next `
            -ReasonCode $ReasonCode `
            -AllowTerminalRecovery:$AllowTerminalRecovery
        Set-RerunRecoveryValue -Object $Manifest -Name 'status' -Value $manifestStatus
        $phase = switch ($manifestState) {
            'waiting' { 'waiting_for_source' }
            'retry_scheduled' { 'waiting_for_source' }
            default { $manifestState }
        }
        Set-RerunRecoveryValue -Object $Manifest -Name 'current_phase' -Value $phase
        Set-RerunRecoveryValue -Object $Manifest -Name 'current_row_index' -Value $rowIndex
        if ($Persist) {
            if ([string]::IsNullOrWhiteSpace($ManifestPath)) { throw 'ManifestPath is required to persist a rerun row transition.' }
            Write-RerunManifest -Path $ManifestPath -Payload $Manifest
        }
    }
}

function Get-RerunSourceRootPath {
    param([Parameter(Mandatory)] [string]$SourcePath)
    if ([string]::IsNullOrWhiteSpace($SourcePath)) { return '' }
    try {
        $root = [System.IO.Path]::GetPathRoot($SourcePath)
        if ($root) {
            $text = [string]$root
            if (($SourcePath.StartsWith('\\') -or $SourcePath.StartsWith('//')) -and -not $text.EndsWith([string][System.IO.Path]::DirectorySeparatorChar)) {
                $text += [System.IO.Path]::DirectorySeparatorChar
            }
            return $text
        }
    } catch {}
    return ''
}

function Get-RerunRecoveryFirstText {
    param($Object, [string[]]$Names)
    foreach ($name in @($Names)) {
        $value = [string](Get-RerunRecoveryValue -Object $Object -Name $name -Default '')
        if (-not [string]::IsNullOrWhiteSpace($value)) { return $value.Trim() }
    }
    return ''
}

function Resolve-RerunConfiguredSourceRoot {
    param(
        [hashtable]$Config,
        [Parameter(Mandatory)] [string]$SourcePath
    )
    if ($null -eq $Config -or [string]::IsNullOrWhiteSpace($SourcePath)) { return '' }
    $candidates = [System.Collections.Generic.List[string]]::new()
    foreach ($key in @('SourceMovies','SourceTV')) {
        $candidate = [string](Get-RerunRecoveryValue -Object $Config -Name $key -Default '')
        if (-not [string]::IsNullOrWhiteSpace($candidate)) { $candidates.Add($candidate) | Out-Null }
    }
    foreach ($profile in @((Get-RerunRecoveryValue -Object $Config -Name 'LibraryProfiles' -Default @()))) {
        $candidate = Get-RerunRecoveryFirstText -Object $profile -Names @('source_path','SourcePath','source_root','SourceRoot')
        if (-not [string]::IsNullOrWhiteSpace($candidate)) { $candidates.Add($candidate) | Out-Null }
    }

    $sourceFull = ''
    try { $sourceFull = [System.IO.Path]::GetFullPath($SourcePath) } catch { return '' }
    $matches = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in $candidates) {
        try {
            $candidateFull = [System.IO.Path]::GetFullPath($candidate)
            $candidatePathRoot = [System.IO.Path]::GetPathRoot($candidateFull)
            if (-not $candidateFull.Equals($candidatePathRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                $candidateFull = $candidateFull.TrimEnd(
                    [System.IO.Path]::DirectorySeparatorChar,
                    [System.IO.Path]::AltDirectorySeparatorChar
                )
            }
            if (Test-RerunRecoveryPathUnderRoot -Path $sourceFull -Root $candidateFull) {
                $matches.Add($candidateFull) | Out-Null
            }
        } catch {}
    }
    if ($matches.Count -eq 0) { return '' }
    return [string]($matches | Sort-Object Length -Descending | Select-Object -First 1)
}

function Get-RerunSourceExceptionCode {
    param([Parameter(Mandatory)] [System.Exception]$Exception)
    $current = $Exception
    while ($null -ne $current) {
        if ($current -is [System.UnauthorizedAccessException] -or $current -is [System.Security.SecurityException]) {
            return 'source_access_failed'
        }
        if ($current -is [System.IO.FileNotFoundException]) { return 'source_missing' }
        if ($current -is [System.IO.DriveNotFoundException] -or $current -is [System.IO.DirectoryNotFoundException]) {
            return 'source_location_unavailable'
        }
        if ($current -is [System.TimeoutException] -or $current -is [System.IO.IOException]) {
            return 'source_access_failed'
        }
        $current = $current.InnerException
    }
    return 'source_access_failed'
}

function New-RerunSourceHealthResult {
    param(
        [string]$Code,
        [string]$Message,
        [bool]$Retryable,
        [string]$RootPath = '',
        $FileInfo = $null,
        [string]$IdentityV2 = '',
        [string]$ContentSha256 = ''
    )
    return [pscustomobject][ordered]@{
        Available = ($Code -eq 'available')
        Code = $Code
        Message = $Message
        Retryable = $Retryable
        RootPath = $RootPath
        FileInfo = $FileInfo
        IdentityV2 = $IdentityV2
        ContentSha256 = $ContentSha256
    }
}

function Invoke-RerunBoundedProbeJob {
    param(
        [Parameter(Mandatory)] [scriptblock]$ScriptBlock,
        [array]$ArgumentList = @(),
        [ValidateRange(1, 7200)] [int]$TimeoutSeconds = 10
    )
    $job = $null
    try {
        $job = Start-Job -ScriptBlock $ScriptBlock -ArgumentList $ArgumentList
        if (-not (Wait-Job -Job $job -Timeout $TimeoutSeconds)) {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            return [pscustomobject]@{ TimedOut = $true; Result = $null }
        }
        $result = @(Receive-Job -Job $job -ErrorAction SilentlyContinue) | Select-Object -Last 1
        return [pscustomobject]@{ TimedOut = $false; Result = $result }
    } catch {
        return [pscustomobject]@{
            TimedOut = $false
            Result = [pscustomobject]@{ Code = 'source_access_failed'; Message = $_.Exception.Message }
        }
    } finally {
        if ($null -ne $job) {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-RerunSourceHealth {
    param(
        [Parameter(Mandatory)] [string]$SourcePath,
        [string]$ExpectedIdentityV2 = '',
        [string]$ExpectedContentSha256 = '',
        [Nullable[long]]$ExpectedSize = $null,
        [string]$ExpectedMtimeUtc = '',
        [string]$ConfiguredRootPath = '',
        [string]$FfprobePath = '',
        [ValidateRange(1, 300)] [int]$ProbeTimeoutSeconds = 10,
        [ValidateRange(1, 7200)] [int]$IdentityTimeoutSeconds = 1800,
        [ValidateRange(0, 300000)] [int]$SimulatedProbeDelayMilliseconds = 0
    )
    $rootPath = Get-RerunSourceRootPath -SourcePath $SourcePath
    if ([string]::IsNullOrWhiteSpace($rootPath)) {
        return New-RerunSourceHealthResult -Code 'source_missing' -Message 'Source path is not fully qualified.' -Retryable $false
    }
    if (-not [string]::IsNullOrWhiteSpace($ConfiguredRootPath)) {
        try {
            $configuredFull = [System.IO.Path]::GetFullPath($ConfiguredRootPath)
            $configuredPathRoot = [System.IO.Path]::GetPathRoot($configuredFull)
            if (-not $configuredFull.Equals($configuredPathRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                $configuredFull = $configuredFull.TrimEnd(
                    [System.IO.Path]::DirectorySeparatorChar,
                    [System.IO.Path]::AltDirectorySeparatorChar
                )
            }
            if (-not (Test-RerunRecoveryPathUnderRoot -Path $SourcePath -Root $configuredFull)) {
                return New-RerunSourceHealthResult -Code 'source_missing' -Message "Source path is outside the configured source root: $configuredFull" -Retryable $false -RootPath $configuredFull
            }
            $rootPath = $configuredFull
        } catch {
            return New-RerunSourceHealthResult -Code 'source_missing' -Message "Configured source root is invalid: $ConfiguredRootPath" -Retryable $false
        }
    }

    $rootProbe = Invoke-RerunBoundedProbeJob -TimeoutSeconds $ProbeTimeoutSeconds -ArgumentList @($rootPath, $SimulatedProbeDelayMilliseconds) -ScriptBlock {
        param($ProbeRoot, $DelayMilliseconds)
        if ([int]$DelayMilliseconds -gt 0) { Start-Sleep -Milliseconds ([int]$DelayMilliseconds) }
        try {
            if (Test-Path -LiteralPath $ProbeRoot -PathType Container -ErrorAction Stop) {
                [pscustomobject]@{ Code = 'available'; Message = 'Source root is reachable.' }
            } else {
                [pscustomobject]@{ Code = 'source_location_unavailable'; Message = "Configured source root is unavailable: $ProbeRoot" }
            }
        } catch [System.UnauthorizedAccessException] {
            [pscustomobject]@{ Code = 'source_access_failed'; Message = $_.Exception.Message }
        } catch [System.Security.SecurityException] {
            [pscustomobject]@{ Code = 'source_access_failed'; Message = $_.Exception.Message }
        } catch {
            [pscustomobject]@{ Code = 'source_access_failed'; Message = $_.Exception.Message }
        }
    }
    if ($rootProbe.TimedOut) {
        return New-RerunSourceHealthResult -Code 'source_access_failed' -Message "Source root probe timed out after ${ProbeTimeoutSeconds}s: $rootPath" -Retryable $true -RootPath $rootPath
    }
    if ($null -eq $rootProbe.Result -or [string]$rootProbe.Result.Code -ne 'available') {
        $code = if ($null -eq $rootProbe.Result) { 'source_access_failed' } else { [string]$rootProbe.Result.Code }
        $message = if ($null -eq $rootProbe.Result) { 'Source root probe returned no evidence.' } else { [string]$rootProbe.Result.Message }
        return New-RerunSourceHealthResult -Code $code -Message $message -Retryable ($code -in @('source_location_unavailable','source_access_failed')) -RootPath $rootPath
    }

    $identityModulePath = [string]$script:RerunRecoveryIdentityModulePath
    $fileProbe = Invoke-RerunBoundedProbeJob -TimeoutSeconds $IdentityTimeoutSeconds -ArgumentList @($SourcePath, $FfprobePath, $identityModulePath) -ScriptBlock {
        param($ProbeSourcePath, $ProbeFfprobePath, $IdentityModulePath)
        try {
            if (-not (Test-Path -LiteralPath $ProbeSourcePath -PathType Leaf -ErrorAction Stop)) {
                return [pscustomobject]@{ Code = 'source_missing'; Message = "Source file is missing under a reachable root: $ProbeSourcePath" }
            }
            $item = Get-Item -LiteralPath $ProbeSourcePath -Force -ErrorAction Stop
            if (-not ($item -is [System.IO.FileInfo])) {
                return [pscustomobject]@{ Code = 'source_missing'; Message = "Source path is not a file: $ProbeSourcePath" }
            }
            if (-not (Test-Path -LiteralPath $IdentityModulePath -PathType Leaf)) {
                return [pscustomobject]@{ Code = 'source_access_failed'; Message = "Source identity module is unavailable: $IdentityModulePath" }
            }
            . $IdentityModulePath
            $sampleHash = Get-RerunSourceSampleHash -Path $item.FullName -Size ([long]$item.Length)
            if ([string]::IsNullOrWhiteSpace([string]$sampleHash)) {
                return [pscustomobject]@{ Code = 'source_access_failed'; Message = 'Source contents could not be read for identity verification.' }
            }
            $identity = Get-RerunSourceIdentityV2 -FileInfo $item -FfprobePath $ProbeFfprobePath
            if ([string]::IsNullOrWhiteSpace([string]$identity)) {
                return [pscustomobject]@{ Code = 'source_access_failed'; Message = 'Source identity could not be computed.' }
            }
            # Compute the full-file authority last so the accepted digest is
            # newer than the sampled/ffprobe evidence and immediately precedes
            # the final size/mtime stability check.
            $contentSha256 = Get-RerunContentSha256 -Path $item.FullName
            if ([string]::IsNullOrWhiteSpace([string]$contentSha256)) {
                return [pscustomobject]@{ Code = 'source_access_failed'; Message = 'Source contents could not be read for full SHA-256 verification.' }
            }
            $afterItem = Get-Item -LiteralPath $ProbeSourcePath -Force -ErrorAction Stop
            if ([long]$afterItem.Length -ne [long]$item.Length -or $afterItem.LastWriteTimeUtc -ne $item.LastWriteTimeUtc) {
                return [pscustomobject]@{ Code = 'source_identity_changed'; Message = 'Source changed while identity evidence was being computed.' }
            }
            return [pscustomobject][ordered]@{
                Code = 'available'
                Message = 'Source file, sampled fingerprint, and full SHA-256 are available.'
                FullName = $item.FullName
                Name = $item.Name
                DirectoryName = $item.DirectoryName
                Extension = $item.Extension
                Length = [long]$item.Length
                LastWriteTimeUtc = $item.LastWriteTimeUtc.ToString('o')
                IdentityV2 = [string]$identity
                ContentSha256 = [string]$contentSha256
            }
        } catch [System.UnauthorizedAccessException] {
            [pscustomobject]@{ Code = 'source_access_failed'; Message = $_.Exception.Message }
        } catch [System.Security.SecurityException] {
            [pscustomobject]@{ Code = 'source_access_failed'; Message = $_.Exception.Message }
        } catch [System.IO.FileNotFoundException] {
            [pscustomobject]@{ Code = 'source_missing'; Message = $_.Exception.Message }
        } catch [System.IO.DriveNotFoundException] {
            [pscustomobject]@{ Code = 'source_location_unavailable'; Message = $_.Exception.Message }
        } catch [System.IO.DirectoryNotFoundException] {
            [pscustomobject]@{ Code = 'source_location_unavailable'; Message = $_.Exception.Message }
        } catch {
            [pscustomobject]@{ Code = 'source_access_failed'; Message = $_.Exception.Message }
        }
    }
    if ($fileProbe.TimedOut) {
        return New-RerunSourceHealthResult -Code 'source_access_failed' -Message "Source metadata/identity probe timed out after ${IdentityTimeoutSeconds}s: $SourcePath" -Retryable $true -RootPath $rootPath
    }
    if ($null -eq $fileProbe.Result -or [string]$fileProbe.Result.Code -ne 'available') {
        $code = if ($null -eq $fileProbe.Result) { 'source_access_failed' } else { [string]$fileProbe.Result.Code }
        $message = if ($null -eq $fileProbe.Result) { 'Source metadata/identity probe returned no evidence.' } else { [string]$fileProbe.Result.Message }
        return New-RerunSourceHealthResult -Code $code -Message $message -Retryable ($code -in @('source_location_unavailable','source_access_failed')) -RootPath $rootPath
    }

    $fileInfo = [pscustomobject][ordered]@{
        FullName = [string]$fileProbe.Result.FullName
        Name = [string]$fileProbe.Result.Name
        DirectoryName = [string]$fileProbe.Result.DirectoryName
        Extension = [string]$fileProbe.Result.Extension
        Length = [long]$fileProbe.Result.Length
        LastWriteTimeUtc = [datetime]::Parse([string]$fileProbe.Result.LastWriteTimeUtc, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind)
    }
    $identity = [string]$fileProbe.Result.IdentityV2
    $contentSha256 = [string]$fileProbe.Result.ContentSha256

    if ($null -ne $ExpectedSize -and [long]$ExpectedSize -ge 0 -and [long]$fileInfo.Length -ne [long]$ExpectedSize) {
        return New-RerunSourceHealthResult -Code 'source_identity_changed' -Message "Source size changed: expected=$ExpectedSize current=$($fileInfo.Length)" -Retryable $false -RootPath $rootPath -FileInfo $fileInfo
    }
    if (-not [string]::IsNullOrWhiteSpace($ExpectedMtimeUtc)) {
        try {
            $parsed = [datetimeoffset]::Parse($ExpectedMtimeUtc, [System.Globalization.CultureInfo]::InvariantCulture)
            if ([math]::Abs(($fileInfo.LastWriteTimeUtc - $parsed.UtcDateTime).TotalSeconds) -gt 2) {
                return New-RerunSourceHealthResult -Code 'source_identity_changed' -Message "Source mtime changed: expected=$ExpectedMtimeUtc current=$($fileInfo.LastWriteTimeUtc.ToString('o'))" -Retryable $false -RootPath $rootPath -FileInfo $fileInfo
            }
        } catch [System.FormatException] {
            return New-RerunSourceHealthResult -Code 'source_identity_changed' -Message "Source identity evidence contains an invalid mtime: $ExpectedMtimeUtc" -Retryable $false -RootPath $rootPath -FileInfo $fileInfo
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($ExpectedIdentityV2) -and -not ([string]$identity).Equals($ExpectedIdentityV2, [System.StringComparison]::OrdinalIgnoreCase)) {
        return New-RerunSourceHealthResult -Code 'source_identity_changed' -Message 'Source sampled identity v2 changed.' -Retryable $false -RootPath $rootPath -FileInfo $fileInfo -IdentityV2 ([string]$identity) -ContentSha256 $contentSha256
    }
    if (-not [string]::IsNullOrWhiteSpace($ExpectedContentSha256) -and -not $contentSha256.Equals($ExpectedContentSha256, [System.StringComparison]::OrdinalIgnoreCase)) {
        return New-RerunSourceHealthResult -Code 'source_identity_changed' -Message 'Source full-content SHA-256 changed.' -Retryable $false -RootPath $rootPath -FileInfo $fileInfo -IdentityV2 ([string]$identity) -ContentSha256 $contentSha256
    }
    return New-RerunSourceHealthResult -Code 'available' -Message 'Source file, sampled fingerprint, and full SHA-256 are available.' -Retryable $false -RootPath $rootPath -FileInfo $fileInfo -IdentityV2 ([string]$identity) -ContentSha256 $contentSha256
}

function Get-RerunRetryDelaySeconds {
    param([int]$Attempt, [int[]]$BackoffSeconds)
    $schedule = @($BackoffSeconds | ForEach-Object { [math]::Max(0, [int]$_) })
    if ($schedule.Count -eq 0) { return 0 }
    $index = [math]::Min([math]::Max(0, $Attempt - 1), $schedule.Count - 1)
    return [int]$schedule[$index]
}

function Invoke-RerunSourceAvailabilityRecovery {
    param(
        [Parameter(Mandatory)] $Plan,
        [ValidateRange(1, 20)] [int]$MaxAttempts = 3,
        [int[]]$BackoffSeconds = @(5, 15, 45),
        [string]$FfprobePath = '',
        [ValidateRange(1, 300)] [int]$ProbeTimeoutSeconds = 10,
        [ValidateRange(1, 7200)] [int]$IdentityTimeoutSeconds = 1800,
        [ValidateRange(0, 300000)] [int]$SimulatedProbeDelayMilliseconds = 0,
        [scriptblock]$SleepAction = { param([int]$Seconds) if ($Seconds -gt 0) { Start-Sleep -Seconds $Seconds } },
        $Manifest = $null,
        [string]$ManifestPath = ''
    )
    $sourcePath = [string](Get-RerunRecoveryValue -Object $Plan -Name 'source_path' -Default '')
    $expectedIdentity = [string](Get-RerunRecoveryValue -Object $Plan -Name 'planned_source_identity_v2' -Default '')
    if ([string]::IsNullOrWhiteSpace($expectedIdentity)) {
        $expectedIdentity = [string](Get-RerunRecoveryValue -Object $Plan -Name 'source_identity_v2' -Default '')
    }
    $expectedContentSha256 = [string](Get-RerunRecoveryValue -Object $Plan -Name 'planned_source_content_sha256' -Default '')
    if ([string]::IsNullOrWhiteSpace($expectedContentSha256)) {
        $expectedContentSha256 = [string](Get-RerunRecoveryValue -Object $Plan -Name 'source_content_sha256' -Default '')
    }
    $expectedContentSha256Algorithm = [string](Get-RerunRecoveryValue -Object $Plan -Name 'source_content_sha256_algorithm' -Default '')
    $strongIdentityFailureCode = ''
    $strongIdentityFailureMessage = ''
    if ($expectedContentSha256 -notmatch '^[A-Fa-f0-9]{64}$') {
        $strongIdentityFailureCode = 'source_content_sha256_missing'
        $strongIdentityFailureMessage = 'The accepted row has no valid source_content_sha256 evidence, so reconnect identity cannot be proven.'
    } elseif ($expectedContentSha256Algorithm -cne 'sha256-full-file') {
        $strongIdentityFailureCode = 'source_content_sha256_algorithm_invalid'
        $algorithmDisplay = if ([string]::IsNullOrWhiteSpace($expectedContentSha256Algorithm)) { '(missing)' } else { $expectedContentSha256Algorithm }
        $strongIdentityFailureMessage = "The accepted row does not declare the required sha256-full-file authority (found $algorithmDisplay), so reconnect identity cannot be proven."
    }
    if (-not [string]::IsNullOrWhiteSpace($strongIdentityFailureCode)) {
        Set-RerunPlanLifecycle -Plan $Plan -State 'review' -Status 'review' -What 'Automatic source recovery was blocked.' -Why $strongIdentityFailureMessage -Next 'Review the source full-content identity and start a new correlated rerun.' -ReasonCode $strongIdentityFailureCode -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review full source identity before retrying.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:($null -ne $Manifest -and -not [string]::IsNullOrWhiteSpace($ManifestPath))
        Set-RerunRecoveryValue -Object $Plan -Name 'last_error' -Value $strongIdentityFailureMessage
        $missingHashHealth = New-RerunSourceHealthResult -Code $strongIdentityFailureCode -Message $strongIdentityFailureMessage -Retryable $false
        return [pscustomobject]@{ Ready = $false; Health = $missingHashHealth }
    }
    $configuredRootPath = [string](Get-RerunRecoveryValue -Object $Plan -Name 'source_root' -Default '')
    $expectedSize = $null
    $sizeValue = Get-RerunRecoveryValue -Object $Plan -Name 'source_size' -Default $null
    if ($null -ne $sizeValue -and [string]$sizeValue -match '^\d+$') { $expectedSize = [long]$sizeValue }
    $expectedMtime = [string](Get-RerunRecoveryValue -Object $Plan -Name 'source_mtime_utc' -Default '')
    Set-RerunRecoveryValue -Object $Plan -Name 'max_attempts' -Value $MaxAttempts

    while ($true) {
        $health = Get-RerunSourceHealth -SourcePath $sourcePath -ExpectedIdentityV2 $expectedIdentity -ExpectedContentSha256 $expectedContentSha256 -ExpectedSize $expectedSize -ExpectedMtimeUtc $expectedMtime -ConfiguredRootPath $configuredRootPath -FfprobePath $FfprobePath -ProbeTimeoutSeconds $ProbeTimeoutSeconds -IdentityTimeoutSeconds $IdentityTimeoutSeconds -SimulatedProbeDelayMilliseconds $SimulatedProbeDelayMilliseconds
        if ($health.Available) {
            Set-RerunRecoveryValue -Object $Plan -Name 'planned_source_identity_v2' -Value ([string]$health.IdentityV2)
            Set-RerunRecoveryValue -Object $Plan -Name 'source_identity_v2' -Value ([string]$health.IdentityV2)
            Set-RerunRecoveryValue -Object $Plan -Name 'planned_source_content_sha256' -Value ([string]$health.ContentSha256)
            Set-RerunRecoveryValue -Object $Plan -Name 'source_content_sha256' -Value ([string]$health.ContentSha256)
            Set-RerunRecoveryValue -Object $Plan -Name 'source_content_sha256_algorithm' -Value 'sha256-full-file'
            Set-RerunRecoveryValue -Object $Plan -Name 'source_root' -Value ([string]$health.RootPath)
            Set-RerunRecoveryValue -Object $Plan -Name 'source_size' -Value ([long]$health.FileInfo.Length)
            Set-RerunRecoveryValue -Object $Plan -Name 'source_mtime_utc' -Value $health.FileInfo.LastWriteTimeUtc.ToString('o')
            return [pscustomobject]@{ Ready = $true; Health = $health }
        }

        if ($health.Code -in @('source_location_unavailable','source_access_failed')) {
            $attempt = 0
            try { $attempt = [int](Get-RerunRecoveryValue -Object $Plan -Name 'attempt_count' -Default 0) } catch {}
            $attempt += 1
            $now = [datetime]::UtcNow.ToString('o')
            Set-RerunRecoveryValue -Object $Plan -Name 'attempt_count' -Value $attempt
            if ([string]::IsNullOrWhiteSpace([string](Get-RerunRecoveryValue -Object $Plan -Name 'first_failure_at' -Default ''))) {
                Set-RerunRecoveryValue -Object $Plan -Name 'first_failure_at' -Value $now
            }
            Set-RerunRecoveryValue -Object $Plan -Name 'last_failure_at' -Value $now
            Set-RerunRecoveryValue -Object $Plan -Name 'last_error' -Value $health.Message
            Set-RerunPlanLifecycle -Plan $Plan -State 'waiting' -Status 'waiting' -What 'Source availability check is waiting.' -Why $health.Message -Next 'Apply the bounded retry schedule.' -ReasonCode $health.Code -Retryable $true -OperatorActionRequired $false -AvailableOperatorAction 'Wait or request Retry now.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:($null -ne $Manifest -and -not [string]::IsNullOrWhiteSpace($ManifestPath))

            if ($attempt -ge $MaxAttempts) {
                Set-RerunRecoveryValue -Object $Plan -Name 'next_retry_at' -Value ''
                Set-RerunPlanLifecycle -Plan $Plan -State 'retry_exhausted' -Status 'retry_exhausted' -What 'Automatic source retries were exhausted.' -Why $health.Message -Next 'Wait for an operator retry after restoring the source root.' -ReasonCode $health.Code -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Retry after restoring the source root.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:($null -ne $Manifest -and -not [string]::IsNullOrWhiteSpace($ManifestPath))
                return [pscustomobject]@{ Ready = $false; Health = $health }
            }

            $delay = Get-RerunRetryDelaySeconds -Attempt $attempt -BackoffSeconds $BackoffSeconds
            $nextRetryAt = [datetime]::UtcNow.AddSeconds($delay).ToString('o')
            Set-RerunRecoveryValue -Object $Plan -Name 'next_retry_at' -Value $nextRetryAt
            Set-RerunPlanLifecycle -Plan $Plan -State 'retry_scheduled' -Status 'retry_scheduled' -What 'A bounded source retry was scheduled.' -Why $health.Message -Next "Retry source availability at $nextRetryAt." -ReasonCode $health.Code -Retryable $true -OperatorActionRequired $false -AvailableOperatorAction 'Wait or request Retry now.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:($null -ne $Manifest -and -not [string]::IsNullOrWhiteSpace($ManifestPath))
            & $SleepAction $delay
            continue
        }

        $terminalStatus = if ($health.Code -eq 'source_identity_changed') { 'review' } else { 'failed' }
        $next = if ($terminalStatus -eq 'review') { 'Review the changed source identity; automatic staging is blocked.' } else { 'Correct the source path or access problem before retrying.' }
        Set-RerunPlanLifecycle -Plan $Plan -State $terminalStatus -Status $terminalStatus -What 'Source validation blocked automatic staging.' -Why $health.Message -Next $next -ReasonCode $health.Code -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction $next -Manifest $Manifest -ManifestPath $ManifestPath -Persist:($null -ne $Manifest -and -not [string]::IsNullOrWhiteSpace($ManifestPath))
        Set-RerunRecoveryValue -Object $Plan -Name 'last_error' -Value $health.Message
        return [pscustomobject]@{ Ready = $false; Health = $health }
    }
}

function Test-RerunRecoveryPathUnderRoot {
    param([Parameter(Mandatory)] [string]$Path, [Parameter(Mandatory)] [string]$Root)
    try {
        $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
        $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
        if ($pathFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
        $prefix = $rootFull + [System.IO.Path]::DirectorySeparatorChar
        return $pathFull.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
    } catch {
        return $false
    }
}

function Clear-RerunStageAttemptArtifacts {
    param(
        [Parameter(Mandatory)] [string]$BatchScratchRoot,
        [Parameter(Mandatory)] [ValidatePattern('^[A-Za-z0-9_-]+$')] [string]$AttemptId
    )
    if (-not (Test-Path -LiteralPath $BatchScratchRoot -PathType Container)) { return }
    $partialSuffix = ".rerun-partial.$AttemptId"
    foreach ($file in @(Get-ChildItem -LiteralPath $BatchScratchRoot -File -Recurse -Force -ErrorAction SilentlyContinue)) {
        if (-not $file.Name.EndsWith($partialSuffix, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
        if (Test-RerunRecoveryPathUnderRoot -Path $file.FullName -Root $BatchScratchRoot) {
            Remove-Item -LiteralPath $file.FullName -Force -ErrorAction SilentlyContinue
        }
    }
    $attemptDirs = @(Get-ChildItem -LiteralPath $BatchScratchRoot -Directory -Recurse -Force -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq $AttemptId -and $_.Parent -and $_.Parent.Name -eq '.mediapipeline-rerun-staging'
    } | Sort-Object { $_.FullName.Length } -Descending)
    foreach ($dir in $attemptDirs) {
        if (Test-RerunRecoveryPathUnderRoot -Path $dir.FullName -Root $BatchScratchRoot) {
            Remove-Item -LiteralPath $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Test-RerunStagedPlanEvidence {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string]$BatchScratchRoot,
        [string]$FfprobePath = ''
    )
    $stagePath = [string](Get-RerunRecoveryValue -Object $Plan -Name 'stage_path' -Default '')
    if ([string]::IsNullOrWhiteSpace($stagePath) -or -not (Test-RerunRecoveryPathUnderRoot -Path $stagePath -Root $BatchScratchRoot)) { return $false }
    if (-not (Test-Path -LiteralPath $stagePath -PathType Leaf)) { return $false }
    $expectedIdentity = [string](Get-RerunRecoveryValue -Object $Plan -Name 'staged_source_identity_v2' -Default '')
    if ([string]::IsNullOrWhiteSpace($expectedIdentity)) {
        $expectedIdentity = [string](Get-RerunRecoveryValue -Object $Plan -Name 'planned_source_identity_v2' -Default '')
    }
    $expectedContentSha256 = [string](Get-RerunRecoveryValue -Object $Plan -Name 'staged_source_content_sha256' -Default '')
    if ([string]::IsNullOrWhiteSpace($expectedContentSha256)) {
        $expectedContentSha256 = [string](Get-RerunRecoveryValue -Object $Plan -Name 'planned_source_content_sha256' -Default '')
    }
    $expectedContentSha256Algorithm = [string](Get-RerunRecoveryValue -Object $Plan -Name 'source_content_sha256_algorithm' -Default '')
    if (
        [string]::IsNullOrWhiteSpace($expectedIdentity) -or
        $expectedContentSha256 -notmatch '^[A-Fa-f0-9]{64}$' -or
        $expectedContentSha256Algorithm -cne 'sha256-full-file'
    ) { return $false }
    try {
        $stageInfo = Get-Item -LiteralPath $stagePath -Force -ErrorAction Stop
        $expectedSize = Get-RerunRecoveryValue -Object $Plan -Name 'source_size' -Default $null
        if ($null -ne $expectedSize -and [string]$expectedSize -match '^\d+$' -and [long]$stageInfo.Length -ne [long]$expectedSize) { return $false }
        $health = Get-RerunSourceHealth `
            -SourcePath $stagePath `
            -ConfiguredRootPath $BatchScratchRoot `
            -ExpectedIdentityV2 $expectedIdentity `
            -ExpectedContentSha256 $expectedContentSha256 `
            -ExpectedSize $expectedSize `
            -FfprobePath $FfprobePath
        return [bool]$health.Available
    } catch {
        return $false
    }
}

function Get-RerunResumeDisposition {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string]$BatchScratchRoot,
        [string]$FfprobePath = ''
    )
    $status = [string](Get-RerunRecoveryValue -Object $Plan -Name 'status' -Default '')
    $state = [string](Get-RerunRecoveryValue -Object $Plan -Name 'lifecycle_state' -Default $status)
    if ($state -eq 'terminal' -or $status -in @('complete','completed','published','parked','pending_publish','review','failed','retry_exhausted','skipped')) {
        return [pscustomobject]@{ Action = 'terminal'; Reason = 'Row is already terminal.' }
    }
    if ($status -eq 'staged' -or $state -eq 'staged') {
        $nestedLaunchCount = 0
        try { $nestedLaunchCount = [int](Get-RerunRecoveryValue -Object $Plan -Name 'nested_launch_count' -Default 0) } catch {}
        if ($nestedLaunchCount -gt 0) {
            return [pscustomobject]@{ Action = 'review'; Reason = 'Staged status has prior nested-launch evidence and could represent stale progress.' }
        }
        if (Test-RerunStagedPlanEvidence -Plan $Plan -BatchScratchRoot $BatchScratchRoot -FfprobePath $FfprobePath) {
            return [pscustomobject]@{ Action = 'resume_staged'; Reason = 'Staged scratch identity was verified.' }
        }
        return [pscustomobject]@{ Action = 'review'; Reason = 'Staged scratch could not be verified.' }
    }
    if ($status -eq 'staging' -or $state -eq 'staging') {
        $nestedLaunchCount = 0
        try { $nestedLaunchCount = [int](Get-RerunRecoveryValue -Object $Plan -Name 'nested_launch_count' -Default 0) } catch {}
        if (Test-RerunStagedPlanEvidence -Plan $Plan -BatchScratchRoot $BatchScratchRoot -FfprobePath $FfprobePath) {
            if ($nestedLaunchCount -gt 0) {
                return [pscustomobject]@{ Action = 'review'; Reason = 'Verified final stage exists, but prior nested-launch evidence makes replay ambiguous.' }
            }
            $verifiedAttemptId = [string](Get-RerunRecoveryValue -Object $Plan -Name 'stage_attempt_id' -Default '')
            if (-not [string]::IsNullOrWhiteSpace($verifiedAttemptId)) {
                Clear-RerunStageAttemptArtifacts -BatchScratchRoot $BatchScratchRoot -AttemptId $verifiedAttemptId
            }
            return [pscustomobject]@{ Action = 'resume_staged'; Reason = 'Atomic promotion completed before the staged manifest transition; final scratch identity was verified.' }
        }
        $attemptId = [string](Get-RerunRecoveryValue -Object $Plan -Name 'stage_attempt_id' -Default '')
        if (-not [string]::IsNullOrWhiteSpace($attemptId)) {
            Clear-RerunStageAttemptArtifacts -BatchScratchRoot $BatchScratchRoot -AttemptId $attemptId
            return [pscustomobject]@{ Action = 'restart_staging'; Reason = 'Attempt-scoped partial artifacts were removed before staging retry.' }
        }
        return [pscustomobject]@{ Action = 'review'; Reason = 'Interrupted staging has no attempt identity.' }
    }
    if ($status -in @('requested','accepted','manifest_created','pending','waiting','retry_scheduled') -or $state -in @('requested','accepted','manifest_created','pending','waiting','retry_scheduled')) {
        return [pscustomobject]@{ Action = 'replan'; Reason = 'No nested media work has begun.' }
    }
    if ($status -in @('processing','destination_policy') -or $state -in @('processing','destination_policy')) {
        return [pscustomobject]@{ Action = 'review'; Reason = 'Prior nested or destination work is ambiguous and cannot be replayed automatically.' }
    }
    return [pscustomobject]@{ Action = 'review'; Reason = "Unknown resume state: $status/$state" }
}

function Get-RerunSourceWorkOrder {
    param([array]$Plans)
    return @($Plans | Sort-Object `
        @{ Expression = { if ([string]$_.status -in @('pending','staged')) { 0 } else { 1 } } }, `
        @{ Expression = { try { [int]$_.row_index } catch { 0 } } })
}

function Get-RerunHighestAllocatedChunkIndex {
    param($Manifest = $null, [array]$Plans = @())
    $highest = 0
    foreach ($value in @((Get-RerunRecoveryValue -Object $Manifest -Name 'current_chunk' -Default 0))) {
        try { $highest = [math]::Max($highest, [int]$value) } catch {}
    }
    foreach ($plan in @($Plans)) {
        try {
            $highest = [math]::Max($highest, [int](Get-RerunRecoveryValue -Object $plan -Name 'rerun_chunk_index' -Default 0))
        } catch {}
        foreach ($text in @(
            [string](Get-RerunRecoveryValue -Object $plan -Name 'nested_launch_id' -Default ''),
            [string](Get-RerunRecoveryValue -Object $plan -Name 'nested_pipeline_local_base' -Default '')
        )) {
            if ($text -match '\.chunk_(\d+)$') {
                try { $highest = [math]::Max($highest, [int]$Matches[1]) } catch {}
            }
        }
    }
    return $highest
}

function New-RerunChunkAllocation {
    param(
        $Manifest = $null,
        [array]$Plans = @(),
        [Parameter(Mandatory)] [ValidatePattern('^[A-Za-z0-9._-]+$')] [string]$BatchId,
        [Parameter(Mandatory)] [string]$NestedRuntimeRoot,
        [Parameter(Mandatory)] [string]$ManifestRoot
    )
    $chunkIndex = (Get-RerunHighestAllocatedChunkIndex -Manifest $Manifest -Plans $Plans) + 1
    $nestedLaunchId = ("{0}.chunk_{1:D4}" -f $BatchId, $chunkIndex)
    return [pscustomobject][ordered]@{
        chunk_index = $chunkIndex
        nested_launch_id = $nestedLaunchId
        nested_pipeline_local_base = Join-Path $NestedRuntimeRoot $nestedLaunchId
        temp_config_path = Join-Path $ManifestRoot ("{0}.chunk_{1:D4}.config.psd1" -f $BatchId, $chunkIndex)
    }
}

function Copy-RerunRecoveryHistory {
    param([Parameter(Mandatory)] $From, [Parameter(Mandatory)] $To)
    foreach ($name in @(
        'timeline','transition_sequence','attempt_count','max_attempts','first_failure_at','last_failure_at',
        'next_retry_at','last_error','stage_attempt_count','stage_attempt_id','write_sequence',
        'source_content_sha256','planned_source_content_sha256','staged_source_content_sha256','source_content_sha256_algorithm','source_root'
    )) {
        $value = Get-RerunRecoveryValue -Object $From -Name $name -Default $null
        if ($null -ne $value) { Set-RerunRecoveryValue -Object $To -Name $name -Value $value }
    }
}

function Merge-RerunResumePlans {
    param(
        [array]$FreshPlans,
        [Parameter(Mandatory)] $ExistingManifest,
        [Parameter(Mandatory)] [string]$BatchScratchRoot,
        [string]$FfprobePath = ''
    )
    $existingByIndex = @{}
    foreach ($existing in @((Get-RerunRecoveryValue -Object $ExistingManifest -Name 'rows' -Default @()))) {
        $index = 0
        try { $index = [int](Get-RerunRecoveryValue -Object $existing -Name 'row_index' -Default 0) } catch {}
        $existingByIndex[$index] = $existing
    }
    $seen = [System.Collections.Generic.HashSet[int]]::new()
    $merged = [System.Collections.Generic.List[object]]::new()
    foreach ($fresh in @($FreshPlans)) {
        $index = [int](Get-RerunRecoveryValue -Object $fresh -Name 'row_index' -Default 0)
        [void]$seen.Add($index)
        if (-not $existingByIndex.ContainsKey($index)) {
            [void]$merged.Add($fresh)
            continue
        }
        $existing = $existingByIndex[$index]
        $sameSource = $false
        if (Get-Command Test-RerunSamePath -ErrorAction SilentlyContinue) {
            $sameSource = Test-RerunSamePath -Left ([string](Get-RerunRecoveryValue -Object $existing -Name 'source_path' -Default '')) -Right ([string](Get-RerunRecoveryValue -Object $fresh -Name 'source_path' -Default ''))
        } else {
            $sameSource = ([string](Get-RerunRecoveryValue -Object $existing -Name 'source_path' -Default '')).Equals([string](Get-RerunRecoveryValue -Object $fresh -Name 'source_path' -Default ''), [System.StringComparison]::OrdinalIgnoreCase)
        }
        $oldExpectedIdentity = [string](Get-RerunRecoveryValue -Object $existing -Name 'planned_source_identity_v2' -Default '')
        if ([string]::IsNullOrWhiteSpace($oldExpectedIdentity)) { $oldExpectedIdentity = [string](Get-RerunRecoveryValue -Object $existing -Name 'source_identity_v2' -Default '') }
        $newExpectedIdentity = [string](Get-RerunRecoveryValue -Object $fresh -Name 'planned_source_identity_v2' -Default '')
        if ([string]::IsNullOrWhiteSpace($newExpectedIdentity)) { $newExpectedIdentity = [string](Get-RerunRecoveryValue -Object $fresh -Name 'source_identity_v2' -Default '') }
        $oldExpectedContentSha256 = [string](Get-RerunRecoveryValue -Object $existing -Name 'planned_source_content_sha256' -Default '')
        if ([string]::IsNullOrWhiteSpace($oldExpectedContentSha256)) { $oldExpectedContentSha256 = [string](Get-RerunRecoveryValue -Object $existing -Name 'source_content_sha256' -Default '') }
        $oldExpectedContentSha256Algorithm = [string](Get-RerunRecoveryValue -Object $existing -Name 'source_content_sha256_algorithm' -Default '')
        $newExpectedContentSha256 = [string](Get-RerunRecoveryValue -Object $fresh -Name 'planned_source_content_sha256' -Default '')
        if ([string]::IsNullOrWhiteSpace($newExpectedContentSha256)) { $newExpectedContentSha256 = [string](Get-RerunRecoveryValue -Object $fresh -Name 'source_content_sha256' -Default '') }
        $newExpectedContentSha256Algorithm = [string](Get-RerunRecoveryValue -Object $fresh -Name 'source_content_sha256_algorithm' -Default '')
        $existingStatus = [string](Get-RerunRecoveryValue -Object $existing -Name 'status' -Default '')
        $existingState = [string](Get-RerunRecoveryValue -Object $existing -Name 'lifecycle_state' -Default $existingStatus)
        $existingIsTerminal = (
            $existingState -eq 'terminal' -or
            $existingStatus -in @('complete','completed','published','parked','pending_publish','published_non_overlap','published_replace_final','review_workspace','review','failed','retry_exhausted','skipped')
        )
        if (-not $existingIsTerminal -and $oldExpectedContentSha256 -notmatch '^[A-Fa-f0-9]{64}$') {
            Set-RerunPlanLifecycle -Plan $existing -State 'review' -Status 'review' -What 'Automatic resume was blocked because the accepted row has no strong identity baseline.' -Why 'The prior durable row has no valid source_content_sha256, so current bytes cannot be proven to match the pre-outage source.' -Next 'Review the source full-content identity and start a new correlated rerun.' -ReasonCode 'source_content_sha256_missing' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review full source identity before retrying.'
            [void]$merged.Add($existing)
            continue
        }
        if (-not $existingIsTerminal -and $oldExpectedContentSha256Algorithm -cne 'sha256-full-file') {
            $algorithmDisplay = if ([string]::IsNullOrWhiteSpace($oldExpectedContentSha256Algorithm)) { '(missing)' } else { $oldExpectedContentSha256Algorithm }
            Set-RerunPlanLifecycle -Plan $existing -State 'review' -Status 'review' -What 'Automatic resume was blocked because the accepted row has no authoritative strong-identity algorithm.' -Why "The prior durable row declares $algorithmDisplay instead of sha256-full-file, so current bytes cannot be proven to match the pre-outage source." -Next 'Review the source full-content identity and start a new correlated rerun.' -ReasonCode 'source_content_sha256_algorithm_invalid' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review full source identity before retrying.'
            [void]$merged.Add($existing)
            continue
        }
        if (-not $sameSource -or (
            -not [string]::IsNullOrWhiteSpace($oldExpectedIdentity) -and
            -not [string]::IsNullOrWhiteSpace($newExpectedIdentity) -and
            -not $oldExpectedIdentity.Equals($newExpectedIdentity, [System.StringComparison]::OrdinalIgnoreCase)
        ) -or (
            -not [string]::IsNullOrWhiteSpace($oldExpectedContentSha256) -and
            (
                [string]::IsNullOrWhiteSpace($newExpectedContentSha256) -or
                $newExpectedContentSha256Algorithm -cne 'sha256-full-file' -or
                -not $oldExpectedContentSha256.Equals($newExpectedContentSha256, [System.StringComparison]::OrdinalIgnoreCase)
            )
        )) {
            Set-RerunPlanLifecycle -Plan $existing -State 'review' -Status 'review' -What 'Resume was blocked because CSV identity evidence changed.' -Why 'The source path, sampled identity, or full-content SHA-256 no longer matches the accepted execution manifest.' -Next 'Review the changed CSV/source evidence and start a new correlated rerun.' -ReasonCode 'rerun_resume_csv_changed' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review the changed CSV and source identity.'
            [void]$merged.Add($existing)
            continue
        }

        $disposition = Get-RerunResumeDisposition -Plan $existing -BatchScratchRoot $BatchScratchRoot -FfprobePath $FfprobePath
        switch ([string]$disposition.Action) {
            'resume_staged' {
                Add-RerunLifecycleTransition -Target $existing -State 'staged' -What 'Verified staged scratch was accepted for resume.' -Why $disposition.Reason -Next 'Continue nested processing without re-reading the source.' -ReasonCode 'staged_scratch_verified'
                Set-RerunRecoveryValue -Object $existing -Name 'status' -Value 'staged'
                Set-RerunRecoveryValue -Object $existing -Name 'staged_source_identity_v2' -Value ([string](Get-RerunRecoveryValue -Object $existing -Name 'planned_source_identity_v2' -Default ''))
                Set-RerunRecoveryValue -Object $existing -Name 'staged_source_content_sha256' -Value ([string](Get-RerunRecoveryValue -Object $existing -Name 'planned_source_content_sha256' -Default ''))
                [void]$merged.Add($existing)
            }
            'replan' {
                $freshState = [string](Get-RerunRecoveryValue -Object $fresh -Name 'lifecycle_state' -Default ([string](Get-RerunRecoveryValue -Object $fresh -Name 'status' -Default 'accepted')))
                $freshWhat = [string](Get-RerunRecoveryValue -Object $fresh -Name 'what' -Default 'Safe resume reapplied the current planning result.')
                $freshWhy = [string](Get-RerunRecoveryValue -Object $fresh -Name 'why' -Default $disposition.Reason)
                $freshNext = [string](Get-RerunRecoveryValue -Object $fresh -Name 'next' -Default 'Follow the current source planning state before staging.')
                $freshReasonCode = [string](Get-RerunRecoveryValue -Object $fresh -Name 'reason_code' -Default 'rerun_resume_replanned')
                Copy-RerunRecoveryHistory -From $existing -To $fresh
                Add-RerunLifecycleTransition -Target $fresh -State $freshState -What $freshWhat -Why $freshWhy -Next $freshNext -ReasonCode $freshReasonCode
                [void]$merged.Add($fresh)
            }
            'restart_staging' {
                Copy-RerunRecoveryHistory -From $existing -To $fresh
                Set-RerunRecoveryValue -Object $fresh -Name 'status' -Value 'pending'
                Set-RerunRecoveryValue -Object $fresh -Name 'lifecycle_state' -Value 'pending'
                Add-RerunLifecycleTransition -Target $fresh -State 'retry_scheduled' -What 'Interrupted staging was reduced to a safe retry boundary.' -Why $disposition.Reason -Next 'Revalidate the source identity and restart the scratch copy.' -ReasonCode 'stage_copy_interrupted'
                Set-RerunRecoveryValue -Object $fresh -Name 'status' -Value 'retry_scheduled'
                [void]$merged.Add($fresh)
            }
            'terminal' {
                [void]$merged.Add($existing)
            }
            default {
                Set-RerunPlanLifecycle -Plan $existing -State 'review' -Status 'review' -What 'Automatic resume was blocked at an ambiguous boundary.' -Why $disposition.Reason -Next 'Review existing output and destination evidence before any retry.' -ReasonCode 'rerun_resume_ambiguous' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review existing work before retrying.'
                [void]$merged.Add($existing)
            }
        }
    }
    foreach ($index in $existingByIndex.Keys) {
        if ($seen.Contains([int]$index)) { continue }
        $existing = $existingByIndex[$index]
        Set-RerunPlanLifecycle -Plan $existing -State 'review' -Status 'review' -What 'Accepted row is absent from the current CSV.' -Why 'Resume cannot discard an accepted row silently.' -Next 'Review the changed CSV before starting a new rerun.' -ReasonCode 'rerun_resume_csv_changed' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review the changed CSV.'
        [void]$merged.Add($existing)
    }
    return @($merged)
}
