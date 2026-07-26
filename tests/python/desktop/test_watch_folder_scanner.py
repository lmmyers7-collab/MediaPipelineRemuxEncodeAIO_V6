from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.watch.scanner import (  # noqa: E402
    FiredRegistry,
    StabilityTracker,
    normalize_extensions,
    scan_root,
)


class WatchFolderScannerTests(unittest.TestCase):
    def test_normalize_extensions_dot_prefixes_and_casefolds(self) -> None:
        self.assertEqual(normalize_extensions(["MKV", ".mp4", "", " avi "]), frozenset({".mkv", ".mp4", ".avi"}))
        self.assertEqual(normalize_extensions("m2ts"), frozenset({".m2ts"}))

    def test_scan_root_recurses_and_filters_by_extension(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            nested = root / "Season 01"
            nested.mkdir()
            keep = nested / "Episode.MKV"
            skip = nested / "Episode.txt"
            keep.write_bytes(b"video")
            skip.write_text("not media", encoding="utf-8")

            result = scan_root(str(root), normalize_extensions(["mkv"]))

        self.assertTrue(result.ok)
        self.assertEqual(set(result.snapshot), {str(keep.resolve())})
        self.assertEqual(result.snapshot[str(keep.resolve())][0], 5)

    def test_scan_root_reports_unreachable_root(self) -> None:
        missing = str(Path(tempfile.gettempdir()) / "mediapipeline-watch-missing-root")

        result = scan_root(missing, frozenset())

        self.assertFalse(result.ok)
        self.assertEqual(result.root, str(Path(missing).resolve()))
        self.assertEqual(result.snapshot, {})
        self.assertTrue(result.errors)

    def test_stability_tracker_emits_once_after_debounce(self) -> None:
        tracker = StabilityTracker(debounce_seconds=5)
        path = "C:/media/movie.mkv"
        stat = (100, 200)

        tracker.observe(path, stat, now=10)
        self.assertEqual(tracker.pop_stable(now=14), [])
        self.assertEqual(tracker.pop_stable(now=15), [(str(Path(path).resolve()), stat)])
        self.assertEqual(tracker.pop_stable(now=20), [])

        tracker.observe(path, (101, 201), now=21)
        self.assertEqual(tracker.pop_stable(now=25), [])
        self.assertEqual(tracker.pop_stable(now=26), [(str(Path(path).resolve()), (101, 201))])

    def test_growing_file_never_stabilizes_until_unchanged_for_debounce(self) -> None:
        tracker = StabilityTracker(debounce_seconds=5)
        path = "C:/media/copying.mkv"

        tracker.observe(path, (100, 200), now=0)
        self.assertEqual(tracker.pop_stable(now=0), [])
        tracker.observe(path, (250, 300), now=6)
        self.assertEqual(tracker.pop_stable(now=6), [])
        tracker.observe(path, (400, 410), now=12)
        self.assertEqual(tracker.pop_stable(now=12), [])
        tracker.observe(path, (400, 410), now=18)
        self.assertEqual(tracker.pop_stable(now=18), [(str(Path(path).resolve()), (400, 410))])

    def test_fired_registry_suppresses_same_path_and_stat_until_ttl(self) -> None:
        registry = FiredRegistry(ttl_seconds=10)
        path = "C:/media/movie.mkv"
        stat = (100, 200)

        self.assertTrue(registry.should_fire(path, stat, now=1))
        self.assertFalse(registry.should_fire(path, stat, now=2))
        self.assertTrue(registry.should_fire(path, (100, 201), now=3))
        self.assertTrue(registry.should_fire(path, stat, now=12))

    def test_fired_registry_expires_stale_entry_after_lru_reorder(self) -> None:
        registry = FiredRegistry(ttl_seconds=10)
        stat = (100, 200)

        self.assertTrue(registry.should_fire("C:/media/a.mkv", stat, now=0))
        self.assertTrue(registry.should_fire("C:/media/b.mkv", stat, now=5))
        self.assertFalse(registry.should_fire("C:/media/a.mkv", stat, now=6))

        self.assertTrue(registry.should_fire("C:/media/a.mkv", stat, now=11))
        self.assertFalse(registry.should_fire("C:/media/b.mkv", stat, now=11))

    def test_fired_registry_recent_churn_does_not_extend_stale_entry_ttl(self) -> None:
        registry = FiredRegistry(ttl_seconds=10)
        stat = (100, 200)

        self.assertTrue(registry.should_fire("C:/media/stale.mkv", stat, now=0))
        for timestamp in range(1, 10):
            self.assertTrue(registry.should_fire(f"C:/media/new-{timestamp}.mkv", stat, now=timestamp))
        self.assertFalse(registry.should_fire("C:/media/stale.mkv", stat, now=9.5))

        self.assertTrue(registry.should_fire("C:/media/stale.mkv", stat, now=11))

    def test_fired_registry_ttl_boundary_is_inclusive(self) -> None:
        registry = FiredRegistry(ttl_seconds=10)
        path = "C:/media/movie.mkv"
        stat = (100, 200)

        self.assertTrue(registry.should_fire(path, stat, now=0))
        self.assertFalse(registry.should_fire(path, stat, now=10))
        self.assertTrue(registry.should_fire(path, stat, now=10.001))

    def test_fired_registry_zero_ttl_never_suppresses(self) -> None:
        registry = FiredRegistry(ttl_seconds=0)
        path = "C:/media/movie.mkv"
        stat = (100, 200)

        self.assertTrue(registry.should_fire(path, stat, now=1))
        self.assertTrue(registry.should_fire(path, stat, now=1))

    def test_fired_registry_max_entries_uses_lru_order(self) -> None:
        registry = FiredRegistry(max_entries=2, ttl_seconds=100)
        stat = (100, 200)

        self.assertTrue(registry.should_fire("C:/media/a.mkv", stat, now=0))
        self.assertTrue(registry.should_fire("C:/media/b.mkv", stat, now=1))
        self.assertFalse(registry.should_fire("C:/media/a.mkv", stat, now=2))
        self.assertTrue(registry.should_fire("C:/media/c.mkv", stat, now=3))

        self.assertTrue(registry.should_fire("C:/media/b.mkv", stat, now=4))
        self.assertFalse(registry.should_fire("C:/media/c.mkv", stat, now=4))


if __name__ == "__main__":
    unittest.main()
