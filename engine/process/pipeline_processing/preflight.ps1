# ==============================================================================
# engine\process\pipeline_processing\preflight.ps1
# ==============================================================================
# Structured preflight classification helpers for per-file processing.
#
# These helpers build decisions and ordered effect instructions. The caller
# remains responsible for applying counters, logs, failure-state writes, and
# completion events.
# ==============================================================================

function Add-MediaPipelinePreflightTypeName {
    param(
        [Parameter(Mandatory)] $Object,
        [Parameter(Mandatory)] [string] $TypeName
    )

    $Object.PSObject.TypeNames.Insert(0, $TypeName)
    return $Object
}

function New-MediaPipelinePreflightEffect {
    param(
        [Parameter(Mandatory)]
        [ValidateSet('skip_stat', 'retry_notice', 'register_failure', 'clear_failure_state', 'log')]
        [string] $Kind,
        [string] $SkipStat = '',
        [string] $Message = '',
        [string] $Level = 'INFO',
        $FailureRegistration = $null
    )

    return Add-MediaPipelinePreflightTypeName -TypeName 'MediaPipeline.ProcessPreflight.Effect' -Object ([pscustomobject]@{
        Kind                = [string]$Kind
        SkipStat            = [string]$SkipStat
        Message             = [string]$Message
        Level               = [string]$Level
        FailureRegistration = $FailureRegistration
    })
}

function New-MediaPipelinePreflightFailureRegistration {
    param(
        [Parameter(Mandatory)] [string] $Classification,
        [Parameter(Mandatory)] [string] $Reason,
        [Parameter(Mandatory)] [string] $Stage,
        [string] $SuggestedAction = '',
        [string] $SuggestedRename = ''
    )

    return Add-MediaPipelinePreflightTypeName -TypeName 'MediaPipeline.ProcessPreflight.FailureRegistration' -Object ([pscustomobject]@{
        Classification  = [string]$Classification
        Reason          = [string]$Reason
        Stage           = [string]$Stage
        SuggestedAction = [string]$SuggestedAction
        SuggestedRename = [string]$SuggestedRename
    })
}

function New-MediaPipelinePreflightCheckResult {
    param(
        [Parameter(Mandatory)] [string] $Name,
        [Parameter(Mandatory)] [string] $State,
        [bool] $Terminal = $false,
        [string] $Reason = '',
        [string] $ErrorCode = '',
        [hashtable] $Data = @{}
    )

    return Add-MediaPipelinePreflightTypeName -TypeName 'MediaPipeline.ProcessPreflight.CheckResult' -Object ([pscustomobject]@{
        SchemaVersion = 'process_preflight_check.v1'
        Name          = [string]$Name
        State         = [string]$State
        Terminal      = [bool]$Terminal
        Reason        = [string]$Reason
        ErrorCode     = [string]$ErrorCode
        Data          = $Data
    })
}

function New-MediaPipelineProcessPreflightDecision {
    param(
        [bool] $Terminal = $false,
        [string] $Status = 'continue',
        [bool] $Success = $false,
        [bool] $QueueTerminal = $false,
        [bool] $Retryable = $true,
        [string] $Reason = '',
        [string] $ErrorCode = '',
        [string] $EventStage = '',
        [string] $MediaType = '',
        [object[]] $Checks = @(),
        [object[]] $Effects = @(),
        $TvInfo = $null,
        [string] $SafeName = '',
        $OutputPaths = $null,
        $FailureState = $null
    )

    return Add-MediaPipelinePreflightTypeName -TypeName 'MediaPipeline.ProcessPreflight.Decision' -Object ([pscustomobject]@{
        SchemaVersion      = 'process_preflight_decision.v1'
        Terminal           = [bool]$Terminal
        ContinueProcessing = -not [bool]$Terminal
        Status             = [string]$Status
        Success            = [bool]$Success
        QueueTerminal      = [bool]$QueueTerminal
        Retryable          = [bool]$Retryable
        Reason             = [string]$Reason
        ErrorCode          = [string]$ErrorCode
        EventStage         = [string]$EventStage
        MediaType          = [string]$MediaType
        Checks             = @($Checks)
        Effects            = @($Effects)
        TvInfo             = $TvInfo
        SafeName           = [string]$SafeName
        OutputPaths        = $OutputPaths
        FailureState       = $FailureState
    })
}

