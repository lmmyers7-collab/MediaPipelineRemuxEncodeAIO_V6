from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.desktop.network.registry import InFlightRegistry


class NetworkRegistrySaveOrderTests(unittest.TestCase):
    def test_older_snapshot_cannot_overwrite_newer_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight.json"
            registry = InFlightRegistry()
            registry.claim(job_id="job-old", worker_id="w1", worker_name="W1", source_path=r"C:\old.mkv", encode_config={})
            first_snapshot = threading.Event()
            release_first = threading.Event()
            newer_done = threading.Event()
            errors: list[BaseException] = []
            real_dumps = json.dumps

            def gated_dumps(data, *args, **kwargs):
                if len(data.get("jobs", [])) == 1 and not first_snapshot.is_set():
                    first_snapshot.set()
                    if not release_first.wait(5):
                        raise RuntimeError("older snapshot release timeout")
                return real_dumps(data, *args, **kwargs)

            def save(done: threading.Event | None = None) -> None:
                try:
                    registry.save(path)
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    if done:
                        done.set()

            with patch("mediapipeline.desktop.network.registry_persistence.json.dumps", side_effect=gated_dumps):
                older = threading.Thread(target=save)
                older.start()
                self.assertTrue(first_snapshot.wait(5))
                registry.claim(job_id="job-new", worker_id="w2", worker_name="W2", source_path=r"C:\new.mkv", encode_config={})
                newer = threading.Thread(target=save, args=(newer_done,))
                newer.start()
                completed_out_of_order = newer_done.wait(0.25)
                release_first.set()
                older.join(5)
                newer.join(5)

            self.assertFalse(completed_out_of_order)
            self.assertFalse(older.is_alive() or newer.is_alive())
            self.assertEqual(errors, [])
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(sorted(row["job_id"] for row in persisted["jobs"]), ["job-new", "job-old"])

    def test_save_deep_copies_nested_worker_stats(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight.json"
            registry = InFlightRegistry()
            with registry._lock:
                registry._worker_stats["w1"] = {"name": "W1", "files": 1}
            ready = threading.Event()
            release = threading.Event()
            real_dumps = json.dumps

            def gated_dumps(data, *args, **kwargs):
                ready.set()
                if not release.wait(5):
                    raise RuntimeError("snapshot release timeout")
                return real_dumps(data, *args, **kwargs)

            with patch("mediapipeline.desktop.network.registry_persistence.json.dumps", side_effect=gated_dumps):
                thread = threading.Thread(target=registry.save, args=(path,))
                thread.start()
                self.assertTrue(ready.wait(5))
                with registry._lock:
                    registry._worker_stats["w1"]["files"] = 2
                release.set()
                thread.join(5)

            self.assertFalse(thread.is_alive())
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["worker_stats"]["w1"]["files"], 1)
