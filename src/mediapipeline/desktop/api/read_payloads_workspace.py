from __future__ import annotations

from typing import Any

from mediapipeline.core.maintenance.change_ledger import (
    DEFAULT_CHANGE_LEDGER_ROW_LIMIT,
)
from mediapipeline.core.rename.policy import rename_cleaning_policy_from_resolved, rename_request_with_cleaning_policy

from .http_helpers import query_json_object, query_value
from .read_payloads_policy import read_unavailable_payload


def _query_json_dict(query: dict[str, list[str]], key: str) -> dict[str, Any]:
    return query_json_object(query, key)


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

    def _maintenance_change_ledger_payload(self, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("maintenance change ledger")
        get_change_ledger = getattr(self.facade, "get_maintenance_change_ledger", None)
        if not callable(get_change_ledger):
            return read_unavailable_payload("maintenance change ledger")
        raw_limit = query_value(query or {}, "limit", str(DEFAULT_CHANGE_LEDGER_ROW_LIMIT))
        return get_change_ledger(resolved, row_limit=raw_limit)

    def _maintenance_productization_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("maintenance productization")
        get_status = getattr(self.facade, "get_productization_status", None)
        if not callable(get_status):
            return read_unavailable_payload("maintenance productization")
        return get_status(resolved)

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

    def _rename_clean_filename_preview_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        staged_policy = any(
            key in query
            for key in (
                "remove_terms_text",
                "movie_filter_options",
                "movie_filter_terms",
                "tv_remove_terms_text",
                "tv_filter_options",
                "tv_filter_terms",
            )
        )
        request = {
            "filename": query_value(query, "filename", ""),
            "mode": query_value(query, "mode", "movie"),
            "source_folder": query_value(query, "source_folder", ""),
            "remove_terms_text": query_value(query, "remove_terms_text", ""),
            "movie_filter_options": _query_json_dict(query, "movie_filter_options"),
            "movie_filter_terms": _query_json_dict(query, "movie_filter_terms"),
            "tv_remove_terms_text": query_value(query, "tv_remove_terms_text", ""),
            "tv_filter_options": _query_json_dict(query, "tv_filter_options"),
            "tv_filter_terms": _query_json_dict(query, "tv_filter_terms"),
        }
        if staged_policy:
            request["_rename_movie_filter_policy_source"] = "staged"
        else:
            resolved = self._resolved()
            request = rename_request_with_cleaning_policy(
                request,
                rename_cleaning_policy_from_resolved(resolved),
                source="saved",
                strip_existing=True,
            )
        return self.facade.get_rename_clean_filename_preview(request)

    def _rename_cleaning_filter_catalog_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        config_data = getattr(resolved, "config_data", None) if resolved is not None else None
        return self.facade.get_rename_cleaning_filter_catalog(config_data if isinstance(config_data, dict) else None)

    def _rename_movie_filter_catalog_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        config_data = getattr(resolved, "config_data", None) if resolved is not None else None
        return self.facade.get_rename_movie_filter_catalog(config_data if isinstance(config_data, dict) else None)

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
