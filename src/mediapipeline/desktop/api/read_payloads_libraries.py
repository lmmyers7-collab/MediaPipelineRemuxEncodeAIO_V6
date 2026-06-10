from __future__ import annotations

from typing import Any

from .http_helpers import query_int, query_value
from .read_payloads_policy import read_unavailable_payload


class LocalApiLibrariesReadPayloadMixin:
    def _libraries_route_map_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("libraries route map")
        return self.facade.get_library_route_map(resolved)

    def _libraries_route_trace_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("libraries route trace")
        request = {
            "row_key": query_value(query, "row_key", query_value(query, "id", "")),
            "id": query_value(query, "id", ""),
            "source_path": query_value(query, "source_path", query_value(query, "path", "")),
            "path": query_value(query, "path", ""),
            "output_path": query_value(query, "output_path", ""),
        }
        return self.facade.get_library_route_trace(resolved, request, self._library_route_evidence(resolved))

    def _libraries_route_compare_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("libraries route compare")
        request = {
            "left_id": query_value(query, "left_id", query_value(query, "left", "")),
            "right_id": query_value(query, "right_id", query_value(query, "right", "")),
        }
        return self.facade.get_library_profile_compare(resolved, request)

    def _libraries_route_validation_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("libraries route validation")
        limit = query_int(query, "limit", 20)
        evidence = self._library_route_evidence(resolved, limit=limit)
        snapshot = self._snapshot()
        if snapshot is not None:
            try:
                evidence["diagnostics"] = self.facade.get_diagnostics(snapshot).to_mapping()
            except Exception as exc:  # pragma: no cover - defensive route isolation
                evidence["diagnostics"] = {"error": str(exc), "rows": []}
        evidence["commands"] = self.command_journal.to_mapping(limit=limit)
        return self.facade.get_library_route_validation(resolved, {"limit": limit}, evidence)

    def _library_route_evidence(self, resolved: Any, *, limit: int = 20) -> dict[str, Any]:
        evidence = self.facade.get_library_route_evidence(resolved, limit=limit)
        return evidence if isinstance(evidence, dict) else {}


__all__ = ["LocalApiLibrariesReadPayloadMixin"]
