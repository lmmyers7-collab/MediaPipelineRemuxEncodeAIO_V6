from __future__ import annotations

import threading
from types import SimpleNamespace

from .. import APP_NAME, APP_VERSION
from mediapipeline.core.audit.facade import AuditFacadeMixin
from mediapipeline.core.completed.facade import CompletedFacadeMixin
from mediapipeline.core.completed.open_facade import CompletedOpenFacadeMixin
from mediapipeline.core.diagnostics.facade import DiagnosticsFacadeMixin
from mediapipeline.core.diagnostics.tdarr_matrix_audit_facade import DiagnosticsTdarrMatrixAuditFacadeMixin
from mediapipeline.core.failures.facade import FailureFacadeMixin
from mediapipeline.core.final_library.facade import FinalLibraryPromotionFacadeMixin
from mediapipeline.core.maintenance.backfill_facade import MaintenanceBackfillFacadeMixin
from mediapipeline.core.maintenance.commands_facade import MaintenanceCommandFacadeMixin
from mediapipeline.core.maintenance.dependency_atlas_facade import MaintenanceDependencyAtlasFacadeMixin
from mediapipeline.core.maintenance.facade import MaintenanceFacadeMixin
from mediapipeline.core.maintenance.release_facade import MaintenanceReleaseFacadeMixin
from mediapipeline.core.maintenance.retention_facade import MaintenanceRetentionFacadeMixin
from mediapipeline.core.maintenance.state_journal_archive_facade import MaintenanceStateJournalArchiveFacadeMixin
from mediapipeline.core.library.facade import LibraryRouteMapFacadeMixin
from mediapipeline.core.metrics.facade import MetricsFacadeMixin
from mediapipeline.core.network.facade import NetworkDiscoveryUnavailable, NetworkFacadeMixin
from mediapipeline.core.network.lifecycle_facade import NetworkLifecycleFacadeMixin
from mediapipeline.core.publish.pending_facade import PendingPublishFacadeMixin
from mediapipeline.core.publish.reconciliation_facade import PublishReconciliationFacadeMixin
from mediapipeline.core.repair_reconcile.facade import RepairReconcileDryRunFacadeMixin
from mediapipeline.core.processes.preflight_facade import ProcessFacadeMixin
from mediapipeline.core.processes.audit_facade import AuditLaunchFacadeMixin
from mediapipeline.core.processes.control_facade import ProcessControlFacadeMixin
from mediapipeline.core.processes.guard_facade import ProcessGuardFacadeMixin
from mediapipeline.core.processes.lifecycle_reconciliation_facade import LifecycleReconciliationFacadeMixin
from mediapipeline.core.processes.pipeline_facade import PipelineLaunchFacadeMixin
from mediapipeline.core.processes.rerun_facade import RerunLaunchFacadeMixin
from mediapipeline.core.processes.schedule_facade import ProcessScheduleFacadeMixin
from mediapipeline.core.processes.recovery import initial_recovery_status
from mediapipeline.core.queue.facade import QueueFacadeMixin
from mediapipeline.core.rename.facade import RenameFacadeMixin
from mediapipeline.core.sample_validation.facade import SampleValidationFacadeMixin
from mediapipeline.core.schedule.facade import ScheduleFacadeMixin
from mediapipeline.core.config.settings_facade import SettingsFacadeMixin
from mediapipeline.core.config.settings_helpers_facade import SettingsHelperFacadeMixin
from mediapipeline.core.config.settings_patch_candidate_facade import SettingsPatchCandidateFacadeMixin
from mediapipeline.core.config.settings_risk_facade import SettingsRiskFacadeMixin
from mediapipeline.core.config.settings_wizard_facade import SettingsWizardFacadeMixin
from mediapipeline.core.config.preset_library import PresetLibraryFacadeMixin
from mediapipeline.core.orchestration.settings_patch_facade import SettingsPatchFacadeMixin
from mediapipeline.core.status.facade import StatusFacadeMixin
from mediapipeline.core.subtitles.facade import SubtitleQaFacadeMixin
from mediapipeline.core.queue.source_inventory import queue_inventory_source_roots
from mediapipeline.core.application.utilities import FacadeUtilityMixin
from .schedule_stop_watcher import ScheduleStopWatcherManager
from ..watch import WatchContext, WatchFolderManager, watch_folder_state_mapping
from .network_lifecycle_provider import NetworkLifecycleProviderMixin
from mediapipeline.desktop.network.mdns import ZeroconfUnavailable, discover_coordinators
from mediapipeline.desktop.network.probe import probe_worker_auth
from mediapipeline.desktop.network.rerun_claims import request_network_rerun_row_retry


