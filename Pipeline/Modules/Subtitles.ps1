# ==============================================================================
# Modules\Subtitles.ps1
# ==============================================================================
# Compatibility facade for subtitle processing. The public function names remain
# stable while implementation lives in focused Modules\Subtitles.*.ps1 files.
#
# Dot-sourced from MediaPipeline_chatgpt.ps1. Child modules read the same
# script-scope configuration and helper functions as the previous monolith.
# ==============================================================================

$subtitleModuleRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $PSCommandPath }
foreach ($subtitleModule in @(
    'Subtitles.Common.ps1',
    'Subtitles.Srt.ps1',
    'Subtitles.Ass.ps1',
    'Subtitles.Tx3g.ps1',
    'Subtitles.Bdpgs.ps1',
    'Subtitles.Builders.ps1'
)) {
    $subtitleModulePath = Join-Path $subtitleModuleRoot $subtitleModule
    if (-not (Test-Path -LiteralPath $subtitleModulePath)) {
        throw "Required subtitle module not found: $subtitleModulePath"
    }
    . $subtitleModulePath
}