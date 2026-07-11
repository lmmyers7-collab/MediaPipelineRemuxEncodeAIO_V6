"""Audit and sample-run harness for the generated Tdarr Matrix test library."""

from mediapipeline.tools.dev import tdarr_matrix_models as _models
from mediapipeline.tools.dev.tdarr_matrix_models import *  # noqa: F403
from mediapipeline.tools.dev.tdarr_matrix_operations import *  # noqa: F403
from mediapipeline.tools.dev.tdarr_matrix_audits import *  # noqa: F403
from mediapipeline.tools.dev.tdarr_matrix_reporting import *  # noqa: F403


def _with_probe_adapters(function, *args, **kwargs):
    """Preserve the façade's replaceable ffprobe adapter seam."""
    original_available = _models.ffprobe_command_available
    original_probe = _models.probe_fixture_row
    try:
        _models.ffprobe_command_available = ffprobe_command_available
        _models.probe_fixture_row = probe_fixture_row
        return function(*args, **kwargs)
    finally:
        _models.ffprobe_command_available = original_available
        _models.probe_fixture_row = original_probe


def audit_fixture_video_probes(*args, **kwargs):
    return _with_probe_adapters(_models.audit_fixture_video_probes, *args, **kwargs)


def select_sample_rows_with_fixture_probe_filter(*args, **kwargs):
    return _with_probe_adapters(
        _models.select_sample_rows_with_fixture_probe_filter,
        *args,
        **kwargs,
    )

if __name__ == "__main__":
    raise SystemExit(main())
