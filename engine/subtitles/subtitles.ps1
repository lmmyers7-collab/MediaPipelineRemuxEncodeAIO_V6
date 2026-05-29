# ==============================================================================
# engine\subtitles\subtitles.ps1
# ==============================================================================
# Compatibility facade for subtitle processing. The public function names remain
# stable while implementation lives in focused subtitle module files.
#
# Dot-sourced from MediaPipeline_chatgpt.ps1. Child modules read the same
# script-scope configuration and helper functions as the previous monolith.
# ==============================================================================

$repoRootForSubtitleModules = if ($PSScriptRoot) {
    Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
} else {
    Split-Path -Parent $PSCommandPath
}
$subtitleEngineModulePaths = @{
    'Subtitles.Ass.ps1' = Join-Path $repoRootForSubtitleModules 'engine\subtitles\ass.ps1'
    'Subtitles.Common.ps1' = Join-Path $repoRootForSubtitleModules 'engine\subtitles\common.ps1'
    'Subtitles.Srt.ps1' = Join-Path $repoRootForSubtitleModules 'engine\subtitles\srt.ps1'
    'Subtitles.Tx3g.ps1' = Join-Path $repoRootForSubtitleModules 'engine\subtitles\tx3g.ps1'
    'Subtitles.Bdpgs.ps1' = Join-Path $repoRootForSubtitleModules 'engine\subtitles\bdpgs.ps1'
    'Subtitles.Builders.ps1' = Join-Path $repoRootForSubtitleModules 'engine\subtitles\builders.ps1'
}
foreach ($subtitleModule in @(
    'Subtitles.Common.ps1',
    'Subtitles.Srt.ps1',
    'Subtitles.Ass.ps1',
    'Subtitles.Tx3g.ps1',
    'Subtitles.Bdpgs.ps1',
    'Subtitles.Builders.ps1'
)) {
    $subtitleModulePath = $subtitleEngineModulePaths[$subtitleModule]
    if (-not (Test-Path -LiteralPath $subtitleModulePath)) {
        throw "Required subtitle module not found: $subtitleModulePath"
    }
    . $subtitleModulePath
}
