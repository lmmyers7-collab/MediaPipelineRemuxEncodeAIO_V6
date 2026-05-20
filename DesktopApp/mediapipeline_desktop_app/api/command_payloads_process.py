from __future__ import annotations

import threading
from typing import Any

from .command_payloads_policy import (
    backend_shutdown_success_payload,
    backend_shutdown_unavailable_payload,
    resolved_paths_unavailable_payload,
)


class LocalApiProcessCommandPayloadMixin:
    def _request_backend_shutdown_after_response(self) -> None:
        shutdown_request = self.shutdown_request
        if shutdown_request is None:
            return

        def _run() -> None:
            try:
                shutdown_request()
            except Exception:
                self.logger.exception("local API backend shutdown callback failed")

        try:
            timer = threading.Timer(0.1, _run)
            timer.daemon = True
            timer.start()
        except Exception:
            self.logger.exception("local API backend shutdown timer start failed")

    def _pipeline_control_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("pipeline.control", "snapshot")
        return self.facade.request_pipeline_control(resolved, str(request.get("action") or "")).to_mapping()

    def _pipeline_start_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("pipeline.start", "snapshot")
        return self.facade.start_pipeline_process(resolved, request).to_mapping()

    def _audit_start_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("audit.start", "snapshot")
        return self.facade.start_audit_process(resolved, request).to_mapping()

    def _rerun_start_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.start", "snapshot")
        return self.facade.start_rerun_csv_process(resolved, request).to_mapping()

    def _force_active_work_shutdown_cleanup(self, resolved: Any) -> list[str]:
        messages: list[str] = []
        service = getattr(self.facade, "service", None)
        if service is None:
            return messages
        cleanup_tracked = getattr(service, "kill_active_spawned_processes", None)
        if callable(cleanup_tracked):
            try:
                messages.extend(str(item) for item in cleanup_tracked())
            except Exception as exc:
                self.logger.exception("local API tracked process cleanup failed before backend shutdown: %s", exc)
                messages.append(f"Tracked process cleanup failed: {exc}")
        cleanup_related = getattr(service, "kill_related_pipeline_processes", None)
        if callable(cleanup_related):
            try:
                messages.extend(str(item) for item in cleanup_related(resolved))
            except Exception as exc:
                self.logger.exception("local API related process cleanup failed before backend shutdown: %s", exc)
                messages.append(f"Related process cleanup failed: {exc}")
        return [message for message in messages if str(message).strip()]

    def _backend_shutdown_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.shutdown_request is None:
            return backend_shutdown_unavailable_payload()
        readiness = None
        resolved = self._resolved()
        if resolved is not None:
            try:
                readiness = self.facade.get_close_readiness(resolved, self._snapshot()).to_mapping()
            except Exception as exc:
                self.logger.exception("local API close-readiness verification failed before backend shutdown: %s", exc)
                readiness = {
                    "safe_to_close": False,
                    "state": "unknown",
                    "active_work": True,
                    "reason": "Close readiness could not be verified before backend shutdown.",
                }
        force_active_work_shutdown = bool(request.get("force_active_work_shutdown", False))
        cleanup_messages: list[str] = []
        if (
            isinstance(readiness, dict)
            and not bool(readiness.get("safe_to_close", True))
            and not force_active_work_shutdown
        ):
            return backend_shutdown_success_payload(readiness)
        if (
            force_active_work_shutdown
            and resolved is not None
            and isinstance(readiness, dict)
            and not bool(readiness.get("safe_to_close", True))
        ):
            cleanup_messages = self._force_active_work_shutdown_cleanup(resolved)
        self._request_backend_shutdown_after_response()
        return backend_shutdown_success_payload(
            readiness,
            force_active_work_shutdown=force_active_work_shutdown,
            cleanup_messages=cleanup_messages,
        )
