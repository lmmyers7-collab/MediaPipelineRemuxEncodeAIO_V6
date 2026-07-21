from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import threading
from pathlib import Path
from typing import Callable

from .models import CompletedJobRecord, TelemetrySnapshot
from mediapipeline.tools.paths import find_repo_root
from mediapipeline.core.storage.constants import APP_STATE_NAME
from mediapipeline.core.schedule.app_state import AppStateScheduleServiceMixin
from mediapipeline.core.audit.rerun_service import AuditRerunServiceMixin
from mediapipeline.core.audit.sources import AuditSourceMetricsServiceMixin
from mediapipeline.core.config.service import ConfigProfileServiceMixin
from mediapipeline.core.completed.service import CompletedJobsServiceMixin
from mediapipeline.core.files.opening import FileOpenServiceMixin
from mediapipeline.core.failures.cleanup_service import FailureCleanupServiceMixin
from mediapipeline.core.final_library.service import FinalLibraryPromotionServiceMixin
from mediapipeline.core.folder_policy.service import FolderPolicyServiceMixin
from mediapipeline.core.maintenance.productization import (
    prepare_product_runtime,
    product_runtime_roots,
    productized_app_enabled,
)
from mediapipeline.core.publish.pending_service import PendingPublishServiceMixin
from mediapipeline.core.paths.service import PathResolutionServiceMixin
from mediapipeline.core.processes.lifecycle import ProcessLifecycleServiceMixin
from mediapipeline.core.queue.remux_pilot_auto_service import RemuxPilotAutoPromotionServiceMixin
from mediapipeline.core.queue.service import QueueServiceMixin
from mediapipeline.core.maintenance.dependency_atlas import DependencyAtlasServiceMixin
from mediapipeline.core.maintenance.release import ReleasePackageServiceMixin
from mediapipeline.core.diagnostics.tdarr_matrix_audit import TdarrMatrixAuditServiceMixin
from mediapipeline.core.rename.service import RenameServiceMixin
from mediapipeline.core.status.service import StatusServiceMixin
from mediapipeline.core.telemetry.service import TelemetryServiceMixin


LOG_NAME = "MediaPipelineRemuxEncodeAIO_DesktopApp.log"
DESKTOP_LOG_MAX_BYTES = 50 * 1024 * 1024
DESKTOP_LOG_BACKUP_COUNT = 3
ACTIVE_JOB_RECONCILIATION_INTERVAL_SECONDS = 15.0