function Test-MediaPipelineExtensionPreflight {
    param(
        [Parameter(Mandatory)] $File,
        [Parameter(Mandatory)] [string[]] $ValidExtensions
    )

    $extension = [string]$File.Extension
    if (-not ($ValidExtensions -contains $extension.ToLower())) {
        $check = New-MediaPipelinePreflightCheckResult -Name 'extension' -State 'bad_extension' -Terminal:$true -Reason 'Bad extension' -ErrorCode 'BAD_EXTENSION' -Data @{
            extension        = $extension
            valid_extensions = @($ValidExtensions)
        }
        return New-MediaPipelineProcessPreflightDecision `
            -Terminal:$true `
            -Status 'skipped' `
            -Success:$false `
            -QueueTerminal:$true `
            -Retryable:$false `
            -Reason 'Bad extension' `
            -ErrorCode 'BAD_EXTENSION' `
            -EventStage 'skipped' `
            -Checks @($check) `
            -Effects @(
                (New-MediaPipelinePreflightEffect -Kind 'skip_stat' -SkipStat 'BadExtension'),
                (New-MediaPipelinePreflightEffect -Kind 'log' -Message "SKIP (bad extension): $($File.Name)" -Level 'DEBUG')
            )
    }

    $check = New-MediaPipelinePreflightCheckResult -Name 'extension' -State 'passed' -Data @{
        extension = $extension
    }
    return New-MediaPipelineProcessPreflightDecision -Checks @($check)
}

