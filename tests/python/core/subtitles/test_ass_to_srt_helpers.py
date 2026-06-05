import importlib
import sys
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace


REPO_ROOT = find_repo_root(Path(__file__))
PIPELINE_ROOT = REPO_ROOT / "ops" / "pipeline"

if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

ass_to_srt = importlib.import_module("mediapipeline.pipeline.ass_to_srt_cli")


def _line(
    *,
    text: str,
    plaintext: str,
    style: str = "Default",
    start: int = 1000,
    end: int = 2000,
    line_type: str = "Dialogue",
    effect: str = "",
):
    return SimpleNamespace(
        type=line_type,
        style=style,
        text=text,
        plaintext=plaintext,
        start=start,
        end=end,
        effect=effect,
    )


def test_import_ass_to_srt_keeps_cli_module_public_surface():
    assert ass_to_srt.__file__.endswith("ass_to_srt.py")
    assert ass_to_srt.ms_to_srt(3661007) == "01:01:01,007"
    assert callable(ass_to_srt.parse_args)
    assert callable(ass_to_srt.main)
    assert callable(ass_to_srt.merge_overlapping_cues)


def test_text_cleanup_and_srt_rendering_preserve_exact_output_shape():
    line = _line(
        text=r"{\i1}Hello{\i0}<font color='red'>bad</font>\NSecond\hline",
        plaintext="Hello bad\nSecond line",
    )

    rendered = ass_to_srt.render_ass_text_for_srt(line, strip_formatting=False)
    cleaned = ass_to_srt.clean_text(rendered, preserve_srt_markup=True)
    output = ass_to_srt.render_srt([(0, 2500, cleaned)])

    assert cleaned == "<i>Hello</i>bad\nSecond line"
    assert output == "1\n00:00:00,000 --> 00:00:02,500\n<i>Hello</i>bad\nSecond line\n"


def test_dialogue_collection_keeps_whitelist_and_tracks_drop_diagnostics():
    style_is_noise = ass_to_srt.compile_style_matcher(["Sign*", "OP*"])
    style_is_dialog = ass_to_srt.compile_style_matcher(["Signs Important"])
    subs = [
        _line(text="Hello", plaintext="Hello", style="Default", start=0, end=1000),
        _line(text="Sign text", plaintext="Sign text", style="Sign Top", start=1000, end=2000),
        _line(text=r"{\k10}la", plaintext="la", style="OP Romaji", start=2000, end=3000),
        _line(text="Whitelisted", plaintext="Whitelisted", style="Signs Important", start=3000, end=4000),
        _line(text="m 0 0 l 10 10", plaintext="m 0 0 l 10 10", style="Default", start=4000, end=5000),
        _line(text="ignored", plaintext="ignored", line_type="Comment", start=5000, end=6000),
    ]

    result = ass_to_srt.collect_dialogue_cues(
        subs,
        style_is_noise=style_is_noise,
        style_is_dialog=style_is_dialog,
        remove_karaoke=True,
        strip_formatting=True,
    )

    assert result["cues"] == [
        (0, 1000, "Hello"),
        (3000, 4000, "Whitelisted"),
    ]
    assert result["skipped_style"] == 2
    assert result["skipped_empty"] == 1
    assert result["skipped_nodialog"] == 1
    assert result["style_whitelist"] == {"Signs Important": 1}
    assert result["sample_drops"]["style"][0].startswith("00:00:01,000 style='Sign Top'")


def test_overlap_merge_minimum_gap_and_rendering_are_stable():
    merged = ass_to_srt.merge_overlapping_cues([
        (1000, 3000, "dialogue"),
        (2000, 4000, "sign"),
    ])
    gapped = ass_to_srt.apply_minimum_gap(merged)

    assert merged == [
        (1000, 2000, "dialogue"),
        (2000, 3000, "dialogue\nsign"),
        (3000, 4000, "sign"),
    ]
    assert gapped == [
        (1000, 1999, "dialogue"),
        (2000, 2999, "dialogue\nsign"),
        (3000, 4000, "sign"),
    ]
    assert ass_to_srt.render_srt(gapped) == (
        "1\n00:00:01,000 --> 00:00:01,999\ndialogue\n\n"
        "2\n00:00:02,000 --> 00:00:02,999\ndialogue\nsign\n\n"
        "3\n00:00:03,000 --> 00:00:04,000\nsign\n"
    )


def test_encoding_selection_can_be_exercised_without_real_pysubs2_loader():
    class FakePysubs2:
        @staticmethod
        def load(_path, *, encoding):
            if encoding == "utf-8":
                return [_line(text="bad\ufffd", plaintext="bad\ufffd")]
            if encoding == "cp932":
                return [_line(text="clean text", plaintext="clean text")]
            raise UnicodeDecodeError(encoding, b"\x80", 0, 1, "bad byte")

    loader = importlib.import_module("mediapipeline.pipeline.ass_to_srt.ass_events").load_ass_with_best_encoding
    subs, encoding, diagnostics, last_err = loader(
        "sample.ass",
        ("utf-8", "cp932", "iso-8859-1"),
        FakePysubs2,
    )

    assert subs[0].plaintext == "clean text"
    assert encoding == "cp932"
    assert diagnostics[0]["replacement_count"] == 1
    assert diagnostics[1]["encoding"] == "cp932"
    assert diagnostics[2]["ok"] is False
    assert isinstance(last_err, UnicodeDecodeError)
