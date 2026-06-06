# ==============================================================================
# ops\pipeline\engine\config\runtime_validation.ps1
# ==============================================================================
# Runtime validation helpers and route boundary math.
# ==============================================================================

function Get-MediaPipelineRouteMaxHeightFromUpperTolerance {
    param(
        [int] $BaseHeight,
        [double] $TolerancePercent
    )

    return [int][Math]::Round([double]$BaseHeight * (1.0 + ([double]$TolerancePercent / 100.0)))
}

function Get-MediaPipelineRouteMinHeightFromLowerTolerance {
    param(
        [int] $BaseHeight,
        [double] $TolerancePercent
    )

    return [int][Math]::Round([double]$BaseHeight * (1.0 - ([double]$TolerancePercent / 100.0)))
}

function Get-MediaPipelineRouteHeightToleranceBoundaries {
    param(
        [double] $Route1080pUpperHeightTolerancePercent = 11.111111,
        [double] $Route1440pLowerHeightTolerancePercent = 16.597222,
        [double] $Route1440pUpperHeightTolerancePercent = 24.930556,
        [double] $Route4KLowerHeightTolerancePercent = 16.666667
    )

    $route1080pMaxHeight = Get-MediaPipelineRouteMaxHeightFromUpperTolerance -BaseHeight 1080 -TolerancePercent $Route1080pUpperHeightTolerancePercent
    $route1440pMinHeight = Get-MediaPipelineRouteMinHeightFromLowerTolerance -BaseHeight 1440 -TolerancePercent $Route1440pLowerHeightTolerancePercent
    $route1440pMaxHeight = Get-MediaPipelineRouteMaxHeightFromUpperTolerance -BaseHeight 1440 -TolerancePercent $Route1440pUpperHeightTolerancePercent
    $route4kMinHeight = Get-MediaPipelineRouteMinHeightFromLowerTolerance -BaseHeight 2160 -TolerancePercent $Route4KLowerHeightTolerancePercent

    return [pscustomobject]([ordered]@{
        Route1080pMaxHeight = [int]$route1080pMaxHeight
        Route1440pMinHeight = [int]$route1440pMinHeight
        Route1440pMaxHeight = [int]$route1440pMaxHeight
        Route4KMinHeight    = [int]$route4kMinHeight
        IsContiguous        = (($route1440pMinHeight -eq ($route1080pMaxHeight + 1)) -and ($route4kMinHeight -eq ($route1440pMaxHeight + 1)))
    })
}

function Invoke-MediaPipelineRuntimeConfigLogicalValidation {
    [CmdletBinding()]
    param()

    # Logical config validation
    if ([double]$MinFreeSpaceGB -le 0) {
        Add-StartupWarning "MinFreeSpaceGB ($MinFreeSpaceGB) must be > 0; using 10"
        $script:MinFreeSpaceGB = 10
    }
}
