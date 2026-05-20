from __future__ import annotations

from ..models import ResolvedPaths
from .dto import PublishReconciliationDto
from .facade_publish_reconciliation_policy import publish_reconciliation_from_payloads


class PublishReconciliationFacadeMixin:
    """Read-only Completed/Pending/Drain evidence reconciliation."""

    def get_publish_reconciliation_preview(self, resolved: ResolvedPaths, limit: int = 250) -> PublishReconciliationDto:
        completed = self.get_completed_preview(resolved, limit=limit).to_mapping()
        pending = self.get_pending_publish_preview(resolved).to_mapping()
        return publish_reconciliation_from_payloads(completed, pending, limit=limit)

__all__ = [
    "PublishReconciliationFacadeMixin",
]
