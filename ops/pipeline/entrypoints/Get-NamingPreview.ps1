[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$InputJsonPath,
    [Parameter(Mandatory)] [string]$OutputJsonPath
)

$ErrorActionPreference = 'Stop'

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] $Payload
    )
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $tmp = Join-Path $dir ('.' + (Split-Path -Leaf $Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $Payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmp -Encoding UTF8 -Force
        if (Test-Path -LiteralPath $Path) {
            [System.IO.File]::Replace($tmp, $Path, $null)
        } else {
            [System.IO.File]::Move($tmp, $Path)
        }
    } finally {
        if (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
    }
}

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    Write-Verbose "[$Level] $Message"
}

function Test-JsonObject {
    param($Value)

    if ($null -eq $Value) { return $false }
    if ($Value -is [System.Collections.IDictionary]) { return $true }
    return $Value.GetType().FullName -eq 'System.Management.Automation.PSCustomObject'
}

function Get-RequiredJsonProperty {
    param(
        [Parameter(Mandatory)] $Object,
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Context
    )

    if (-not (Test-JsonObject $Object)) {
        throw "$Context must be a JSON object."
    }
    if ($Object -is [System.Collections.IDictionary]) {
        if (-not $Object.Contains($Name)) { throw "$Context.$Name is required." }
        $value = $Object[$Name]
        if ($value -is [System.Array]) { return ,$value }
        return $value
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { throw "$Context.$Name is required." }
    if ($property.Value -is [System.Array]) { return ,$property.Value }
    return $property.Value
}

function Assert-JsonBooleanMap {
    param(
        [Parameter(Mandatory)] $Value,
        [Parameter(Mandatory)] [string]$Context
    )

    if (-not (Test-JsonObject $Value)) { throw "$Context must be a JSON object." }
    foreach ($property in @($Value.PSObject.Properties)) {
        if ($property.Value -isnot [bool]) {
            throw "$Context.$($property.Name) must be a boolean."
        }
    }
}

function Assert-JsonTermMap {
    param(
        [Parameter(Mandatory)] $Value,
        [Parameter(Mandatory)] [string]$Context
    )

    if (-not (Test-JsonObject $Value)) { throw "$Context must be a JSON object." }
    foreach ($property in @($Value.PSObject.Properties)) {
        Assert-JsonStringArray -Value $property.Value -Context "$Context.$($property.Name)"
    }
}

function Assert-JsonStringArray {
    param(
        $Value,
        [Parameter(Mandatory)] [string]$Context
    )

    if ($Value -is [string] -or $Value -isnot [System.Collections.IEnumerable] -or (Test-JsonObject $Value)) {
        throw "$Context must be a JSON array of strings."
    }
    foreach ($item in @($Value)) {
        if ($item -isnot [string]) { throw "$Context must contain only strings." }
    }
}

function Set-NamingPreviewCleaningPolicy {
    param([Parameter(Mandatory)] $Policy)

    $policySchema = [string](Get-RequiredJsonProperty -Object $Policy -Name 'schema_version' -Context 'rename_cleaning_policy')
    if ($policySchema -ne 'rename_cleaning_policy.v1') {
        throw "Unsupported rename cleaning policy schema: $policySchema"
    }
    $policyFingerprint = [string](Get-RequiredJsonProperty -Object $Policy -Name 'policy_fingerprint' -Context 'rename_cleaning_policy')
    if ($policyFingerprint -notmatch '^[0-9A-Fa-f]{64}$') {
        throw 'rename_cleaning_policy.policy_fingerprint must be a 64-character SHA-256 hex digest.'
    }

    $movie = Get-RequiredJsonProperty -Object $Policy -Name 'movie' -Context 'rename_cleaning_policy'
    $tv = Get-RequiredJsonProperty -Object $Policy -Name 'tv' -Context 'rename_cleaning_policy'
    $movieOptions = Get-RequiredJsonProperty -Object $movie -Name 'options' -Context 'rename_cleaning_policy.movie'
    $movieTerms = Get-RequiredJsonProperty -Object $movie -Name 'terms' -Context 'rename_cleaning_policy.movie'
    $movieRemoveTerms = Get-RequiredJsonProperty -Object $movie -Name 'remove_terms' -Context 'rename_cleaning_policy.movie'
    $tvOptions = Get-RequiredJsonProperty -Object $tv -Name 'options' -Context 'rename_cleaning_policy.tv'
    $tvTerms = Get-RequiredJsonProperty -Object $tv -Name 'terms' -Context 'rename_cleaning_policy.tv'
    $tvRemoveTerms = Get-RequiredJsonProperty -Object $tv -Name 'remove_terms' -Context 'rename_cleaning_policy.tv'

    Assert-JsonBooleanMap -Value $movieOptions -Context 'rename_cleaning_policy.movie.options'
    Assert-JsonTermMap -Value $movieTerms -Context 'rename_cleaning_policy.movie.terms'
    Assert-JsonStringArray -Value $movieRemoveTerms -Context 'rename_cleaning_policy.movie.remove_terms'
    Assert-JsonBooleanMap -Value $tvOptions -Context 'rename_cleaning_policy.tv.options'
    Assert-JsonTermMap -Value $tvTerms -Context 'rename_cleaning_policy.tv.terms'
    Assert-JsonStringArray -Value $tvRemoveTerms -Context 'rename_cleaning_policy.tv.remove_terms'

    # The preview boundary accepts only the six documented nested policy
    # values. Compatibility aliases or unrelated payload properties never
    # become script variables.
    $script:RenameMovieFilterOptions = $movieOptions
    $script:RenameMovieFilterTerms = $movieTerms
    $script:RenameMovieRemoveTerms = @($movieRemoveTerms)
    $script:RenameTVFilterOptions = $tvOptions
    $script:RenameTVFilterTerms = $tvTerms
    $script:RenameTVRemoveTerms = @($tvRemoveTerms)

    return $policyFingerprint
}

$script:PriorityMarkers = @('!')
$script:AggressiveEpisodeParsing = $true
$script:ValidExtensions = @('.mkv','.mp4','.m4v','.avi','.mov','.ts','.m2ts','.webm')
$CreateTVSubfolder = $true

$pipelineRoot = Split-Path -Parent $PSScriptRoot
$queuePlanModule = Join-Path $pipelineRoot 'engine\queue\queue_plan.ps1'
$namingModule = Join-Path $pipelineRoot 'engine\naming\naming.ps1'
if (-not (Test-Path -LiteralPath $queuePlanModule)) { throw "QueuePlan module not found: $queuePlanModule" }
if (-not (Test-Path -LiteralPath $namingModule)) { throw "Naming module not found: $namingModule" }
. $queuePlanModule
. $namingModule

$payload = Get-Content -LiteralPath $InputJsonPath -Raw | ConvertFrom-Json -ErrorAction Stop
$requestSchema = [string](Get-RequiredJsonProperty -Object $payload -Name 'schema_version' -Context 'naming preview request')
$responseSchema = ''
$appliedPolicyFingerprint = ''
switch ($requestSchema) {
    'naming_preview_request.v1' {
        $responseSchema = 'naming_preview.v1'
    }
    'naming_preview_request.v2' {
        $responseSchema = 'naming_preview.v2'
        $policy = Get-RequiredJsonProperty -Object $payload -Name 'rename_cleaning_policy' -Context 'naming preview request'
        $appliedPolicyFingerprint = Set-NamingPreviewCleaningPolicy -Policy $policy
    }
    default {
        throw "Unsupported naming preview request schema: $requestSchema"
    }
}
$rows = [System.Collections.Generic.List[object]]::new()

foreach ($item in @($payload.items)) {
    $sourcePath = [string]$item.path
    $originalName = [string]$item.original_name
    if ([string]::IsNullOrWhiteSpace($originalName) -and -not [string]::IsNullOrWhiteSpace($sourcePath)) {
        $originalName = Split-Path -Leaf $sourcePath
    }
    $extension = [string]$item.extension
    if ([string]::IsNullOrWhiteSpace($extension) -and -not [string]::IsNullOrWhiteSpace($originalName)) {
        $extension = [System.IO.Path]::GetExtension($originalName)
    }
    $mediaKind = ([string]$item.media_kind).Trim()
    if ([string]::IsNullOrWhiteSpace($mediaKind)) { $mediaKind = 'Movie' }

    try {
        $parsedIdentity = $null
        if ($mediaKind -eq 'Movie') {
            $plan = New-PlexMovieDestinationPlan -OriginalName $originalName -Extension $extension
            if ($requestSchema -eq 'naming_preview_request.v2') {
                $movieTitle = [string]$plan.MovieTitle
                $title = $movieTitle
                $year = $null
                $movieMatch = [regex]::Match($movieTitle, '^\s*(?<title>.+?)\s+\((?<year>(?:18|19|20|21)\d{2})\)\s*$')
                if ($movieMatch.Success) {
                    $title = $movieMatch.Groups['title'].Value.Trim()
                    $year = [int]$movieMatch.Groups['year'].Value
                }
                $parsedIdentity = [ordered]@{
                    media_kind = 'Movie'
                    movie_title = $movieTitle
                    title = $title
                    year = $year
                    identity_key = [string]$plan.IdentityKey
                }
            }
        } elseif ($mediaKind -eq 'TV') {
            $file = $null
            if (-not [string]::IsNullOrWhiteSpace($sourcePath) -and (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
                $file = Get-Item -LiteralPath $sourcePath -ErrorAction Stop
            } else {
                $directoryName = if (-not [string]::IsNullOrWhiteSpace($sourcePath)) {
                    [System.IO.Path]::GetDirectoryName($sourcePath)
                } else {
                    [System.IO.Path]::GetTempPath()
                }
                if ([string]::IsNullOrWhiteSpace($directoryName)) { $directoryName = [System.IO.Path]::GetTempPath() }
                $file = [pscustomobject]@{
                    Name          = $originalName
                    FullName      = if ($sourcePath) { $sourcePath } else { Join-Path $directoryName $originalName }
                    DirectoryName = $directoryName
                    Extension     = $extension
                }
            }
            $tvInfo = Get-TVInfoFromFile $file
            if (-not $tvInfo.IsReliable) {
                throw $tvInfo.ParseError
            }
            $plan = New-PlexDestinationPlan -MediaKind TV -File $file -TvInfo $tvInfo -OriginalName $originalName -Extension $extension
            if ($requestSchema -eq 'naming_preview_request.v2') {
                $episodeEnd = $plan.EpisodeEnd
                $parsedIdentity = [ordered]@{
                    media_kind = 'TV'
                    show = [string]$plan.ShowTitle
                    show_name = [string]$plan.ShowTitle
                    season = [int]$plan.SeasonNumber
                    episode_start = [int]$plan.EpisodeNumber
                    episode = [int]$plan.EpisodeNumber
                    episode_end = if ($null -eq $episodeEnd) { $null } else { [int]$episodeEnd }
                    episode_title = [string]$plan.EpisodeTitle
                    revision = if ($null -eq $tvInfo.Revision) { $null } else { [int]$tvInfo.Revision }
                    parse_mode = [string]$plan.ParseMode
                    reliable = [bool]$tvInfo.IsReliable
                    parse_error = [string]$tvInfo.ParseError
                    identity_key = [string]$plan.IdentityKey
                }
            }
        } else {
            throw "Unsupported naming preview media kind: $mediaKind"
        }
        $successRow = [ordered]@{
            ok = $true
            source_path = $sourcePath
            original_name = $originalName
            media_kind = $mediaKind
            file_base_name = [string]$plan.FileBaseName
            file_name = [string]$plan.FileName
            relative_directory = [string]$plan.RelativeDirectory
            relative_path = [string]$plan.RelativePath
            identity_key = [string]$plan.IdentityKey
            error = ''
        }
        if ($requestSchema -eq 'naming_preview_request.v2') {
            $successRow['parsed_identity'] = $parsedIdentity
        }
        $rows.Add([pscustomobject]$successRow)
    } catch {
        $rows.Add([pscustomobject]@{
            ok = $false
            source_path = $sourcePath
            original_name = $originalName
            media_kind = $mediaKind
            file_base_name = ''
            file_name = ''
            relative_directory = ''
            relative_path = ''
            identity_key = ''
            error = [string]$_.Exception.Message
        })
    }
}

$responsePayload = [ordered]@{
    schema_version = $responseSchema
    rows = @($rows)
}
if ($requestSchema -eq 'naming_preview_request.v2') {
    $responsePayload['applied_policy_fingerprint'] = $appliedPolicyFingerprint
}
Write-JsonAtomic -Path $OutputJsonPath -Payload $responsePayload