class DesktopAppService(
    PathResolutionServiceMixin,
    RemuxPilotAutoPromotionServiceMixin,
    TelemetryServiceMixin,
    StatusServiceMixin,
    AuditSourceMetricsServiceMixin,
    ProcessLifecycleServiceMixin,
    AppStateScheduleServiceMixin,
    ReleasePackageServiceMixin,
    DependencyAtlasServiceMixin,
    TdarrMatrixAuditServiceMixin,
    PendingPublishServiceMixin,
    AuditRerunServiceMixin,
    QueueServiceMixin,
    ConfigProfileServiceMixin,
    CompletedJobsServiceMixin,
    FinalLibraryPromotionServiceMixin,
    FileOpenServiceMixin,
    FailureCleanupServiceMixin,
    FolderPolicyServiceMixin,
    RenameServiceMixin,
):
    def __init__(self, app_root: Path) -> None:
        self.app_root = app_root
        try:
            self.workspace_root = find_repo_root(app_root)
        except RuntimeError:
            if app_root.name.casefold() == "desktop" and app_root.parent.name.casefold() == "apps":
                self.workspace_root = app_root.parent.parent
            else:
                self.workspace_root = app_root.parent
        self.product_runtime_roots = product_runtime_roots(create=productized_app_enabled())
        if productized_app_enabled() and self.product_runtime_roots is not None:
            prepare_product_runtime(app_root, self.workspace_root)
        self.desktop_log_path = (
            self.product_runtime_roots["logs_root"] / LOG_NAME
            if productized_app_enabled() and self.product_runtime_roots is not None
            else app_root / LOG_NAME
        )
        self.command_journal_path = (
            self.product_runtime_roots["run_logs_root"] / "local_api_command_history.json"
            if productized_app_enabled() and self.product_runtime_roots is not None
            else app_root / "RunLogs" / "local_api_command_history.json"
        )
        self.run_logs_root = self.command_journal_path.parent
        self.app_state_path = (
            self.product_runtime_roots["state_root"] / "App" / APP_STATE_NAME
            if productized_app_enabled() and self.product_runtime_roots is not None
            else app_root / APP_STATE_NAME
        )
        self._nvidia_smi_path: str | None = None
        self._nvidia_smi_checked = False
        self._vlc_path: Path | None = None
        self._vlc_checked = False
        self._telemetry_lock = threading.Lock()
        self._telemetry_stop = threading.Event()
        self._telemetry_thread: threading.Thread | None = None
        self._cached_telemetry = TelemetrySnapshot()
        self._completed_history_cache_key: str | None = None
        self._completed_history_cache_limit_key = ""
        self._completed_history_cached_at = 0.0
        self._completed_history_manifest_mtime: float = 0.0
        self._completed_history_records: list[CompletedJobRecord] = []
        # Sentinel observed by the UI "no entries found" status:
        #   -2 = read from local manifest (current implementation)
        #   -1 = SMB scan via pwsh (legacy)
        #   >=0 = os.walk dirs visited (legacy)
        self._completed_scan_dirs_visited: int = -2
        self._completed_scan_sidecars_found: int = 0
        # Number of source files excluded from the last build_queue_preview
        # call because they appeared in the completed-jobs manifest.
        self._queue_completed_excluded: int = 0
        self._queue_source_candidates: int = 0
        self._queue_completed_size_mismatches: int = 0
        self._queue_completed_identity_mismatches: int = 0
        self._queue_completed_unverified: int = 0
        self._queue_scan_limited: bool = False
        self._queue_completed_cache_status: str = "Completed cache: not checked"
        self._queue_dry_run_cleanup_warnings: list[str] = []
        self._last_spawn_stdout_log: Path | None = None
        self._last_spawn_stderr_log: Path | None = None
        self._active_spawned_processes_lock = threading.Lock()
        self._active_spawned_processes: dict[int, tuple[object, str]] = {}
        self._pending_lifecycle_lease_lock = threading.Lock()
        self._pending_lifecycle_lease: object | None = None
        self._active_job_reconciliation_provider = None
        self._process_terminal_command_evidence_recorder: Callable[..., None] | None = None
        self._active_job_reconciliation_stop = threading.Event()
        self._active_job_reconciliation_thread: threading.Thread | None = None
        self.logger = self._create_logger()
        self._initialize_remux_pilot_auto_promotion()
        self._initialize_telemetry_sampler()

    def configure_active_job_reconciliation(self, resolved_provider) -> None:
        self._active_job_reconciliation_provider = resolved_provider

    def configure_process_terminal_command_evidence(self, recorder: Callable[..., None]) -> None:
        self._process_terminal_command_evidence_recorder = recorder

    def record_process_terminal_command_evidence(
        self,
        *,
        command_id: str,
        phase: str,
        return_code: int | None,
        pid: int,
        mode: str,
    ) -> None:
        recorder = self._process_terminal_command_evidence_recorder
        if recorder is None:
            return
        recorder(
            command_id=command_id,
            phase=phase,
            return_code=return_code,
            pid=pid,
            mode=mode,
        )

    def start_background_tasks(self) -> None:
        super().start_background_tasks()
        if self._active_job_reconciliation_thread and self._active_job_reconciliation_thread.is_alive():
            return
        self._active_job_reconciliation_stop.clear()
        self._active_job_reconciliation_thread = threading.Thread(
            target=self._active_job_reconciliation_loop,
            name="MediaPipelineActiveJobReconciliation",
            daemon=True,
        )
        self._active_job_reconciliation_thread.start()

    def stop_background_tasks(self) -> None:
        self._active_job_reconciliation_stop.set()
        thread = self._active_job_reconciliation_thread
        if thread and thread.is_alive():
            thread.join(timeout=1.5)
        self._active_job_reconciliation_thread = None
        super().stop_background_tasks()

    def _active_job_reconciliation_loop(self) -> None:
        while not self._active_job_reconciliation_stop.is_set():
            provider = self._active_job_reconciliation_provider
            try:
                resolved = provider() if callable(provider) else None
                if resolved is not None:
                    self.reconcile_active_job_records(resolved)
            except Exception as exc:
                self.logger.warning("ActiveJobs background reconciliation failed: %s", exc)
            self._active_job_reconciliation_stop.wait(ACTIVE_JOB_RECONCILIATION_INTERVAL_SECONDS)

    def _create_logger(self) -> logging.Logger:
        logger = logging.getLogger("mediapipeline.desktop")
        if logger.handlers:
            return logger

        logger.setLevel(logging.INFO)
        log_path = Path(getattr(self, "desktop_log_path", self.app_root / LOG_NAME))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=DESKTOP_LOG_MAX_BYTES,
            backupCount=DESKTOP_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        return logger
