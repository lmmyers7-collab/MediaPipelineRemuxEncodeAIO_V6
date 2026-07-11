from __future__ import annotations

NETWORK_TEST_CONNECTION_SCHEMA_VERSION = "desktop_network_worker_test_connection.v1"
NETWORK_COORDINATOR_DISCOVERY_SCHEMA_VERSION = "desktop_network_coordinator_discovery.v1"

class NetworkDiscoveryUnavailable(RuntimeError):
    """Raised when optional coordinator discovery is unavailable."""
