"""Backend-owned single-instance lease and durable lifecycle identity."""

from __future__ import annotations

import ctypes
import json
import os
import tempfile
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol


BACKEND_INSTANCE_SCHEMA_VERSION = "desktop_backend_instance.v1"
BACKEND_INSTANCE_ERROR_SCHEMA_VERSION = "desktop_backend_instance_error.v1"
BACKEND_INSTANCE_METADATA_FILENAME = "backend_instance.v1.json"
_WINDOWS_BACKEND_MUTEX_NAME = "Local\\MediaPipelineRemuxEncodeAIO_Backend"
_ERROR_ALREADY_EXISTS = 183


class BackendInstanceAlreadyRunning(RuntimeError):
    """Raised when another backend still owns the process-wide lease."""


class BackendInstanceLock(Protocol):
    def try_acquire(self) -> bool: ...

    def release(self) -> None: ...


class _WindowsNamedMutexLock:
    def __init__(self, _state_root: Path) -> None:
        self._handle: int | None = None

    def try_acquire(self) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
        create_mutex.restype = ctypes.c_void_p
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (ctypes.c_void_p,)
        close_handle.restype = ctypes.c_int

        ctypes.set_last_error(0)
        handle = create_mutex(None, 0, _WINDOWS_BACKEND_MUTEX_NAME)
        if not handle:
            error_code = ctypes.get_last_error()
            raise OSError(error_code, "Could not create the backend single-instance mutex")
        if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
            close_handle(handle)
            return False
        self._handle = int(handle)
        return True

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (ctypes.c_void_p,)
        close_handle.restype = ctypes.c_int
        if not close_handle(ctypes.c_void_p(handle)):
            error_code = ctypes.get_last_error()
            raise OSError(error_code, "Could not close the backend single-instance mutex")


class _PosixFileLock:
    def __init__(self, state_root: Path) -> None:
        self._path = state_root / "backend_instance.lock"
        self._stream: Any | None = None

    def try_acquire(self) -> bool:
        import fcntl

        stream = self._path.open("a+b")
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            stream.close()
            return False
        except BaseException:
            stream.close()
            raise
        self._stream = stream
        return True

    def release(self) -> None:
        import fcntl

        stream = self._stream
        if stream is None:
            return
        self._stream = None
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


def _default_lock_factory(state_root: Path) -> BackendInstanceLock:
    if os.name == "nt":
        return _WindowsNamedMutexLock(state_root)
    return _PosixFileLock(state_root)


def default_backend_instance_state_root() -> Path:
    local_app_data = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_app_data:
        return Path(local_app_data) / "MediaPipelineRemuxEncodeAIO" / "Lifecycle"
    return Path(tempfile.gettempdir()) / "MediaPipelineRemuxEncodeAIO" / "Lifecycle"


def _read_recovered_metadata(path: Path) -> tuple[str, dict[str, Any]]:
    if not path.exists():
        return "missing", {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "stale_malformed", {}
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != BACKEND_INSTANCE_SCHEMA_VERSION
        or not str(payload.get("owner_id") or "").strip()
        or not isinstance(payload.get("owner_pid"), int)
    ):
        return "stale_malformed", {}
    return "stale_valid", payload


class BackendInstanceGuard:
    """Hold backend exclusivity until server and worker cleanup has completed."""

    def __init__(
        self,
        *,
        state_root: Path,
        lock: BackendInstanceLock,
        shell_surface: str,
        owner_id: str,
        owner_pid: int,
        clock: Callable[[], float],
        recovered_metadata_status: str,
        recovered_metadata: dict[str, Any],
    ) -> None:
        self.state_root = state_root
        self.metadata_path = state_root / BACKEND_INSTANCE_METADATA_FILENAME
        self._lock = lock
        self._clock = clock
        self._released = False
        self._acquired_at = float(clock())
        self._payload: dict[str, Any] = {
            "schema_version": BACKEND_INSTANCE_SCHEMA_VERSION,
            "owner_id": owner_id,
            "owner_pid": owner_pid,
            "shell_surface": str(shell_surface or "unknown"),
            "phase": "starting",
            "backend_url": "",
            "acquired_at_unix_seconds": self._acquired_at,
            "updated_at_unix_seconds": self._acquired_at,
            "recovered_metadata_status": recovered_metadata_status,
            "recovered_owner_id": str(recovered_metadata.get("owner_id") or ""),
            "recovered_owner_pid": int(recovered_metadata.get("owner_pid") or 0),
        }

    @property
    def owner_id(self) -> str:
        return str(self._payload["owner_id"])

    @classmethod
    def acquire(
        cls,
        state_root: Path,
        *,
        shell_surface: str,
        lock_factory: Callable[[Path], BackendInstanceLock] = _default_lock_factory,
        owner_id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
        pid: int | None = None,
        clock: Callable[[], float] = time.time,
    ) -> "BackendInstanceGuard":
        root = Path(state_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        metadata_path = root / BACKEND_INSTANCE_METADATA_FILENAME
        lock = lock_factory(root)
        if not lock.try_acquire():
            status, metadata = _read_recovered_metadata(metadata_path)
            owner_id = str(metadata.get("owner_id") or "unknown")
            owner_pid = int(metadata.get("owner_pid") or 0)
            phase = str(metadata.get("phase") or "unknown")
            raise BackendInstanceAlreadyRunning(
                "Another MediaPipeline Python backend still owns the backend instance lease "
                f"(owner_id={owner_id}, owner_pid={owner_pid}, phase={phase}, metadata={status}). "
                "The new shell must fail closed until that backend exits."
            )

        recovered_status, recovered_metadata = _read_recovered_metadata(metadata_path)
        guard = cls(
            state_root=root,
            lock=lock,
            shell_surface=shell_surface,
            owner_id=str(owner_id_factory()),
            owner_pid=int(os.getpid() if pid is None else pid),
            clock=clock,
            recovered_metadata_status=recovered_status,
            recovered_metadata=recovered_metadata,
        )
        try:
            guard._write_metadata()
        except BaseException:
            lock.release()
            raise
        return guard

    def mark_listening(self, backend_url: str) -> None:
        self._write_phase("listening", backend_url=backend_url)

    def mark_cleanup(self) -> None:
        self._write_phase("cleanup")

    def _write_phase(self, phase: str, *, backend_url: str | None = None) -> None:
        if self._released:
            raise RuntimeError("Backend instance ownership has already been released")
        self._payload["phase"] = phase
        if backend_url is not None:
            self._payload["backend_url"] = str(backend_url)
        self._payload["updated_at_unix_seconds"] = float(self._clock())
        self._write_metadata()

    def _write_metadata(self) -> None:
        temporary_path = self.metadata_path.with_name(
            f".{self.metadata_path.name}.{self.owner_id}.tmp"
        )
        temporary_path.write_text(
            json.dumps(self._payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, self.metadata_path)

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        metadata_error: BaseException | None = None
        try:
            try:
                payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and payload.get("owner_id") == self.owner_id:
                    self.metadata_path.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
            except BaseException as exc:
                metadata_error = exc
        finally:
            self._lock.release()
        if metadata_error is not None:
            raise metadata_error


__all__ = [
    "BACKEND_INSTANCE_ERROR_SCHEMA_VERSION",
    "BACKEND_INSTANCE_METADATA_FILENAME",
    "BACKEND_INSTANCE_SCHEMA_VERSION",
    "BackendInstanceAlreadyRunning",
    "BackendInstanceGuard",
    "default_backend_instance_state_root",
]
