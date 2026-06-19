from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import threading
from typing import Any


DEFAULT_REMUX_PILOT_AUTO_PROMOTION_INTERVAL_SECONDS = 10.0


class RemuxPilotAutoPromotionServiceMixin:
    def _initialize_remux_pilot_auto_promotion(self) -> None:
        self._remux_pilot_auto_resolved_provider: Callable[[], Any] | None = None
        self._remux_pilot_auto_payload_builder: Callable[..., dict[str, Any]] | None = None
        self._remux_pilot_auto_interval_seconds = DEFAULT_REMUX_PILOT_AUTO_PROMOTION_INTERVAL_SECONDS
        self._remux_pilot_auto_lock = threading.Lock()
        self._remux_pilot_auto_stop = threading.Event()
        self._remux_pilot_auto_thread: threading.Thread | None = None
        self._remux_pilot_auto_last_signature = ""

    def configure_remux_pilot_auto_promotion(
        self,
        *,
        resolved_provider: Callable[[], Any] | None,
        payload_builder: Callable[..., dict[str, Any]] | None = None,
        interval_seconds: float = DEFAULT_REMUX_PILOT_AUTO_PROMOTION_INTERVAL_SECONDS,
    ) -> None:
        if not hasattr(self, "_remux_pilot_auto_lock"):
            self._initialize_remux_pilot_auto_promotion()
        self._remux_pilot_auto_resolved_provider = resolved_provider
        self._remux_pilot_auto_payload_builder = payload_builder
        self._remux_pilot_auto_interval_seconds = max(1.0, float(interval_seconds or 1.0))

    def start_background_tasks(self) -> None:
        super_start = getattr(super(), "start_background_tasks", None)
        if callable(super_start):
            super_start()
        self._start_remux_pilot_auto_promotion()

    def stop_background_tasks(self) -> None:
        self._stop_remux_pilot_auto_promotion()
        super_stop = getattr(super(), "stop_background_tasks", None)
        if callable(super_stop):
            super_stop()

    def run_remux_pilot_auto_promotion_once(self) -> dict[str, Any]:
        if not hasattr(self, "_remux_pilot_auto_lock"):
            self._initialize_remux_pilot_auto_promotion()
        provider = self._remux_pilot_auto_resolved_provider
        if not callable(provider):
            return {
                "ok": True,
                "command": "queue.file_overrides.remux_pilot_auto_promote",
                "message": "Remux pilot auto-promotion is not configured.",
                "skipped": "not_configured",
            }

        resolved = provider()
        payload_builder = self._remux_pilot_auto_payload_builder
        if not callable(payload_builder):
            return {
                "ok": True,
                "command": "queue.file_overrides.remux_pilot_auto_promote",
                "message": "Remux pilot auto-promotion payload builder is not configured.",
                "skipped": "not_configured",
            }

        signature = self._remux_pilot_auto_state_signature(resolved)
        if signature and signature == self._remux_pilot_auto_last_signature:
            return {
                "ok": True,
                "command": "queue.file_overrides.remux_pilot_auto_promote",
                "message": "Remux pilot auto-promotion state is unchanged.",
                "skipped": "state_unchanged",
            }

        payload = payload_builder(resolved=resolved)
        self._remux_pilot_auto_last_signature = self._remux_pilot_auto_state_signature(resolved) or signature
        logger = getattr(self, "logger", None)
        if payload.get("promoted_series_count"):
            if logger is not None:
                logger.info("%s", payload.get("message") or "Remux pilot auto-promotion applied.")
        elif not payload.get("ok"):
            if logger is not None:
                logger.warning("%s", payload.get("message") or "Remux pilot auto-promotion was blocked.")
        return payload

    def _start_remux_pilot_auto_promotion(self) -> None:
        if not hasattr(self, "_remux_pilot_auto_lock"):
            self._initialize_remux_pilot_auto_promotion()
        if not callable(self._remux_pilot_auto_resolved_provider):
            return
        if not callable(self._remux_pilot_auto_payload_builder):
            return
        with self._remux_pilot_auto_lock:
            if self._remux_pilot_auto_thread is not None and self._remux_pilot_auto_thread.is_alive():
                return
            self._remux_pilot_auto_stop = threading.Event()
            self._remux_pilot_auto_thread = threading.Thread(
                target=self._remux_pilot_auto_loop,
                name="remux-pilot-auto-promotion",
                daemon=True,
            )
            self._remux_pilot_auto_thread.start()

    def _stop_remux_pilot_auto_promotion(self) -> None:
        if not hasattr(self, "_remux_pilot_auto_stop"):
            return
        thread = self._remux_pilot_auto_thread
        self._remux_pilot_auto_stop.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
        self._remux_pilot_auto_thread = None

    def _remux_pilot_auto_loop(self) -> None:
        while not self._remux_pilot_auto_stop.is_set():
            try:
                self.run_remux_pilot_auto_promotion_once()
            except Exception as exc:
                logger = getattr(self, "logger", None)
                if logger is not None:
                    logger.warning("Remux pilot auto-promotion monitor failed: %s", exc)
            self._remux_pilot_auto_stop.wait(self._remux_pilot_auto_interval_seconds)

    def _remux_pilot_auto_state_signature(self, resolved: Any) -> str:
        parts: list[str] = []
        for attr in ("completed_manifest_path", "queue_snapshot_path", "file_overrides_path"):
            path_value = getattr(resolved, attr, None)
            if not path_value:
                parts.append(f"{attr}:")
                continue
            path = Path(path_value)
            try:
                stat = path.stat()
            except OSError:
                parts.append(f"{attr}:missing")
            else:
                parts.append(f"{attr}:{stat.st_mtime_ns}:{stat.st_size}")
        return "|".join(parts)
