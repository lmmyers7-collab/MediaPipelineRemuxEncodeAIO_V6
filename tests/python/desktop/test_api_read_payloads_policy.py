from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.read_payloads_policy import (
    CLOSE_READINESS_UNAVAILABLE_REASON,
    CLOSE_READINESS_UNAVAILABLE_WARNING,
    close_readiness_unavailable_payload,
    read_unavailable_payload,
)


class LocalApiReadPayloadPolicyTests(unittest.TestCase):
    def test_read_unavailable_payload_preserves_error_contract(self) -> None:
        self.assertEqual(read_unavailable_payload("queue"), {"error": "queue unavailable"})
        self.assertEqual(read_unavailable_payload("settings workspace"), {"error": "settings workspace unavailable"})

    def test_close_readiness_unavailable_payload_preserves_contract(self) -> None:
        payload = close_readiness_unavailable_payload()

        self.assertEqual(payload["schema_version"], "desktop_close_readiness.v1")
        self.assertFalse(payload["safe_to_close"])
        self.assertEqual(payload["state"], "unknown")
        self.assertTrue(payload["active_work"])
        self.assertEqual(payload["reason"], CLOSE_READINESS_UNAVAILABLE_REASON)
        self.assertEqual(payload["warnings"], [CLOSE_READINESS_UNAVAILABLE_WARNING])


if __name__ == "__main__":
    unittest.main()
