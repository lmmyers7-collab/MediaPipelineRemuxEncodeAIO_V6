from __future__ import annotations

from io import BytesIO
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.http_helpers import read_json_body, resolve_asset_path


class _FakeHandler:
    def __init__(self, *, content_length: str, body: bytes = b"", content_type: str | None = "application/json") -> None:
        self.headers = {"Content-Length": content_length}
        if content_type is not None:
            self.headers["Content-Type"] = content_type
        self.rfile = BytesIO(body)


class ApiHttpHelpersTests(unittest.TestCase):
    def test_read_json_body_rejects_negative_content_length(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        handler = _FakeHandler(content_length="-1", body=b'{"ok": true}')

        payload = read_json_body(handler, lambda body, status: sent.append((body, status)))

        self.assertIsNone(payload)
        self.assertEqual(sent, [({"error": "invalid content length"}, 400)])
        self.assertEqual(handler.rfile.tell(), 0)

    def test_read_json_body_rejects_oversized_content_length_without_reading(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        handler = _FakeHandler(content_length="1001", body=b'{"ok": true}')

        payload = read_json_body(handler, lambda body, status: sent.append((body, status)), max_bytes=1000)

        self.assertIsNone(payload)
        self.assertEqual(sent, [({"error": "request body is too large"}, 413)])
        self.assertEqual(handler.rfile.tell(), 0)

    def test_read_json_body_accepts_empty_body_as_object(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        handler = _FakeHandler(content_length="0")

        payload = read_json_body(handler, lambda body, status: sent.append((body, status)))

        self.assertEqual(payload, {})
        self.assertEqual(sent, [])

    def test_read_json_body_rejects_missing_content_type_without_reading(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        body = b'{"ok": true}'
        handler = _FakeHandler(content_length=str(len(body)), body=body, content_type=None)

        payload = read_json_body(handler, lambda body, status: sent.append((body, status)))

        self.assertIsNone(payload)
        self.assertEqual(sent, [({"error": "unsupported media type; use application/json"}, 415)])
        self.assertEqual(handler.rfile.tell(), 0)

    def test_read_json_body_rejects_non_json_content_type_without_reading(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        body = b'{"ok": true}'
        handler = _FakeHandler(content_length=str(len(body)), body=body, content_type="text/plain")

        payload = read_json_body(handler, lambda body, status: sent.append((body, status)))

        self.assertIsNone(payload)
        self.assertEqual(sent, [({"error": "unsupported media type; use application/json"}, 415)])
        self.assertEqual(handler.rfile.tell(), 0)

    def test_read_json_body_accepts_json_content_type_with_charset(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        body = b'{"ok": true}'
        handler = _FakeHandler(content_length=str(len(body)), body=body, content_type="application/json; charset=utf-8")

        payload = read_json_body(handler, lambda body, status: sent.append((body, status)))

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(sent, [])

    def test_resolve_asset_path_rejects_traversal_and_returns_asset_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            assets = root / "assets"
            assets.mkdir()
            asset = assets / "app.js"
            asset.write_text("console.log('ok');", encoding="utf-8")
            (root / "secret.txt").write_text("secret", encoding="utf-8")

            self.assertEqual(resolve_asset_path(root, "/assets/app.js"), asset.resolve())
            self.assertIsNone(resolve_asset_path(root, "/assets/../secret.txt"))
            self.assertIsNone(resolve_asset_path(root, "/assets/..%2Fsecret.txt"))


if __name__ == "__main__":
    unittest.main()

