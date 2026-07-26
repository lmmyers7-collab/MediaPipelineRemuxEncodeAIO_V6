from __future__ import annotations

import os
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias


FileStat: TypeAlias = tuple[int, int]


@dataclass(frozen=True)
class ScanError:
    path: str
    message: str

    def to_mapping(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


@dataclass(frozen=True)
class ScanResult:
    root: str
    snapshot: dict[str, FileStat]
    errors: tuple[ScanError, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class _Observation:
    path: str
    stat: FileStat
    first_seen: float
    last_seen: float
    emitted: bool = False


def _canonical_path(path: str) -> str:
    try:
        return str(Path(path).resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        return os.path.abspath(path)


def _path_key(path: str) -> str:
    return os.path.normcase(_canonical_path(path)).casefold()


def normalize_extensions(extensions: object) -> frozenset[str]:
    values: list[str]
    if isinstance(extensions, str):
        values = [extensions]
    else:
        try:
            values = [str(item) for item in extensions or []]  # type: ignore[arg-type]
        except TypeError:
            values = [str(extensions or "")]
    normalized: set[str] = set()
    for value in values:
        text = value.strip().casefold()
        if not text:
            continue
        normalized.add(text if text.startswith(".") else f".{text}")
    return frozenset(normalized)


def scan_root(root: str, extensions: frozenset[str]) -> ScanResult:
    snapshot: dict[str, FileStat] = {}
    errors: list[ScanError] = []
    normalized_extensions = normalize_extensions(extensions)
    root_path = _canonical_path(str(root or ""))

    def scan_dir(path: str) -> None:
        try:
            with os.scandir(path) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name.casefold())
        except OSError as exc:
            errors.append(ScanError(path=path, message=str(exc)))
            return

        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    scan_dir(entry.path)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                suffix = os.path.splitext(entry.name)[1].casefold()
                if normalized_extensions and suffix not in normalized_extensions:
                    continue
                stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                errors.append(ScanError(path=entry.path, message=str(exc)))
                continue
            snapshot[_canonical_path(entry.path)] = (int(stat.st_size), int(stat.st_mtime_ns))

    scan_dir(root_path)
    return ScanResult(root=root_path, snapshot=snapshot, errors=tuple(errors))


class StabilityTracker:
    def __init__(
        self,
        *,
        debounce_seconds: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.debounce_seconds = max(0.0, float(debounce_seconds))
        self._clock = clock or time.monotonic
        self._observations: dict[str, _Observation] = {}

    def set_debounce_seconds(self, debounce_seconds: float) -> None:
        self.debounce_seconds = max(0.0, float(debounce_seconds))

    def observe(self, path: str, stat: FileStat, now: float | None = None) -> None:
        timestamp = self._clock() if now is None else float(now)
        key = _path_key(path)
        current = self._observations.get(key)
        normalized_stat = (int(stat[0]), int(stat[1]))
        if current is None or current.stat != normalized_stat:
            self._observations[key] = _Observation(
                path=_canonical_path(path),
                stat=normalized_stat,
                first_seen=timestamp,
                last_seen=timestamp,
            )
            return
        current.path = _canonical_path(path)
        current.last_seen = timestamp

    def remove_missing(self, paths: set[str]) -> None:
        keys = {_path_key(path) for path in paths}
        for key in list(self._observations):
            if key not in keys:
                del self._observations[key]

    def pop_stable(self, now: float | None = None) -> list[tuple[str, FileStat]]:
        timestamp = self._clock() if now is None else float(now)
        stable: list[tuple[str, FileStat]] = []
        for observation in self._observations.values():
            if observation.emitted:
                continue
            if timestamp - observation.first_seen < self.debounce_seconds:
                continue
            observation.emitted = True
            stable.append((observation.path, observation.stat))
        stable.sort(key=lambda item: item[0].casefold())
        return stable


class FiredRegistry:
    def __init__(
        self,
        *,
        max_entries: int = 10_000,
        ttl_seconds: float = 24.0 * 60.0 * 60.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.max_entries = max(1, int(max_entries))
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self._clock = clock or time.monotonic
        self._entries: OrderedDict[tuple[str, int, int], float] = OrderedDict()

    def _entry_key(self, path: str, stat: FileStat) -> tuple[str, int, int]:
        return (_path_key(path), int(stat[0]), int(stat[1]))

    def _expire(self, now: float) -> None:
        if self.ttl_seconds <= 0:
            self._entries.clear()
            return
        for key, timestamp in list(self._entries.items()):
            if now - timestamp > self.ttl_seconds:
                del self._entries[key]

    def has_fired(self, path: str, stat: FileStat, now: float | None = None) -> bool:
        timestamp = self._clock() if now is None else float(now)
        self._expire(timestamp)
        key = self._entry_key(path, stat)
        if key not in self._entries:
            return False
        self._entries.move_to_end(key)
        return True

    def mark_fired(self, path: str, stat: FileStat, now: float | None = None) -> None:
        timestamp = self._clock() if now is None else float(now)
        self._expire(timestamp)
        key = self._entry_key(path, stat)
        self._entries[key] = timestamp
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def should_fire(self, path: str, stat: FileStat, now: float | None = None) -> bool:
        timestamp = self._clock() if now is None else float(now)
        if self.has_fired(path, stat, timestamp):
            return False
        self.mark_fired(path, stat, timestamp)
        return True


__all__ = [
    "FiredRegistry",
    "FileStat",
    "ScanError",
    "ScanResult",
    "StabilityTracker",
    "normalize_extensions",
    "scan_root",
]
