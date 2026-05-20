# ==============================================================================
# Modules\Versioning.ps1
# ==============================================================================
# Central version semantics. ProductVersion is operator-facing and feeds the
# desktop/WebView sidebar label. Bump it here for normal release tracking:
#   v6.001 = minor bug fix
#   v6.010 = minor feature
#   v6.100 = major feature within the V6 line
#   v7.000 = next major product line
# Sidecar and audit versions remain compatibility/schema gates and must not be
# bumped just because the desktop release label changes.
# ==============================================================================

function Get-MediaPipelineProductVersion {
    return 'v6.000'
}

function Get-MediaPipelineSidecarVersion {
    return '1.0'
}

function Get-MediaPipelineAuditSchemaVersion {
    return '1.0'
}

function Get-MediaPipelineVersionInfo {
    return [pscustomobject]@{
        ProductVersion         = Get-MediaPipelineProductVersion
        PipelineSidecarVersion = Get-MediaPipelineSidecarVersion
        AuditSchemaVersion     = Get-MediaPipelineAuditSchemaVersion
    }
}
