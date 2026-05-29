from __future__ import annotations

from typing import Any

from .command_results import resolved_paths_unavailable_payload


class LocalApiSampleValidationCommandPayloadMixin:
    def _sample_validation_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("sample_validation.preview", "sample_validation")
        return self.facade.preview_sample_validation_record(resolved, request)

    def _sample_validation_append_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("sample_validation.append", "sample_validation")
        return self.facade.append_sample_validation_record(resolved, request).to_mapping()
