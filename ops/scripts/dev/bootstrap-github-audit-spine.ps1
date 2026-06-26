param(
    [switch]$Apply,
    [string]$Repository = "",
    [string]$LabelsPath = ".github/audit-labels.json"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location -LiteralPath $RepoRoot

if (-not [System.IO.Path]::IsPathRooted($LabelsPath)) {
    $LabelsPath = Join-Path $RepoRoot $LabelsPath
}

if (-not (Test-Path -LiteralPath $LabelsPath)) {
    throw "Label definition file not found: $LabelsPath"
}

$Labels = Get-Content -LiteralPath $LabelsPath -Raw | ConvertFrom-Json
if (-not $Labels -or $Labels.Count -eq 0) {
    throw "No labels found in $LabelsPath"
}

if ([string]::IsNullOrWhiteSpace($Repository)) {
    $origin = (& git remote get-url origin 2>$null)
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($origin)) {
        if ($origin -match "github\.com[:/](?<owner>[^/]+)/(?<repo>[^/]+?)(?:\.git)?$") {
            $Repository = "$($Matches.owner)/$($Matches.repo)"
        }
    }
}

if ($Apply -and [string]::IsNullOrWhiteSpace($Repository)) {
    throw "No GitHub repository was provided and no origin remote could be resolved. Pass -Repository owner/repo."
}

if ($Apply -and -not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI 'gh' is required for -Apply."
}

if ($Apply) {
    Write-Host "Applying audit labels to $Repository"
} else {
    Write-Host "Dry run. Re-run with -Apply after gh is authenticated and the GitHub remote exists."
    if ([string]::IsNullOrWhiteSpace($Repository)) {
        Write-Host "No repository resolved; dry-run commands will use owner/repo as a placeholder."
        $Repository = "owner/repo"
    }
}

foreach ($Label in $Labels) {
    $name = [string]$Label.name
    $color = [string]$Label.color
    $description = [string]$Label.description

    if ([string]::IsNullOrWhiteSpace($name) -or [string]::IsNullOrWhiteSpace($color)) {
        throw "Every label requires non-empty name and color fields."
    }

    $args = @(
        "label",
        "create",
        $name,
        "--repo",
        $Repository,
        "--color",
        $color,
        "--description",
        $description,
        "--force"
    )

    if ($Apply) {
        & gh @args
        if ($LASTEXITCODE -ne 0) {
            throw "gh label create failed for '$name'."
        }
    } else {
        Write-Host ("gh " + ($args -join " "))
    }
}

Write-Host "Label bootstrap complete."
Write-Host "Create the GitHub Project view manually from .github/GITHUB_AUDIT_BOOTSTRAP.md when needed."
