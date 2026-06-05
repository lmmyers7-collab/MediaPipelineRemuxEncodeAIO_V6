from __future__ import annotations

from typing import Any

from .command_results import resolved_paths_unavailable_payload


class LocalApiFailureCommandPayloadMixin:
    def _failures_clear_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("failures.clear", "failures")
        return self.facade.clear_failure_markers(resolved, request).to_mapping()
