from __future__ import annotations

from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from mediapipeline.tools.release_identity import read_release_label

APP_NAME = "MediaPipelineRemuxEncodeAIO"
_APP_VERSION_FALLBACK = "2026.06.04.001"


def _read_pipeline_product_version() -> str:
    root = find_repo_root(Path(__file__))
    try:
        return read_release_label(root, default=_APP_VERSION_FALLBACK)
    except ValueError:
        return _APP_VERSION_FALLBACK


APP_VERSION = _read_pipeline_product_version()
PIPELINE_SIDECAR_VERSION = "1.0"
APP_CHUNK = ""
