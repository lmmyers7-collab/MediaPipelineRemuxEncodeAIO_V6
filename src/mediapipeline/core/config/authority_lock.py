"""Cross-process lock for the JSON settings authority transaction."""

from __future__ import annotations

import errno
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator


SETTINGS_AUTHORITY_LOCK_TIMEOUT_SECONDS = 10.0
SETTINGS_AUTHORITY_LOCK_POLL_SECONDS = 0.025


class SettingsAuthorityLockError(RuntimeError):
    """Raised when exclusive settings-authority ownership cannot be obtained."""


def settings_authority_lock_path(store_path: Path) -> Path:
    return store_path.with_name(f"{store_path.name}.lock")


def _ensure_lock_byte(handle: BinaryIO) -> None:
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
        os.fsync(handle.fileno())
    handle.seek(0)


def _try_lock(handle: BinaryIO) -> bool:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK} or getattr(exc, "winerror", None) in {
                33,
                36,
            }:
                return False
            raise

    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise


def _unlock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def settings_authority_lock(
    store_path: Path,
    *,
    timeout_seconds: float = SETTINGS_AUTHORITY_LOCK_TIMEOUT_SECONDS,
    poll_seconds: float = SETTINGS_AUTHORITY_LOCK_POLL_SECONDS,
    read_only: bool = False,
) -> Iterator[Path]:
    """Hold one OS-released lock across authority access.

    Read-only callers must use an already initialized lock file so acquiring
    the lock cannot create directories, files, or bytes as a side effect.
    """

    lock_path = settings_authority_lock_path(store_path)
    if read_only:
        if not lock_path.is_file():
            raise SettingsAuthorityLockError(
                "Settings authority read lock is not initialized; run the explicit settings repair/import flow first."
            )
        try:
            if lock_path.stat().st_size < 1:
                raise SettingsAuthorityLockError(
                    "Settings authority read lock is invalid; run the explicit settings repair/import flow first."
                )
        except OSError as exc:
            raise SettingsAuthorityLockError("Settings authority read lock could not be inspected.") from exc
    else:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    try:
        handle = lock_path.open("rb" if read_only else "a+b", buffering=0)
    except OSError as exc:
        action = "opened for read-only verification" if read_only else "opened"
        raise SettingsAuthorityLockError(f"Settings authority lock could not be {action}.") from exc
    acquired = False
    try:
        if not read_only:
            _ensure_lock_byte(handle)
        while True:
            try:
                acquired = _try_lock(handle)
            except OSError as exc:
                raise SettingsAuthorityLockError(
                    "Settings authority lock acquisition failed before the configuration transaction began."
                ) from exc
            if acquired:
                break
            if time.monotonic() >= deadline:
                raise SettingsAuthorityLockError(
                    "Settings authority lock acquisition timed out because another settings transaction is active."
                )
            time.sleep(max(0.001, float(poll_seconds)))
        yield lock_path
    finally:
        if acquired:
            try:
                _unlock(handle)
            except OSError:
                pass
        handle.close()


__all__ = [
    "SETTINGS_AUTHORITY_LOCK_POLL_SECONDS",
    "SETTINGS_AUTHORITY_LOCK_TIMEOUT_SECONDS",
    "SettingsAuthorityLockError",
    "settings_authority_lock",
    "settings_authority_lock_path",
]
