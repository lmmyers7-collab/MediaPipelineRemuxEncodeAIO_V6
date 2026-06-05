from __future__ import annotations

from .read_payloads_inventory import LocalApiInventoryReadPayloadMixin
from .read_payloads_status import LocalApiStatusReadPayloadMixin
from .read_payloads_workspace import LocalApiWorkspaceReadPayloadMixin


class LocalApiReadPayloadMixin(
    LocalApiStatusReadPayloadMixin,
    LocalApiInventoryReadPayloadMixin,
    LocalApiWorkspaceReadPayloadMixin,
):
    """Aggregate GET/read payload adapters for the local API server."""
