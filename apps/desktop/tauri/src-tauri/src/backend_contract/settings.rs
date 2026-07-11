use crate::dialogs::shell_error;
use crate::http_helpers::request_backend_json;
use crate::ShellResult;

pub(super) fn validate_settings(backend_url: &str, token: &str) -> ShellResult<()> {
    let settings_raw_triage_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settingsView.rawTriage.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings raw triage split factory",
            "function createSettingsRawTriageModule",
        ),
        (
            "settings raw triage split stash",
            "window.__settingsRawTriageModule",
        ),
        ("settings raw triage rows", "function settingsRawTriageRows"),
        (
            "settings raw action plan rows",
            "function settingsRawActionPlanRows",
        ),
        (
            "settings raw action plan summary",
            "Settings raw-key action plan:",
        ),
    ] {
        if !settings_raw_triage_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings raw-triage script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_safety_locks_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settingsView.safetyLocks.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings safety locks split factory",
            "function createSettingsSafetyLocksModule",
        ),
        (
            "settings safety locks split stash",
            "window.__settingsSafetyLocksModule",
        ),
        (
            "settings safety lock rows",
            "function settingsSafetyLockRows",
        ),
        (
            "settings safety lock summary",
            "Settings safety lock review:",
        ),
    ] {
        if !settings_safety_locks_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings safety-lock script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_backend_result_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settings/backendResult.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings backend result split factory",
            "function createSettingsBackendResultModule",
        ),
        (
            "settings preview/save result rows",
            "function settingsBackendResultRows",
        ),
        (
            "settings preview/save result detail",
            "function settingsBackendResultDetailLines",
        ),
        (
            "settings preview/save result renderer",
            "function renderSettingsBackendResultFromEntries",
        ),
        (
            "settings save review current-values guard",
            "Save Settings will review the current values before writing.",
        ),
        (
            "settings save persistence boundary",
            "Save Settings is the persistence command",
        ),
        (
            "settings backend result split stash",
            "window.__settingsBackendResultModule",
        ),
    ] {
        if !settings_backend_result_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings backend-result script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_final_library_promotion_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settings/finalLibraryPromotion.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings final-library promotion split factory",
            "function createSettingsFinalLibraryPromotionModule",
        ),
        (
            "settings final-library promotion split stash",
            "window.__settingsFinalLibraryPromotionModule",
        ),
    ] {
        if !settings_final_library_promotion_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings final-library promotion script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_patch_overview_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settings/patchOverview.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings patch overview split factory",
            "function createSettingsPatchOverviewModule",
        ),
        (
            "settings handbrake preview summary renderer",
            "function renderHandbrakePreviewSummary",
        ),
        (
            "settings source-specific route preview boundary",
            "Source-specific route previews are not exposed in Settings",
        ),
    ] {
        if !settings_patch_overview_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings patch-overview script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_patch_interactions_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settings/patchInteractions.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings patch interaction split factory",
            "function createSettingsPatchInteractionsModule",
        ),
        (
            "settings patch interaction event binder",
            "function initSettingsViewEvents",
        ),
    ] {
        if !settings_patch_interactions_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings patch-interactions script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_patch_readiness_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settings/patchReadiness.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings patch readiness split factory",
            "function createSettingsPatchReadinessModule",
        ),
        (
            "settings patch readiness validator",
            "function settingsPatchSaveReadinessIssues",
        ),
    ] {
        if !settings_patch_readiness_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings patch-readiness script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_patch_review_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settings/patchReview.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings patch-review split factory",
            "function createSettingsPatchReviewModule",
        ),
        (
            "settings builder patch collector",
            "function collectSettingsBuilderPatch",
        ),
        (
            "settings builder routing profile patch key",
            "RoutingProfile: settingsBuilderInputValue(\"settings-builder-routing-profile\")",
        ),
        (
            "settings patch-review child composition",
            "const settingsPatchReadinessModule = window.__settingsPatchReadinessModule || {}",
        ),
        (
            "settings final-library promotion composition",
            "const settingsFinalLibraryPromotionModule = window.__settingsFinalLibraryPromotionModule || {}",
        ),
        (
            "settings patch-overview composition",
            "const settingsPatchOverviewModule = window.__settingsPatchOverviewModule || {}",
        ),
        (
            "settings patch-interactions composition",
            "const settingsPatchInteractionsModule = window.__settingsPatchInteractionsModule || {}",
        ),
    ] {
        if !settings_patch_review_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings patch-review script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_metadata_script =
        request_backend_json(backend_url, "GET", "/assets/settingsMetadata.js", token, "")?;
    for (label, fragment) in [(
        "settings video detail output container field",
        "[\"OutputContainer\", \"settings-builder-output-container\", \"select\"]",
    )] {
        if !settings_metadata_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings metadata script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_video_builder_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settingsView.builders.video.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings video detail patch collector",
            "function collectVideoDetailSettingsBuilderPatch",
        ),
        (
            "settings video detail output container control",
            "setVideoDetailBuilderControl(\"settings-builder-output-container\", \"OutputContainer\", \"select\", \"mkv\")",
        ),
        (
            "settings video detail patch assignment",
            "patch[key] = readVideoDetailBuilderValue(id, kind, field?.label || key)",
        ),
    ] {
        if !settings_video_builder_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings video builder script is missing required fragment '{label}'."
            )));
        }
    }
    let mut settings_view_bundle = String::new();
    for asset_path in [
        "/assets/settings/view/builder.js",
        "/assets/settings/view/impact.js",
        "/assets/settings/view/review.js",
        "/assets/settings/view/commands.js",
        "/assets/settings/view/lifecycle.js",
        "/assets/settings/view/facade.js",
    ] {
        settings_view_bundle.push_str(&request_backend_json(
            backend_url,
            "GET",
            asset_path,
            token,
            "",
        )?);
        settings_view_bundle.push('\n');
    }
    let settings_script =
        request_backend_json(backend_url, "GET", "/assets/settingsView.js", token, "")?;
    settings_view_bundle.push_str(&settings_script);
    for (label, fragment) in [
        (
            "settings raw triage child bridge",
            "const settingsRawTriageModule = window.__settingsRawTriageModule || {}",
        ),
        (
            "settings safety locks child bridge",
            "const settingsSafetyLocksModule = window.__settingsSafetyLocksModule || {}",
        ),
        (
            "settings backend result child bridge",
            "const settingsBackendResultModule = window.__settingsBackendResultModule || {}",
        ),
        (
            "settings policy impact child bridge",
            "const settingsPolicyImpactModule = window.__settingsPolicyImpactModule || {}",
        ),
        (
            "settings policy impact child cleanup",
            "delete window.__settingsPolicyImpactModule",
        ),
        (
            "settings view facade split factory",
            "function createSettingsViewFacade",
        ),
        (
            "settings view parent composition",
            "settingsViewFacadeFactory.createSettingsViewFacade",
        ),
    ] {
        if !settings_view_bundle.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_media_projection_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settings/policyImpact/mediaProjection.js",
        token,
        "",
    )?;
    let settings_effective_policy_view_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settings/policyImpact/effectivePolicyView.js",
        token,
        "",
    )?;
    let settings_policy_impact_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settings/policyImpact.js",
        token,
        "",
    )?;
    let settings_policy_impact_bundle = format!(
        "{settings_media_projection_script}\n{settings_effective_policy_view_script}\n{settings_policy_impact_script}"
    );
    for (label, fragment) in [
        (
            "settings media projection split factory",
            "function createSettingsMediaProjection",
        ),
        (
            "settings effective policy view split factory",
            "function createSettingsEffectivePolicyView",
        ),
        (
            "settings policy impact split factory",
            "function createSettingsPolicyImpactModule",
        ),
        (
            "settings policy impact split stash",
            "window.__settingsPolicyImpactModule",
        ),
        (
            "settings backend readiness reader",
            "function settingsBackendMediaPolicyReadiness",
        ),
        (
            "settings backend readiness renderer",
            "function renderSettingsBackendMediaPolicyReadiness",
        ),
        (
            "settings backend readiness heading",
            "Backend media-policy readiness:",
        ),
        ("settings backend readiness guardrail", "this table cannot stage settings, save config, launch work, run FFmpeg, publish files, or touch source media"),
        ("settings staged policy delta rows", "function settingsPolicyDeltaRows"),
        ("settings save-candidate policy delta summary", "Save-candidate media-policy delta:"),
        (
            "settings effective policy trust rows",
            "function settingsEffectivePolicyRows",
        ),
        (
            "settings effective policy trust summary",
            "Effective policy trust summary:",
        ),
        (
            "settings effective policy launch-active boundary",
            "Launch-active policy is the saved backend config",
        ),
    ] {
        if !settings_policy_impact_bundle.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings policy-impact script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_overview_script =
        request_backend_json(backend_url, "GET", "/assets/settingsOverview.js", token, "")?;
    for (label, fragment) in [
        (
            "settings trust readiness line",
            "function settingsMediaPolicyReadinessLine",
        ),
        (
            "settings trust readiness payload",
            "settings.media_policy_readiness",
        ),
    ] {
        if !settings_overview_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings overview script is missing required fragment '{label}'."
            )));
        }
    }
    Ok(())
}