function Get-MediaPipelineFailureStatePreflight {
    param(
        [Parameter(Mandatory)] $File
    )

    $failureState = Get-SourceFailureState $File
    if (-not $failureState) {
        $check = New-MediaPipelinePreflightCheckResult -Name 'failure_state' -State 'clear'
        return New-MediaPipelineProcessPreflightDecision -Checks @($check)
    }

    $stateCode = if ($failureState.PSObject.Properties['error_code'] -and $failureState.error_code) {
        Normalize-FailureCode -Code ([string]$failureState.error_code)
    } else {
        Get-MediaFailureCode -Stage ([string]$failureState.stage) -Reason ([string]$failureState.reason) -Classification ([string]$failureState.classification)
    }
    $stateClassification = [string]$failureState.classification
    $retrySuffix = ''
    if ($failureState.PSObject.Properties['retry_count'] -and $failureState.PSObject.Properties['retry_limit']) {
        try {
            $retryCount = [int]$failureState.retry_count
            $retryLimit = [int]$failureState.retry_limit
            if ($retryCount -gt 0 -and $retryLimit -gt 0) { $retrySuffix = " retry=$retryCount/$retryLimit" }
        } catch {}
    }

    $check = New-MediaPipelinePreflightCheckResult -Name 'failure_state' -State $stateClassification -Terminal:($stateClassification -eq 'permanent' -or $stateClassification -eq 'operator_required') -Reason ([string]$failureState.reason) -ErrorCode $stateCode -Data @{
        failure_state = $failureState
        retry_suffix  = $retrySuffix
    }

    if ($stateClassification -eq 'permanent' -or $stateClassification -eq 'operator_required') {
        $skipKey = if ($stateClassification -eq 'operator_required') { 'OperatorRequired' } else { 'PermanentFailure' }
        $label = if ($stateClassification -eq 'operator_required') { 'operator required' } else { 'permanent failure' }
        return New-MediaPipelineProcessPreflightDecision `
            -Terminal:$true `
            -Status 'skipped' `
            -Success:$false `
            -QueueTerminal:$true `
            -Retryable:$false `
            -Reason ([string]$failureState.reason) `
            -ErrorCode $stateCode `
            -EventStage 'skipped' `
            -Checks @($check) `
            -Effects @(
                (New-MediaPipelinePreflightEffect -Kind 'skip_stat' -SkipStat $skipKey),
                (New-MediaPipelinePreflightEffect -Kind 'log' -Message "SKIP ($label [$stateCode]${retrySuffix}: $($failureState.reason)): $($File.Name)" -Level 'ERROR')
            ) `
            -FailureState $failureState
    }

    return New-MediaPipelineProcessPreflightDecision `
        -Checks @($check) `
        -Effects @(
            (New-MediaPipelinePreflightEffect -Kind 'retry_notice'),
            (New-MediaPipelinePreflightEffect -Kind 'log' -Message "RETRY after transient failure [$stateCode]$retrySuffix ($($failureState.stage)): $($File.Name)" -Level 'WARN')
        ) `
        -FailureState $failureState
}

function Get-MediaPipelineTvParsePreflight {
    param(
        [Parameter(Mandatory)] $File,
        [bool] $IsTV = $false
    )

    if (-not $IsTV) {
        $check = New-MediaPipelinePreflightCheckResult -Name 'tv_parse' -State 'not_tv'
        return New-MediaPipelineProcessPreflightDecision -Checks @($check)
    }

    $tvInfo = Get-TVInfoFromFile $File
    if ($tvInfo -and -not $tvInfo.IsReliable) {
        $renameSuggestion = Get-TVParseRenameSuggestion -File $File -TvInfo $tvInfo
        $registration = New-MediaPipelinePreflightFailureRegistration -Classification 'permanent' -Reason ([string]$tvInfo.ParseError) -Stage 'tv-parse' -SuggestedRename $renameSuggestion
        $check = New-MediaPipelinePreflightCheckResult -Name 'tv_parse' -State 'unreliable' -Terminal:$true -Reason ([string]$tvInfo.ParseError) -ErrorCode 'TV_PARSE_UNRELIABLE' -Data @{
            tv_info           = $tvInfo
            suggested_rename  = $renameSuggestion
        }
        return New-MediaPipelineProcessPreflightDecision `
            -Terminal:$true `
            -Status 'skipped' `
            -Success:$false `
            -QueueTerminal:$true `
            -Retryable:$false `
            -Reason ([string]$tvInfo.ParseError) `
            -ErrorCode 'TV_PARSE_UNRELIABLE' `
            -EventStage 'skipped' `
            -MediaType 'tv' `
            -Checks @($check) `
            -Effects @(
                (New-MediaPipelinePreflightEffect -Kind 'register_failure' -FailureRegistration $registration),
                (New-MediaPipelinePreflightEffect -Kind 'skip_stat' -SkipStat 'AmbiguousTV'),
                (New-MediaPipelinePreflightEffect -Kind 'log' -Message "SKIP (ambiguous TV filename): $($File.Name) — $($tvInfo.ParseError)" -Level 'ERROR'),
                (New-MediaPipelinePreflightEffect -Kind 'log' -Message "  Suggested rename: $renameSuggestion" -Level 'WARN')
            ) `
            -TvInfo $tvInfo
    }

    $check = New-MediaPipelinePreflightCheckResult -Name 'tv_parse' -State 'passed' -Data @{
        tv_info = $tvInfo
    }
    return New-MediaPipelineProcessPreflightDecision -Checks @($check) -TvInfo $tvInfo
}

function Resolve-MediaPipelineTvShowNameOverridePreflight {
    param(
        [bool] $IsTV = $false,
        $TvInfo = $null
    )

    if (-not ($IsTV -and $TvInfo -and $TvInfo.IsReliable -and $TvInfo.ShowName)) {
        $check = New-MediaPipelinePreflightCheckResult -Name 'show_name_override' -State 'not_applicable'
        return New-MediaPipelineProcessPreflightDecision -Checks @($check) -TvInfo $TvInfo
    }

    $originalShowName = [string]$TvInfo.ShowName
    $override = Resolve-ShowOverrides $originalShowName
    if (-not [string]::IsNullOrWhiteSpace([string]$override.ShowName)) {
        $TvInfo.ShowName = [string]$override.ShowName
        $check = New-MediaPipelinePreflightCheckResult -Name 'show_name_override' -State 'applied' -Data @{
            original_show_name = $originalShowName
            effective_show_name = [string]$TvInfo.ShowName
        }
        return New-MediaPipelineProcessPreflightDecision `
            -Checks @($check) `
            -Effects @((New-MediaPipelinePreflightEffect -Kind 'log' -Message "SHOW NAME OVERRIDE: '$originalShowName' → '$($TvInfo.ShowName)'" -Level 'DEBUG')) `
            -TvInfo $TvInfo
    }

    $check = New-MediaPipelinePreflightCheckResult -Name 'show_name_override' -State 'unchanged' -Data @{
        original_show_name = $originalShowName
    }
    return New-MediaPipelineProcessPreflightDecision -Checks @($check) -TvInfo $TvInfo
}

function Test-MediaPipelineAlreadyProcessedPreflight {
    param(
        [Parameter(Mandatory)] $File,
        [bool] $IsTV = $false,
        $TvInfo = $null,
        $ProcessedIndex = $null,
        [string] $MediaType = '',
        [string] $LibraryProfileId = ''
    )

    $previousLibraryProfileId = Get-Variable -Name CurrentLibraryProfileId -Scope Script -ValueOnly -ErrorAction SilentlyContinue
    $script:CurrentLibraryProfileId = [string]$LibraryProfileId
    try {
        $alreadyProcessed = Already-Processed $File $IsTV $TvInfo $ProcessedIndex
    } finally {
        if ($null -ne $previousLibraryProfileId) {
            $script:CurrentLibraryProfileId = $previousLibraryProfileId
        } else {
            Remove-Variable -Name CurrentLibraryProfileId -Scope Script -ErrorAction SilentlyContinue
        }
    }

    if ($alreadyProcessed) {
        $check = New-MediaPipelinePreflightCheckResult -Name 'already_processed' -State 'already_processed' -Terminal:$true -Reason 'Already processed' -ErrorCode 'ALREADY_PROCESSED'
        return New-MediaPipelineProcessPreflightDecision `
            -Terminal:$true `
            -Status 'skipped' `
            -Success:$true `
            -QueueTerminal:$true `
            -Retryable:$false `
            -Reason 'Already processed' `
            -ErrorCode 'ALREADY_PROCESSED' `
            -EventStage 'skipped' `
            -MediaType $MediaType `
            -Checks @($check) `
            -Effects @(
                (New-MediaPipelinePreflightEffect -Kind 'skip_stat' -SkipStat 'AlreadyProcessed'),
                (New-MediaPipelinePreflightEffect -Kind 'clear_failure_state')
            ) `
            -TvInfo $TvInfo
    }

    $check = New-MediaPipelinePreflightCheckResult -Name 'already_processed' -State 'not_processed'
    return New-MediaPipelineProcessPreflightDecision -Checks @($check) -TvInfo $TvInfo
}

function Test-MediaPipelineStabilityPreflight {
    param(
        [Parameter(Mandatory)] $File,
        [string] $MediaType = ''
    )

    if (-not (Test-FileStable $File.FullName)) {
        $check = New-MediaPipelinePreflightCheckResult -Name 'source_stability' -State 'still_writing' -Terminal:$true -Reason 'File is still being written' -ErrorCode 'SOURCE_STILL_WRITING'
        return New-MediaPipelineProcessPreflightDecision `
            -Terminal:$true `
            -Status 'skipped' `
            -Success:$false `
            -QueueTerminal:$false `
            -Retryable:$true `
            -Reason 'File is still being written' `
            -ErrorCode 'SOURCE_STILL_WRITING' `
            -EventStage 'skipped' `
            -MediaType $MediaType `
            -Checks @($check) `
            -Effects @(
                (New-MediaPipelinePreflightEffect -Kind 'skip_stat' -SkipStat 'StillWriting'),
                (New-MediaPipelinePreflightEffect -Kind 'log' -Message "SKIP (file still being written): $($File.Name)" -Level 'WARN')
            )
    }

    $check = New-MediaPipelinePreflightCheckResult -Name 'source_stability' -State 'stable'
    return New-MediaPipelineProcessPreflightDecision -Checks @($check)
}

function Test-MediaPipelineOutputPathPreflight {
    param(
        [Parameter(Mandatory)] $File,
        [bool] $IsTV = $false,
        $TvInfo = $null,
        [string] $MediaType = '',
        [string] $LibraryProfileId = ''
    )

    $safeName = Get-SafeLocalName $File.Name
    $previousLibraryProfileId = Get-Variable -Name CurrentLibraryProfileId -Scope Script -ValueOnly -ErrorAction SilentlyContinue
    $script:CurrentLibraryProfileId = [string]$LibraryProfileId
    try {
        $outputPaths = Get-OutputPaths $File $IsTV $TvInfo $safeName
    } finally {
        if ($null -ne $previousLibraryProfileId) {
            $script:CurrentLibraryProfileId = $previousLibraryProfileId
        } else {
            Remove-Variable -Name CurrentLibraryProfileId -Scope Script -ErrorAction SilentlyContinue
        }
    }
    $pathCheck = Test-OutputPathCapability -Paths $outputPaths

    if (-not $pathCheck.Ok) {
        $serverOut = ''
        try { $serverOut = [string]$outputPaths.ServerOut } catch {}
        $suggestedRename = if (-not [string]::IsNullOrWhiteSpace($serverOut)) { Split-Path $serverOut -Leaf } else { '' }
        $suggestedAction = Get-FailureSuggestedAction -Stage 'path-capability' -Reason ([string]$pathCheck.Reason)
        $registration = New-MediaPipelinePreflightFailureRegistration -Classification 'permanent' -Reason ([string]$pathCheck.Reason) -Stage 'path-capability' -SuggestedAction $suggestedAction -SuggestedRename $suggestedRename
        $effects = @(
            (New-MediaPipelinePreflightEffect -Kind 'skip_stat' -SkipStat 'PathUnsupported'),
            (New-MediaPipelinePreflightEffect -Kind 'register_failure' -FailureRegistration $registration),
            (New-MediaPipelinePreflightEffect -Kind 'log' -Message "SKIP (output path unsupported): $($File.Name) — $($pathCheck.Reason)" -Level 'WARN')
        )
        if ($pathCheck.Path) {
            $effects += (New-MediaPipelinePreflightEffect -Kind 'log' -Message "  Path: $($pathCheck.Path)" -Level 'DEBUG')
        }
        $check = New-MediaPipelinePreflightCheckResult -Name 'output_path' -State 'unsupported' -Terminal:$true -Reason ([string]$pathCheck.Reason) -ErrorCode 'OUTPUT_PATH_UNSUPPORTED' -Data @{
            safe_name    = $safeName
            output_paths = $outputPaths
            path_check   = $pathCheck
        }
        return New-MediaPipelineProcessPreflightDecision `
            -Terminal:$true `
            -Status 'skipped' `
            -Success:$false `
            -QueueTerminal:$true `
            -Retryable:$false `
            -Reason ([string]$pathCheck.Reason) `
            -ErrorCode 'OUTPUT_PATH_UNSUPPORTED' `
            -EventStage 'skipped' `
            -MediaType $MediaType `
            -Checks @($check) `
            -Effects $effects `
            -SafeName $safeName `
            -OutputPaths $outputPaths
    }

    $check = New-MediaPipelinePreflightCheckResult -Name 'output_path' -State 'supported' -Data @{
        safe_name    = $safeName
        output_paths = $outputPaths
        path_check   = $pathCheck
    }
    return New-MediaPipelineProcessPreflightDecision -Checks @($check) -SafeName $safeName -OutputPaths $outputPaths
}
