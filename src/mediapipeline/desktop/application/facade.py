from __future__ import annotations

import threading

from .. import APP_NAME, APP_VERSION
from mediapipeline.core.audit.facade import AuditFacadeMixin
from mediapipeline.core.completed.facade import CompletedFacadeMixin
from mediapipeline.core.completed.open_facade import CompletedOpenFacadeMixin
from mediapipeline.core.diagnostics.facade import DiagnosticsFacadeMixin
from mediapipeline.core.failures.facade import FailureFacadeMixin
from mediapipeline.core.final_library.facade import FinalLibraryPromotionFacadeMixin
from mediapipeline.core.maintenance.backfill_facade import MaintenanceBackfillFacadeMixin
from mediapipeline.core.maintenance.commands_facade import MaintenanceCommandFacadeMixin
from mediapipeline.core.maintenance.dependency_atlas_facade import MaintenanceDependencyAtlasFacadeMixin
from mediapipeline.core.maintenance.facade import MaintenanceFacadeMixin
from mediapipeline.core.maintenance.release_facade import MaintenanceReleaseFacadeMixin
from mediapipeline.core.network.facade import NetworkFacadeMixin
from mediapipeline.core.publish.pending_facade import PendingPublishFacadeMixin
from mediapipeline.core.publish.reconciliation_facade import PublishReconciliationFacadeMixin
from mediapipeline.core.processes.preflight_facade import ProcessFacadeMixin
from mediapipeline.core.processes.audit_facade import AuditLaunchFacadeMixin
from mediapipeline.core.processes.control_facade import ProcessControlFacadeMixin
from mediapipeline.core.processes.guard_facade import ProcessGuardFacadeMixin
from mediapipeline.core.processes.pipeline_facade import PipelineLaunchFacadeMixin
from mediapipeline.core.processes.rerun_facade import RerunLaunchFacadeMixin
from mediapipeline.core.processes.schedule_facade import ProcessScheduleFacadeMixin
from mediapipeline.core.queue.facade import QueueFacadeMixin
from mediapipeline.core.rename.facade import RenameFacadeMixin
from mediapipeline.core.sample_validation.facade import SampleValidationFacadeMixin
from mediapipeline.core.schedule.facade import ScheduleFacadeMixin
from mediapipeline.core.config.settings_facade import SettingsFacadeMixin
from mediapipeline.core.config.settings_helpers_facade import SettingsHelperFacadeMixin
from mediapipeline.core.config.settings_patch_candidate_facade import SettingsPatchCandidateFacadeMixin
from mediapipeline.core.config.settings_risk_facade import SettingsRiskFacadeMixin
from mediapipeline.core.config.settings_wizard_facade import SettingsWizardFacadeMixin
from mediapipeline.core.orchestration.settings_patch_facade import SettingsPatchFacadeMixin
from mediapipeline.core.status.facade import StatusFacadeMixin
from mediapipeline.core.application.utilities import FacadeUtilityMixin
from .schedule_stop_watcher import ScheduleStopWatcherManager


class MediaPipelineApplicationFacade(
    FacadeUtilityMixin,
    SettingsHelperFacadeMixin,
    SettingsFacadeMixin,
    SettingsPatchCandidateFacadeMixin,
    SettingsPatchFacadeMixin,
    SettingsRiskFacadeMixin,
    SettingsWizardFacadeMixin,
    CompletedFacadeMixin,
    CompletedOpenFacadeMixin,
    FinalLibraryPromotionFacadeMixin,
    MaintenanceFacadeMixin,
    MaintenanceCommandFacadeMixin,
    MaintenanceReleaseFacadeMixin,
    MaintenanceBackfillFacadeMixin,
    MaintenanceDependencyAtlasFacadeMixin,
    NetworkFacadeMixin,
    QueueFacadeMixin,
    FailureFacadeMixin,
    AuditFacadeMixin,
    PendingPublishFacadeMixin,
    PublishReconciliationFacadeMixin,
    PipelineLaunchFacadeMixin,
    AuditLaunchFacadeMixin,
    RerunLaunchFacadeMixin,
    ProcessFacadeMixin,
    ProcessControlFacadeMixin,
    ProcessGuardFacadeMixin,
    ProcessScheduleFacadeMixin,
    RenameFacadeMixin,
    SampleValidationFacadeMixin,
    ScheduleFacadeMixin,
    DiagnosticsFacadeMixin,
    StatusFacadeMixin,
):
    """UI-neutral command/query boundary for current and future shells.

    This facade intentionally does not import desktop shell or view
    modules. It adapts the existing service layer into serializable DTOs that a
    future local API, Tauri/WebView2 frontend, or another desktop shell
    can consume.
    """

    def __init__(
        self,
        service: object,
        *,
        app_name: str = APP_NAME,
        app_version: str = APP_VERSION,
    ) -> None:
        self.service = service
        self.app_name = app_name
        self.app_version = app_version
        self._process_launch_lock = threading.Lock()
        self._process_control_lock = threading.Lock()
        self._maintenance_command_lock = threading.Lock()
        self._maintenance_health_progress_lock = threading.Lock()
        self._maintenance_health_progress = {}
        self._rename_apply_lock = threading.Lock()
        self._settings_save_lock = threading.Lock()
        self._sample_validation_lock = threading.Lock()
        self._schedule_save_lock = threading.Lock()
        self._schedule_stop_watcher = ScheduleStopWatcherManager()

__all__ = [
    "MediaPipelineApplicationFacade",
]
