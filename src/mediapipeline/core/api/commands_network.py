from __future__ import annotations

from .command_results import resolved_paths_unavailable_payload


class LocalApiNetworkCommandPayloadMixin:
    def _network_lifecycle_payload(
        self,
        request: dict,
        *,
        role: str,
        action: str,
        dry_run: bool,
    ) -> dict:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(f"network.{role}.{action}", "network")
        journal_recorder = None
        if not dry_run:
            record = getattr(self, "_record_command_journal", None)
            if callable(record):
                def journal_recorder(payload: dict, request_body: dict | None = None) -> None:
                    record(payload, request=request_body, strict=True)

        return self.facade.request_network_lifecycle(
            resolved,
            role=role,
            action=action,
            dry_run=dry_run,
            request=request,
            journal_recorder=journal_recorder,
        ).to_mapping()

    def _network_coordinator_start_dry_run_payload(self, request: dict) -> dict:
        return self._network_lifecycle_payload(request, role="coordinator", action="start", dry_run=True)

    def _network_coordinator_stop_dry_run_payload(self, request: dict) -> dict:
        return self._network_lifecycle_payload(request, role="coordinator", action="stop", dry_run=True)

    def _network_coordinator_start_payload(self, request: dict) -> dict:
        return self._network_lifecycle_payload(request, role="coordinator", action="start", dry_run=False)

    def _network_coordinator_stop_payload(self, request: dict) -> dict:
        return self._network_lifecycle_payload(request, role="coordinator", action="stop", dry_run=False)

    def _network_worker_start_dry_run_payload(self, request: dict) -> dict:
        return self._network_lifecycle_payload(request, role="worker", action="start", dry_run=True)

    def _network_worker_stop_dry_run_payload(self, request: dict) -> dict:
        return self._network_lifecycle_payload(request, role="worker", action="stop", dry_run=True)

    def _network_worker_start_payload(self, request: dict) -> dict:
        return self._network_lifecycle_payload(request, role="worker", action="start", dry_run=False)

    def _network_worker_stop_payload(self, request: dict) -> dict:
        return self._network_lifecycle_payload(request, role="worker", action="stop", dry_run=False)

    def _network_worker_test_connection_payload(self, request: dict) -> dict:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("network.worker.test_connection", "network")
        return self.facade.request_network_test_connection(resolved, request=request).to_mapping()

    def _network_worker_discover_coordinators_payload(self, request: dict) -> dict:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("network.worker.discover_coordinators", "network")
        return self.facade.request_network_worker_discover_coordinators(resolved, request=request).to_mapping()

    def _network_coordinator_join_blob_payload(self, request: dict) -> dict:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("network.coordinator.join_blob", "network")
        return self.facade.request_network_coordinator_join_blob(resolved, request=request).to_mapping()

    def _network_worker_join_cluster_payload(self, request: dict) -> dict:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("network.worker.join_cluster", "network")
        return self.facade.request_network_worker_join_cluster(resolved, request=request).to_mapping()


__all__ = [
    "LocalApiNetworkCommandPayloadMixin",
]