def _discover_network_coordinators_adapter(*, timeout_secs: float) -> list[str]:
    try:
        return discover_coordinators(timeout_secs=timeout_secs)
    except ZeroconfUnavailable as exc:
        raise NetworkDiscoveryUnavailable(str(exc)) from exc


class MediaPipelineApplicationFacade(
    FacadeUtilityMixin,
    SettingsHelperFacadeMixin,
    SettingsFacadeMixin,
    SettingsPatchCandidateFacadeMixin,
    SettingsPatchFacadeMixin,
    SettingsRiskFacadeMixin,
    SettingsWizardFacadeMixin,
    PresetLibraryFacadeMixin,
    CompletedFacadeMixin,
    CompletedOpenFacadeMixin,
    FinalLibraryPromotionFacadeMixin,
    MaintenanceFacadeMixin,
    MaintenanceCommandFacadeMixin,
    MaintenanceReleaseFacadeMixin,
    MaintenanceBackfillFacadeMixin,
    MaintenanceDependencyAtlasFacadeMixin,
    MaintenanceRetentionFacadeMixin,
    MaintenanceStateJournalArchiveFacadeMixin,
    LibraryRouteMapFacadeMixin,
    MetricsFacadeMixin,
    NetworkFacadeMixin,
    NetworkLifecycleProviderMixin,
    NetworkLifecycleFacadeMixin,
    QueueFacadeMixin,
    SubtitleQaFacadeMixin,
    FailureFacadeMixin,
    AuditFacadeMixin,
    PendingPublishFacadeMixin,
    PublishReconciliationFacadeMixin,
    RepairReconcileDryRunFacadeMixin,
    LifecycleReconciliationFacadeMixin,
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
    DiagnosticsTdarrMatrixAuditFacadeMixin,
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
        self._diagnostics_command_lock = threading.Lock()
        self._maintenance_command_lock = threading.Lock()
        self._maintenance_health_progress_lock = threading.Lock()
        self._maintenance_health_progress = {}
        self._rename_apply_lock = threading.Lock()
        self._settings_save_lock = threading.Lock()
        self._sample_validation_lock = threading.Lock()
        self._schedule_save_lock = threading.Lock()
        self._metrics_state_lock = threading.Lock()
        self._metrics_completed_history_lock = threading.RLock()
        self._audit_source_state_lock = threading.Lock()
        self._network_lifecycle_lock = threading.RLock()
        self._network_lifecycle_state = {}
        self._network_dispatcher_runtime = {}
        self._network_discover_coordinators = _discover_network_coordinators_adapter
        self._network_probe_worker_auth = probe_worker_auth
        self._schedule_stop_watcher = ScheduleStopWatcherManager()
        self._watch_folder_manager = WatchFolderManager()
        self._recovery_status = initial_recovery_status()

    def set_recovery_status(self, status: dict) -> None:
        self._recovery_status = dict(status or initial_recovery_status())

    def get_recovery_status(self) -> dict:
        return dict(self._recovery_status)

    def request_network_rerun_retry(self, resolved, request: dict):
        return request_network_rerun_row_retry(
            app=SimpleNamespace(resolved=resolved),
            batch_id=str(request.get("batch_id") or ""),
            row_key=str(request.get("row_key") or ""),
            request_id=str(request.get("request_id") or ""),
            reason=str(request.get("reason") or ""),
            confirm_retry=request.get("confirm_retry") is True,
        )

    def _start_watch_folder_manager(self, *, resolved_provider, resolved_reload=None) -> dict:
        latest_resolved = {"value": None}

        def current_resolved():
            resolved = latest_resolved.get("value")
            if resolved is not None:
                return resolved
            return resolved_provider()

        def load_settings():
            resolved = resolved_reload() if callable(resolved_reload) else resolved_provider()
            latest_resolved["value"] = resolved
            return dict(getattr(resolved, "config_data", {}) or {})

        def default_watch_roots() -> list[str]:
            return [str(root.path) for root in queue_inventory_source_roots(current_resolved())]

        def start_pipeline(request: dict) -> object:
            return self.start_pipeline_process(current_resolved(), request)

        def log(message: str) -> None:
            logger = getattr(self.service, "logger", None)
            if logger is not None and hasattr(logger, "info"):
                logger.info("%s", message)

        self._watch_folder_manager.start(
            WatchContext(
                load_settings=load_settings,
                default_watch_roots=default_watch_roots,
                start_pipeline=start_pipeline,
                log=log,
            )
        )
        return self.get_watch_folder_state()

    def _stop_watch_folder_manager(self, reason: str) -> None:
        self._watch_folder_manager.stop(reason)

    def get_watch_folder_state(self) -> dict:
        return watch_folder_state_mapping(self._watch_folder_manager)

__all__ = [
    "MediaPipelineApplicationFacade",
]
