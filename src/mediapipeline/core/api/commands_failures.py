from __future__ import annotations

from typing import Any

from .command_results import resolved_paths_unavailable_payload


class LocalApiFailureCommandPayloadMixin:
    def _failures_clear_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("failures.clear", "failures")
        return self.facade.clear_failure_markers(resolved, request).to_mapping()

    def _failures_archive_evidence_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("failures.archive_evidence", "failures")
        return self.facade.archive_failure_evidence(resolved, request).to_mapping()

    def _failures_open_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("failures.open", "failures")
        return self.facade.open_failure_evidence(resolved, request).to_mapping()

    def _failures_artifacts_cleanup_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("failures.artifacts_cleanup", "failures")
        return self.facade.cleanup_failure_artifacts(resolved, request).to_mapping()

    def _failures_lifecycle_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("failures.lifecycle", "failures")
        return self.facade.transition_failure_lifecycle(resolved, request).to_mapping()
