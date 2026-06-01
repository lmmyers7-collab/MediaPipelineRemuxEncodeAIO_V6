from __future__ import annotations

import threading

from .. import APP_NAME, APP_VERSION
from app.audit.facade import AuditFacadeMixin
from app.completed.facade import CompletedFacadeMixin
from app.completed.open_facade import CompletedOpenFacadeMixin
from app.diagnostics.facade import DiagnosticsFacadeMixin
from app.failures.facade import FailureFacadeMixin
from app.final_library.facade import FinalLibraryPromotionFacadeMixin
from app.maintenance.backfill_facade import MaintenanceBackfillFacadeMixin
from app.maintenance.commands_facade import MaintenanceCommandFacadeMixin
from app.maintenance.dependency_atlas_facade import MaintenanceDependencyAtlasFacadeMixin
from app.maintenance.facade import MaintenanceFacadeMixin
from app.maintenance.release_facade import MaintenanceReleaseFacadeMixin
from app.network.facade import NetworkFacadeMixin
from app.publish.pending_facade import PendingPublishFacadeMixin
from app.publish.reconciliation_facade import PublishReconciliationFacadeMixin
from app.processes.preflight_facade import ProcessFacadeMixin
from app.processes.audit_facade import AuditLaunchFacadeMixin
from app.processes.control_facade import ProcessControlFacadeMixin
from app.processes.guard_facade import ProcessGuardFacadeMixin
from app.processes.pipeline_facade import PipelineLaunchFacadeMixin
from app.processes.rerun_facade import RerunLaunchFacadeMixin
from app.processes.schedule_facade import ProcessScheduleFacadeMixin
from app.queue.facade import QueueFacadeMixin
from app.rename.facade import RenameFacadeMixin
from app.sample_validation.facade import SampleValidationFacadeMixin
from app.schedule.facade import ScheduleFacadeMixin
from app.config.settings_facade import SettingsFacadeMixin
from app.config.settings_helpers_facade import SettingsHelperFacadeMixin
from app.config.settings_patch_candidate_facade import SettingsPatchCandidateFacadeMixin
from app.config.settings_risk_facade import SettingsRiskFacadeMixin
from app.config.settings_wizard_facade import SettingsWizardFacadeMixin
from app.orchestration.settings_patch_facade import SettingsPatchFacadeMixin
from app.status.facade import StatusFacadeMixin
from app.application.utilities import FacadeUtilityMixin
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
