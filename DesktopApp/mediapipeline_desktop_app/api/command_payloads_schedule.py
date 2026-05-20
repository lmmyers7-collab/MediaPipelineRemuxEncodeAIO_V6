from __future__ import annotations

from typing import Any


class LocalApiScheduleCommandPayloadMixin:
    def _schedule_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.facade.preview_schedule_patch(request).to_mapping()

    def _schedule_save_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.facade.save_schedule_patch(request).to_mapping()
