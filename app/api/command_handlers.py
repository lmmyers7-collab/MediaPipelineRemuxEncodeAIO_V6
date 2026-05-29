from __future__ import annotations

from .commands_failures import LocalApiFailureCommandPayloadMixin
from .commands_file_overrides import LocalApiFileOverridesCommandPayloadMixin
from .commands_files import LocalApiFileCommandPayloadMixin
from .commands_maintenance import LocalApiMaintenanceCommandPayloadMixin
from .commands_process import LocalApiProcessCommandPayloadMixin
from .commands_queue_priority import LocalApiQueuePriorityCommandPayloadMixin
from .commands_queue_strategy import LocalApiQueueStrategyCommandPayloadMixin
from .commands_rename import LocalApiRenameCommandPayloadMixin
from .commands_schedule import LocalApiScheduleCommandPayloadMixin
from .commands_sample_validation import LocalApiSampleValidationCommandPayloadMixin
from .commands_settings import LocalApiSettingsCommandPayloadMixin


class LocalApiCommandHandlerMixin(
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
    """Aggregate POST command handlers for the local API server."""
