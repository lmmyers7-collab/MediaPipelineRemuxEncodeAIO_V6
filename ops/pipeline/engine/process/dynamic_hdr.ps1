# ==============================================================================
# ops\pipeline\engine\process\dynamic_hdr.ps1
# ==============================================================================
# Dynamic HDR tool discovery and capability probes.
#
# This module intentionally does not enforce preservation policy yet. Phase 2
# makes tool resolution observable and testable while leaving Phase 1 warn-only
# media behavior unchanged until real-media remux evidence is recorded.
# ==============================================================================

. (Join-Path $PSScriptRoot 'dynamic_hdr_tools.ps1')
. (Join-Path $PSScriptRoot 'dynamic_hdr_metadata.ps1')
. (Join-Path $PSScriptRoot 'dynamic_hdr_policy.ps1')
. (Join-Path $PSScriptRoot 'dynamic_hdr_output.ps1')
