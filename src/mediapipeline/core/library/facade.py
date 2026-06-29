from __future__ import annotations

from typing import Any

from mediapipeline.core.library.route_map import (
    build_library_profile_compare,
    build_library_route_map,
    build_library_route_trace,
    build_library_route_validation,
)
from mediapipeline.core.library.summary import build_library_summary
from mediapipeline.core.queue.source_inventory import (
    preview_queue_source_inventory,
    queue_source_inventory_path,
    read_json_artifact,
    read_queue_scan_status,
)
from mediapipeline.desktop.models import ResolvedPaths


class LibraryRouteMapFacadeMixin:
    """Read-only Library Route Map evidence adapter."""

    def get_library_summary(self, resolved: ResolvedPaths) -> dict[str, Any]:
        queue_scan_status, source_inventory = _safe_queue_scan_artifacts(self, resolved)
        return build_library_summary(_resolved_config(resolved), queue_scan_status, source_inventory)

    def get_library_route_map(self, resolved: ResolvedPaths) -> dict[str, Any]:
        return build_library_route_map(_resolved_config(resolved))

    def get_library_route_trace(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_library_route_trace(_resolved_config(resolved), request, evidence or self.get_library_route_evidence(resolved))

    def get_library_profile_compare(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        return build_library_profile_compare(
            _resolved_config(resolved),
            left_id=str(request.get("left_id") or request.get("left") or ""),
            right_id=str(request.get("right_id") or request.get("right") or ""),
        )

    def get_library_route_validation(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        limit = _int_value(request.get("limit"), default=20)
        return build_library_route_validation(
            _resolved_config(resolved),
            evidence or self.get_library_route_evidence(resolved, limit=limit),
            limit=limit,
        )

    def get_library_route_evidence(self, resolved: ResolvedPaths, *, limit: int = 20) -> dict[str, Any]:
        return {
            "queue": _safe_mapping(lambda: self.get_queue_preview(resolved).to_mapping()),
            "completed": _safe_mapping(lambda: self.get_completed_preview(resolved, limit=str(max(1, min(500, limit)))).to_mapping()),
            "pending_publish": _safe_mapping(lambda: self.get_pending_publish_preview(resolved).to_mapping()),
            "sample_validation": _safe_mapping(lambda: self.get_sample_validation_records(resolved, limit=limit)),
        }


def _resolved_config(resolved: ResolvedPaths) -> dict[str, Any]:
    config = getattr(resolved, "config_data", None)
    return dict(config) if isinstance(config, dict) else {}


def _safe_queue_scan_artifacts(instance: Any, resolved: ResolvedPaths) -> tuple[dict[str, Any], dict[str, Any]]:
    queue_scan_status: dict[str, Any] = {}
    source_inventory: dict[str, Any] = {}
    artifact_reader = getattr(instance, "_queue_scan_artifacts", None)
    if callable(artifact_reader):
        try:
            status, inventory = artifact_reader(resolved)
            if isinstance(status, dict):
                queue_scan_status = dict(status)
            if isinstance(inventory, dict):
                source_inventory = dict(inventory)
        except Exception:
            queue_scan_status = {}
            source_inventory = {}
    if not queue_scan_status:
        queue_scan_status = read_queue_scan_status(resolved)
    if not source_inventory:
        source_inventory = preview_queue_source_inventory(read_json_artifact(queue_source_inventory_path(resolved)))
    return queue_scan_status, source_inventory


def _safe_mapping(factory: Any) -> dict[str, Any]:
    try:
        payload = factory()
    except Exception as exc:  # pragma: no cover - defensive read isolation
        return {"error": str(exc), "rows": []}
    return payload if isinstance(payload, dict) else {"error": "payload unavailable", "rows": []}


def _int_value(value: Any, *, default: int = 20) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = ["LibraryRouteMapFacadeMixin"]
