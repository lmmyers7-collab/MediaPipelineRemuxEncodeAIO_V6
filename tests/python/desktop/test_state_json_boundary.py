from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mediapipeline.core.validation.state_json import (
    StateJsonError,
    loads_bounded_state_json,
    read_bounded_state_json,
)


class StateJsonBoundaryTests(unittest.TestCase):
    def test_accepts_one_utf8_bom_and_rejects_invalid_encoding(self) -> None:
        self.assertEqual(loads_bounded_state_json(b"\xef\xbb\xbf{\"ok\":true}"), {"ok": True})

        with self.assertRaisesRegex(StateJsonError, "valid UTF-8") as raised:
            loads_bounded_state_json(b"{\"bad\":\xff}")

        self.assertEqual(raised.exception.code, "invalid_utf8")

    def test_rejects_duplicate_keys_nonfinite_values_and_excess_depth_with_sanitized_errors(self) -> None:
        cases = (
            (b'{"token-secret":1,"token-secret":2}', "duplicate_key"),
            (b'{"value":NaN}', "non_finite"),
            (("[" * 33 + "0" + "]" * 33).encode("ascii"), "too_deep"),
        )

        for raw, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(StateJsonError) as raised:
                    loads_bounded_state_json(raw, max_depth=32)
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn("token-secret", str(raised.exception))

    def test_file_read_caps_bytes_without_replacing_prior_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            original = b'{"schema_version":"fixture.v1"}'
            path.write_bytes(original)

            self.assertEqual(read_bounded_state_json(path, max_bytes=len(original)), {"schema_version": "fixture.v1"})
            path.write_bytes(original + b" ")
            with self.assertRaises(StateJsonError) as raised:
                read_bounded_state_json(path, max_bytes=len(original))

            self.assertEqual(raised.exception.code, "too_large")
            self.assertEqual(path.read_bytes(), original + b" ")

    def test_empty_and_double_bom_are_not_silently_defaulted(self) -> None:
        for raw in (b"", b"\xef\xbb\xbf\xef\xbb\xbf{}"):
            with self.subTest(raw=raw):
                with self.assertRaises(StateJsonError):
                    loads_bounded_state_json(raw)


if __name__ == "__main__":
    unittest.main()
