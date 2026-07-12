from __future__ import annotations

from mediapipeline.core.kernel.contracts.pending_publish import PENDING_PUSH_RETRY_LIMIT

AUTONOMY_HEALTH_SCHEMA_VERSION = "desktop_autonomy_health.v1"

PENDING_REVIEW_SECONDS = 24 * 60 * 60
PENDING_BLOCK_SECONDS = 72 * 60 * 60
PENDING_RETRY_BLOCK_COUNT = PENDING_PUSH_RETRY_LIMIT
PENDING_TOTAL_REVIEW_BYTES = 100 * 1024**3
PENDING_TOTAL_BLOCK_BYTES = 250 * 1024**3

FAILURE_OPERATOR_REQUIRED_BLOCK_SECONDS = 72 * 60 * 60
FAILURE_OPERATOR_REQUIRED_BLOCK_COUNT = 10
FAILURE_INFRASTRUCTURE_BLOCK_COUNT = 3
FAILURE_INFRASTRUCTURE_TEXT_KEYS = {
    "category",
    "classification",
    "error",
    "error_code",
    "message",
    "operation",
    "operator_action",
    "reason",
    "stage",
    "suggested_action",
    "tool",
}

ACTIVE_JOB_TIMEOUT_GRACE_SECONDS = 15 * 60
ACTIVE_JOB_NO_TIMEOUT_BLOCK_SECONDS = 30 * 60

DEFAULT_STORAGE_MIN_FREE_GB = 100.0
STATE_FILE_REVIEW_BYTES = 100 * 1024**2
STATE_FILE_BLOCK_BYTES = 500 * 1024**2
AUTONOMY_SCAN_LIMIT = 500
AUTONOMY_GROWTH_PILOT_DAYS = 7
AUTONOMY_GROWTH_PROJECTION_DAYS = 30
AUTONOMY_GROWTH_REQUIRED_SNAPSHOTS = 2
AUTONOMY_GROWTH_SNAPSHOT_MAX_COUNT = 64
AUTONOMY_GROWTH_SNAPSHOT_FILE_NAME = "autonomy_growth_snapshots.jsonl"
AUTONOMY_GROWTH_SNAPSHOT_LOCK_TIMEOUT_SECONDS = 5.0
GIB_BYTES = 1024**3

AUTONOMY_CATEGORY_LABELS: dict[str, str] = {
    "pending_publish": "Pending publish",
    "failures": "Failure review",
    "workers": "Workers",
    "runtime_health": "Runtime health counters",
    "disk_state": "Disk and state growth",
    "path_health": "Configured path health",
    "journals": "Journals and manifests",
    "publish_recency": "Publish recency",
    "subtitles_ocr": "Subtitle and OCR review",
    "audio_policy_reviews": "Audio policy review",
}
