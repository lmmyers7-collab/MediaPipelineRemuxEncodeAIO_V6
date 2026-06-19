from __future__ import annotations

from .commands_audit import LocalApiAuditCommandPayloadMixin
from .commands_failures import LocalApiFailureCommandPayloadMixin
from .commands_final_library import LocalApiFinalLibraryPromotionCommandPayloadMixin
from .commands_file_overrides import LocalApiFileOverridesCommandPayloadMixin
from .commands_files import LocalApiFileCommandPayloadMixin
from .commands_maintenance import LocalApiMaintenanceCommandPayloadMixin
from .commands_metrics import LocalApiMetricsCommandPayloadMixin
from .commands_network import LocalApiNetworkCommandPayloadMixin
from .commands_process import LocalApiProcessCommandPayloadMixin
from .commands_queue_priority import LocalApiQueuePriorityCommandPayloadMixin
from .commands_queue_scan import LocalApiQueueScanCommandPayloadMixin
from .commands_queue_strategy import LocalApiQueueStrategyCommandPayloadMixin
from .commands_repair_reconcile import LocalApiRepairReconcileCommandPayloadMixin
from .commands_rename import LocalApiRenameCommandPayloadMixin
from .commands_schedule import LocalApiScheduleCommandPayloadMixin
from .commands_sample_validation import LocalApiSampleValidationCommandPayloadMixin
from .commands_settings import LocalApiSettingsCommandPayloadMixin
from .commands_subtitle_qa import LocalApiSubtitleQaCommandPayloadMixin
from .commands_ui_preferences import LocalApiUiPreferencesPayloadMixin


class LocalApiCommandHandlerMixin(
    LocalApiAuditCommandPayloadMixin,
    LocalApiFailureCommandPayloadMixin,
    LocalApiFinalLibraryPromotionCommandPayloadMixin,
    LocalApiFileOverridesCommandPayloadMixin,
    LocalApiFileCommandPayloadMixin,
    LocalApiMaintenanceCommandPayloadMixin,
    LocalApiMetricsCommandPayloadMixin,
    LocalApiNetworkCommandPayloadMixin,
    LocalApiQueueScanCommandPayloadMixin,
    LocalApiQueuePriorityCommandPayloadMixin,
    LocalApiQueueStrategyCommandPayloadMixin,
    LocalApiRepairReconcileCommandPayloadMixin,
    LocalApiRenameCommandPayloadMixin,
    LocalApiScheduleCommandPayloadMixin,
    LocalApiSampleValidationCommandPayloadMixin,
    LocalApiSettingsCommandPayloadMixin,
    LocalApiSubtitleQaCommandPayloadMixin,
    LocalApiUiPreferencesPayloadMixin,
    LocalApiProcessCommandPayloadMixin,
):
    """Aggregate POST command handlers for the local API server."""
