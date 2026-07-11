# ==============================================================================
# ops\pipeline\engine\decide\encoder_descriptors.ps1
# ==============================================================================
# Data-first encoder descriptors. The active resolver intentionally routes only
# the existing HEVC/NVENC path, libx265 CPU fallback, H.264/NVENC primary,
# libx264 primary/fallback, libaom AV1 CPU primary/fallback paths, and explicit
# CPU backend overrides through the descriptor builder. Dormant descriptors may
# describe future supported pairs before route selection is allowed to activate
# them.
# ==============================================================================

. (Join-Path $PSScriptRoot 'encoder_descriptor_catalog.ps1')
. (Join-Path $PSScriptRoot 'encoder_descriptor_selection.ps1')
. (Join-Path $PSScriptRoot 'encoder_descriptor_capabilities.ps1')
. (Join-Path $PSScriptRoot 'encoder_video_flags.ps1')
