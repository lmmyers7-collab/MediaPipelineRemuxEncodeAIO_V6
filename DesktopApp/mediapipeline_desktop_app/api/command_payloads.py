from __future__ import annotations

from .command_payloads_failures import LocalApiFailureCommandPayloadMixin
from .command_payloads_file_overrides import LocalApiFileOverridesCommandPayloadMixin
from .command_payloads_files import LocalApiFileCommandPayloadMixin
from .command_payloads_maintenance import LocalApiMaintenanceCommandPayloadMixin
from .command_payloads_process import LocalApiProcessCommandPayloadMixin
from .command_payloads_queue_priority import LocalApiQueuePriorityCommandPayloadMixin
from .command_payloads_queue_strategy import LocalApiQueueStrategyCommandPayloadMixin
from .command_payloads_rename import LocalApiRenameCommandPayloadMixin
from .command_payloads_schedule import LocalApiScheduleCommandPayloadMixin
from .command_payloads_sample_validation import LocalApiSampleValidationCommandPayloadMixin
from .command_payloads_settings import LocalApiSettingsCommandPayloadMixin


class LocalApiCommandPayloadMixin(
    LocalApiFailureCommandPayloadMixin,
    LocalApiFileOverridesCommandPayloadMixin,
    LocalApiFileCommandPayloadMixin,
    LocalApiMaintenanceCommandPayloadMixin,
    LocalApiQueuePriorityCommandPayloadMixin,
    LocalApiQueueStrategyCommandPayloadMixin,
    LocalApiRenameCommandPayloadMixin,
    LocalApiScheduleCommandPayloadMixin,
    LocalApiSampleValidationCommandPayloadMixin,
    LocalApiSettingsCommandPayloadMixin,
    LocalApiProcessCommandPayloadMixin,
):
    """Aggregate POST command payload adapters for the local API server."""
