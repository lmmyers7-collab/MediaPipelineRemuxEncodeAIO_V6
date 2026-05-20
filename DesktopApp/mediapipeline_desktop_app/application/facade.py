from __future__ import annotations

import threading

from .. import APP_NAME, APP_VERSION
from .facade_audit import AuditFacadeMixin
from .facade_completed import CompletedFacadeMixin
from .facade_completed_open import CompletedOpenFacadeMixin
from .facade_diagnostics import DiagnosticsFacadeMixin
from .facade_failures import FailureFacadeMixin
from .facade_inventory import InventoryFacadeMixin
from .facade_maintenance import MaintenanceFacadeMixin
from .facade_maintenance_backfill import MaintenanceBackfillFacadeMixin
from .facade_maintenance_commands import MaintenanceCommandFacadeMixin
from .facade_maintenance_release import MaintenanceReleaseFacadeMixin
from .facade_network import NetworkFacadeMixin
from .facade_pending_publish import PendingPublishFacadeMixin
from .facade_publish_reconciliation import PublishReconciliationFacadeMixin
from .facade_process import ProcessFacadeMixin
from .facade_process_audit import AuditLaunchFacadeMixin
from .facade_process_control import ProcessControlFacadeMixin
from .facade_process_guard import ProcessGuardFacadeMixin
from .facade_process_pipeline import PipelineLaunchFacadeMixin
from .facade_process_rerun import RerunLaunchFacadeMixin
from .facade_process_schedule import ProcessScheduleFacadeMixin
from .facade_queue import QueueFacadeMixin
from .facade_rename import RenameFacadeMixin
from .facade_sample_validation import SampleValidationFacadeMixin
from .facade_schedule import ScheduleFacadeMixin
from .facade_settings import SettingsFacadeMixin
from .facade_settings_helpers import SettingsHelperFacadeMixin
from .facade_settings_patch import SettingsPatchFacadeMixin
from .facade_settings_patch_candidate import SettingsPatchCandidateFacadeMixin
from .facade_settings_risk import SettingsRiskFacadeMixin
from .facade_status import StatusFacadeMixin
from .facade_utils import FacadeUtilityMixin
from .schedule_stop_watcher import ScheduleStopWatcherManager


class MediaPipelineApplicationFacade(
    FacadeUtilityMixin,
    SettingsHelperFacadeMixin,
    SettingsFacadeMixin,
    SettingsPatchCandidateFacadeMixin,
    SettingsPatchFacadeMixin,
    SettingsRiskFacadeMixin,
    CompletedFacadeMixin,
    CompletedOpenFacadeMixin,
    MaintenanceFacadeMixin,
    MaintenanceCommandFacadeMixin,
    MaintenanceReleaseFacadeMixin,
    MaintenanceBackfillFacadeMixin,
    NetworkFacadeMixin,
    QueueFacadeMixin,
    FailureFacadeMixin,
    AuditFacadeMixin,
    PendingPublishFacadeMixin,
    PublishReconciliationFacadeMixin,
    InventoryFacadeMixin,
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
