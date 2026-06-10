from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.library.route_map import (
    build_library_profile_compare,
    build_library_route_map,
    build_library_route_trace,
    build_library_route_validation,
)


def _base_config() -> dict[str, object]:
    return {
        "SourceMovies": "C:/Media/Movies",
        "SourceTV": "C:/Media/TV",
        "Outsource": "D:/Out",
        "RoutingProfile": "plex_direct_stream",
        "RouteThresholdMode": "size_or_bitrate",
        "SizeGuardMode": "warn",
        "VideoCodec": "hevc_nvenc",
        "OutputContainer": "mkv",
    }


def _profile_by_id(payload: dict[str, object], library_id: str) -> dict[str, object]:
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        raise AssertionError("profiles missing from route map")
    for profile in profiles:
        if isinstance(profile, dict) and profile.get("library_id") == library_id:
            return profile
    raise AssertionError(f"profile not found: {library_id}")


def _route_field(profile: dict[str, object], key: str) -> dict[str, object]:
    fields = profile.get("route_fields")
    if not isinstance(fields, list):
        raise AssertionError("route_fields missing from profile")
    for field in fields:
        if isinstance(field, dict) and field.get("key") == key:
            return field
    raise AssertionError(f"route field not found: {key}")


class LibraryRouteMapBuilderTests(unittest.TestCase):
    def test_synthesized_default_paths_are_review_not_safe(self) -> None:
        payload = build_library_route_map(_base_config())

        self.assertEqual(payload["schema_version"], "library_route_map.v1")
        self.assertFalse(payload["mutation_enabled"])
        self.assertTrue(payload["read_only"])
        for library_id in ("movies", "tv"):
            with self.subTest(library_id=library_id):
                profile = _profile_by_id(payload, library_id)
                source = profile["path_evidence"]["source_path"]  # type: ignore[index]
                output = profile["path_evidence"]["output_path"]  # type: ignore[index]

                self.assertEqual(source["state"], "synthesized_builtin_default")
                self.assertEqual(source["status"], "review")
                self.assertFalse(source["safe"])
                self.assertEqual(output["state"], "synthesized_builtin_default")
                self.assertEqual(output["status"], "review")
                self.assertFalse(output["safe"])

    def test_explicit_override_equal_to_global_remains_explicit(self) -> None:
        config = {
            **_base_config(),
            "LibraryProfiles": [
                {
                    "id": "movies",
                    "name": "Movies",
                    "enabled": True,
                    "designation": "movie",
                    "source_path": "C:/Media/Movies",
                    "output_path": "D:/Out/Movies",
                    "overrides": {"editor": {"RoutingProfile": "plex_direct_stream"}},
                }
            ],
        }

        profile = _profile_by_id(build_library_route_map(config), "movies")
        route_goal = _route_field(profile, "RoutingProfile")

        self.assertEqual(route_goal["state"], "explicit")
        self.assertEqual(route_goal["effective_value"], "plex_direct_stream")
        self.assertTrue(route_goal["value_equals_global"])
        self.assertEqual(route_goal["source"], "library_override")

    def test_disabled_profiles_are_candidates_but_not_selected_for_overlapping_trace(self) -> None:
        config = {
            **_base_config(),
            "LibraryProfiles": [
                {
                    "id": "disabled-root",
                    "name": "Disabled Root",
                    "enabled": False,
                    "designation": "auto",
                    "source_path": "C:/Media",
                    "output_path": "D:/Out",
                },
                {
                    "id": "tv-child",
                    "name": "TV Child",
                    "enabled": True,
                    "designation": "tv",
                    "source_path": "C:/Media/TV/Shows",
                    "output_path": "D:/Out/TV",
                },
            ],
        }
        evidence = {
            "queue": {
                "schema_version": "desktop_queue_preview.v1",
                "rows": [
                    {
                        "row_key": "queue-1",
                        "source_path": "C:/Media/TV/Shows/Show/S01E01.mkv",
                        "height": 1080,
                        "duration_seconds": 1200,
                        "estimated_bitrate_mbps": 8,
                        "media_type": "tv",
                    }
                ],
            }
        }

        payload = build_library_route_trace(config, {"row_key": "queue-1"}, evidence)
        candidates = {row["library_id"]: row for row in payload["candidate_matches"]}

        self.assertEqual(payload["schema_version"], "library_route_trace.v1")
        self.assertEqual(payload["library_match"]["library_id"], "tv-child")
        self.assertEqual(payload["trace_status"], "current")
        self.assertEqual(payload["metadata_gaps"], [])
        self.assertFalse(candidates["disabled-root"]["eligible"])
        self.assertLess(candidates["disabled-root"]["match_depth"], candidates["tv-child"]["match_depth"])

    def test_designation_specific_route_fields_are_filtered_like_library_controls(self) -> None:
        config = {
            **_base_config(),
            "LibraryProfiles": [
                {
                    "id": "movie-explicit",
                    "name": "Movie Explicit",
                    "enabled": True,
                    "designation": "movie",
                    "source_path": "C:/Media/Movies",
                    "output_path": "D:/Out/Movies",
                },
                {
                    "id": "tv-explicit",
                    "name": "TV Explicit",
                    "enabled": True,
                    "designation": "tv",
                    "source_path": "C:/Media/TV",
                    "output_path": "D:/Out/TV",
                },
            ],
        }
        payload = build_library_route_map(config)
        movie = _profile_by_id(payload, "movie-explicit")
        tv = _profile_by_id(payload, "tv-explicit")
        movie_keys = {row["key"] for row in movie["route_fields"]}
        tv_keys = {row["key"] for row in tv["route_fields"]}

        self.assertIn("MovieRoute1080pTargetSizeGB", movie_keys)
        self.assertNotIn("TVRoute1080pTargetSizeGB", movie_keys)
        self.assertIn("TVRoute1080pTargetSizeGB", tv_keys)
        self.assertNotIn("MovieRoute1080pTargetSizeGB", tv_keys)
        self.assertEqual(movie["decision_matrix"][0]["target_fields"], ["MovieRoute1080pTargetSizeGB"])
        self.assertEqual(tv["decision_matrix"][0]["target_fields"], ["TVRoute1080pTargetSizeGB"])

    def test_trace_with_missing_or_partial_evidence_never_becomes_confident(self) -> None:
        missing = build_library_route_trace(_base_config(), {"row_key": "missing"}, {"queue": {"rows": []}})
        partial = build_library_route_trace(
            _base_config(),
            {"source_path": "C:/Media/Movies/MissingMetadata.mkv"},
            {"queue": {"rows": [{"source_path": "C:/Media/Movies/MissingMetadata.mkv"}]}},
        )

        self.assertEqual(missing["trace_status"], "missing")
        self.assertIn("row_evidence", missing["metadata_gaps"])
        self.assertEqual(partial["trace_status"], "review")
        self.assertEqual(set(partial["metadata_gaps"]), {"dimensions", "duration", "bitrate", "media_type"})

    def test_profile_compare_preserves_not_applicable_designation_rows(self) -> None:
        config = {
            **_base_config(),
            "LibraryProfiles": [
                {
                    "id": "movie-explicit",
                    "name": "Movie Explicit",
                    "enabled": True,
                    "designation": "movie",
                    "source_path": "C:/Media/Movies",
                    "output_path": "D:/Out/Movies",
                    "overrides": {"editor": {"MovieRoute1080pTargetSizeGB": 6.0}},
                },
                {
                    "id": "tv-explicit",
                    "name": "TV Explicit",
                    "enabled": True,
                    "designation": "tv",
                    "source_path": "C:/Media/TV",
                    "output_path": "D:/Out/TV",
                    "overrides": {"editor": {"TVRoute1080pTargetSizeGB": 1.5}},
                },
            ],
        }

        payload = build_library_profile_compare(config, "movie-explicit", "tv-explicit")
        rows = {row["field"]: row for row in payload["rows"]}

        self.assertEqual(payload["schema_version"], "library_profile_compare.v1")
        self.assertEqual(payload["compare_status"], "changed")
        self.assertTrue(rows["MovieRoute1080pTargetSizeGB"]["applies"]["left"])
        self.assertFalse(rows["MovieRoute1080pTargetSizeGB"]["applies"]["right"])
        self.assertEqual(rows["MovieRoute1080pTargetSizeGB"]["right"], {"status": "not_applicable"})
        self.assertFalse(rows["TVRoute1080pTargetSizeGB"]["applies"]["left"])
        self.assertTrue(rows["TVRoute1080pTargetSizeGB"]["applies"]["right"])
        self.assertEqual(rows["TVRoute1080pTargetSizeGB"]["left"], {"status": "not_applicable"})

    def test_validation_handoff_keeps_distinct_proof_categories(self) -> None:
        evidence = {
            "sample_validation": {
                "schema_version": "desktop_sample_validation_log.v1",
                "records": [{"record_id": "sample-1", "operator_decision": "approved"}],
            },
            "completed": {
                "schema_version": "desktop_completed_preview.v1",
                "rows": [{"row_key": "completed-1", "output_proof": "verified"}],
            },
            "pending_publish": {
                "schema_version": "desktop_pending_publish_preview.v1",
                "rows": [{"row_key": "pending-1", "state": "parked"}],
            },
            "diagnostics": {"schema_version": "desktop_diagnostics.v1", "status_summary": "Status OK"},
            "commands": {"schema_version": "desktop_command_history.v1", "entries": []},
        }

        payload = build_library_route_validation(_base_config(), evidence, limit=5)
        sections = {section["proof_type"]: section for section in payload["proof_sections"]}

        self.assertEqual(payload["schema_version"], "library_route_validation_handoff.v1")
        self.assertFalse(payload["mutation_enabled"])
        self.assertEqual(
            set(sections),
            {"sample_validation", "completed", "pending_publish", "diagnostics", "command_history"},
        )
        self.assertEqual(sections["sample_validation"]["status"], "current")
        self.assertEqual(sections["completed"]["status"], "current")
        self.assertEqual(sections["pending_publish"]["status"], "current")
        self.assertEqual(sections["diagnostics"]["status"], "current")
        self.assertEqual(sections["command_history"]["status"], "review")
        self.assertTrue(any(row["proof_type"] == "completed" for row in payload["proof_rows"]))
        self.assertTrue(any(row["proof_type"] == "pending_publish" for row in payload["proof_rows"]))


if __name__ == "__main__":
    unittest.main()
