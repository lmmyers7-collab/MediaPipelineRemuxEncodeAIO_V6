# ==============================================================================
# ops\pipeline\engine\decide\encoder_descriptors.ps1
# ==============================================================================
# Data-first encoder descriptors. The active resolver intentionally routes only
# the existing HEVC/NVENC path, libx265 CPU fallback, H.264/NVENC primary,
# libx264 primary/fallback, AV1/NVENC primary with libaom AV1 CPU fallback,
# and explicit CPU/NVENC backend overrides through the descriptor builder.
# QSV and AMF descriptors remain dormant until their own hardware validation
# gates are complete.
# ==============================================================================

. (Join-Path $PSScriptRoot 'encoder_descriptor_catalog.ps1')
. (Join-Path $PSScriptRoot 'encoder_descriptor_selection.ps1')
. (Join-Path $PSScriptRoot 'encoder_descriptor_capabilities.ps1')
. (Join-Path $PSScriptRoot 'encoder_video_flags.ps1')
