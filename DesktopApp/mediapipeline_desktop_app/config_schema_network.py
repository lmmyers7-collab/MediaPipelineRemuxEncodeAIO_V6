from __future__ import annotations

from .config_keys import (
    KEY_COORDINATOR_ALSO_ENCODE_LOCALLY,
    KEY_COORDINATOR_AUTH_TOKEN,
    KEY_COORDINATOR_BIND_ADDRESS,
    KEY_COORDINATOR_HEARTBEAT_TIMEOUT_MINS,
    KEY_COORDINATOR_PORT,
    KEY_NETWORK_ROLE,
    KEY_WORKER_AUTH_TOKEN,
    KEY_WORKER_CONFIG_OVERRIDES,
    KEY_WORKER_COORDINATOR_URL,
    KEY_WORKER_NAME,
    KEY_WORKER_POLL_INTERVAL_SECS,
    KEY_WORKER_SOURCE_PATH_MAP,
)


# These are intentionally kept out of CONFIG_FIELD_DEFINITIONS so the
# standard settings page renderer does not try to auto-build UI for them.
# The Network settings page is hand-built to support the role selector and
# conditional sub-sections.
#
# Defaults below document what load_config() will produce when a field is
# absent, so existing config files load cleanly without changes.
NETWORK_CONFIG_DEFAULTS: dict[str, object] = {
    # "standalone" | "coordinator" | "worker"
    KEY_NETWORK_ROLE: "standalone",

    # --- Coordinator settings (ignored unless NetworkRole == "coordinator") ---
    # TCP port the coordinator HTTP server listens on.
    KEY_COORDINATOR_PORT: 7830,
    # Interface address the plaintext coordinator HTTP API binds to.
    KEY_COORDINATOR_BIND_ADDRESS: "0.0.0.0",
    # When True, the coordinator also encodes files locally (requires a GPU).
    KEY_COORDINATOR_ALSO_ENCODE_LOCALLY: False,
    # Minutes without a heartbeat before a claimed job is considered stale
    # and re-queued for another worker.
    KEY_COORDINATOR_HEARTBEAT_TIMEOUT_MINS: 5,
    # Shared bearer token. Empty string means auto-generated on first
    # coordinator-mode start and persisted to app state.
    KEY_COORDINATOR_AUTH_TOKEN: "",

    # --- Worker settings (ignored unless NetworkRole == "worker") ---
    # Full URL of the coordinator, e.g. "http://192.168.1.50:7830".
    KEY_WORKER_COORDINATOR_URL: "",
    # Human-readable label shown in the coordinator's worker board.
    # Defaults to socket.gethostname() at runtime when left blank.
    KEY_WORKER_NAME: "",
    # Must match the coordinator's CoordinatorAuthToken.
    KEY_WORKER_AUTH_TOKEN: "",
    # Seconds between /api/claim polls when the queue is empty.
    KEY_WORKER_POLL_INTERVAL_SECS: 10,
    # JSON object: prefix rewrites for coordinator-handed paths that this worker
    # cannot reach as-is.
    KEY_WORKER_SOURCE_PATH_MAP: "",
    # JSON object: per-worker-name encode config overrides applied at claim time.
    KEY_WORKER_CONFIG_OVERRIDES: "",
}

NETWORK_ROLE_CHOICES = ("standalone", "coordinator", "worker")
