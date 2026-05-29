from __future__ import annotations

import logging
import threading
from pathlib import Path

from .models import AuditRecord, CompletedJobRecord, FailureRecord, QueueRecord, ResolvedPaths, Snapshot, TelemetrySnapshot
from app.shared.constants import (
    ACTIVE_JOB_SCHEMA_VERSION,
    APP_STATE_NAME,
    CONFIG_SCHEMA_VERSION,
    CONTROL_FLAG_SCHEMA_VERSION,
    CONTROL_FLAG_STALE_AFTER_SECONDS,
    FAILURE_CLEAR_MANIFEST_SCHEMA_VERSION,
    LOG_LEVEL_VALUES,
    MEDIA_FILE_SUFFIXES,
    PLEX_RENAME_DEFAULT_REMOVE_TERMS,
    PROCESS_LAUNCH_ERROR_TAIL_LINES,
    PROCESS_LAUNCH_READY_CHECK_SECONDS,
    RERUN_CSV_COLUMNS,
    SCHEDULE_DAY_NAMES,
    VLC_LONG_PATH_THRESHOLD,
)
from app.schedule.app_state import AppStateScheduleServiceMixin
from app.audit.rerun_service import AuditRerunServiceMixin
from app.config.service import ConfigProfileServiceMixin
from app.completed.service import CompletedJobsServiceMixin
from app.files.opening import FileOpenServiceMixin
from app.failures.cleanup_service import FailureCleanupServiceMixin
from app.folder_policy.service import FolderPolicyServiceMixin
from app.publish.pending_service import PendingPublishServiceMixin
from app.paths.service import PathResolutionServiceMixin
from app.processes.lifecycle import ProcessLifecycleServiceMixin
from app.queue.service import QueueServiceMixin
from app.maintenance.release import ReleasePackageServiceMixin
from app.rename.service import RenameServiceMixin
from app.status.service import StatusServiceMixin
from app.telemetry.service import TelemetryServiceMixin
from app.shared.utils import (
    _normalize_open_path_text,
    _strip_windows_extended_path_prefix,
)


LOG_NAME = "MediaPipelineRemuxEncodeAIO_DesktopApp.log"


class DesktopAppService(
    PathResolutionServiceMixin,
    TelemetryServiceMixin,
    StatusServiceMixin,
    ProcessLifecycleServiceMixin,
    AppStateScheduleServiceMixin,
    ReleasePackageServiceMixin,
    PendingPublishServiceMixin,
    AuditRerunServiceMixin,
    QueueServiceMixin,
    ConfigProfileServiceMixin,
    CompletedJobsServiceMixin,
    FileOpenServiceMixin,
    FailureCleanupServiceMixin,
    FolderPolicyServiceMixin,
    RenameServiceMixin,
):
    def __init__(self, app_root: Path) -> None:
        self.app_root = app_root
        self.workspace_root = app_root.parent
        self.app_state_path = app_root / APP_STATE_NAME
        self._nvidia_smi_path: str | None = None
        self._nvidia_smi_checked = False
        self._vlc_path: Path | None = None
        self._vlc_checked = False
        self._telemetry_lock = threading.Lock()
        self._telemetry_stop = threading.Event()
        self._telemetry_thread: threading.Thread | None = None
        self._cached_telemetry = TelemetrySnapshot()
        self._completed_history_cache_key: str | None = None
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
        self._last_spawn_stdout_log: Path | None = None
        self._last_spawn_stderr_log: Path | None = None
        self._active_spawned_processes_lock = threading.Lock()
        self._active_spawned_processes: dict[int, tuple[object, str]] = {}
        self.logger = self._create_logger()
        self._initialize_telemetry_sampler()

    def _create_logger(self) -> logging.Logger:
        logger = logging.getLogger("mediapipeline_desktop_app")
        if logger.handlers:
            return logger

        logger.setLevel(logging.INFO)
        log_path = self.app_root / LOG_NAME
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        return logger

