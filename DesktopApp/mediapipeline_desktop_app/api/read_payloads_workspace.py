from __future__ import annotations

from typing import Any

from .read_payloads_policy import read_unavailable_payload


class LocalApiWorkspaceReadPayloadMixin:
    def _maintenance_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("maintenance")
        return self.facade.get_maintenance_workspace(resolved).to_mapping()

    def _maintenance_progress_payload(self) -> dict[str, Any]:
        get_progress = getattr(self.facade, "get_maintenance_health_progress", None)
        if not callable(get_progress):
            return read_unavailable_payload("maintenance progress")
        return get_progress()

    def _schedule_payload(self) -> dict[str, Any]:
        return self.facade.get_schedule_workspace().to_mapping()

    def _settings_workspace_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("settings workspace")
        return self.facade.get_settings_workspace(resolved).to_mapping()

    def _settings_wizard_status_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("settings wizard")
        return self.facade.get_settings_wizard_status(resolved)

    def _settings_wizard_defaults_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("settings wizard defaults")
        return self.facade.get_settings_wizard_defaults(resolved)

    def _network_workers_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("network workers")
        return self.facade.get_network_workers(resolved).to_mapping()

    def _sample_validation_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("sample validation")
        raw_limit = query.get("limit", ["20"])[0] if query else "20"
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = 20
        return self.facade.get_sample_validation_records(resolved, limit=limit)
