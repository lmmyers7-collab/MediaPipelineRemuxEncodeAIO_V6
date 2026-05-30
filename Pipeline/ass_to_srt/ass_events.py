from typing import Any, Callable

from ass_to_srt.styles import is_pure_drawing_event, looks_like_karaoke_syllable
from ass_to_srt.text import clean_text, render_ass_text_for_srt
from ass_to_srt.timing import ms_to_srt


def _ass_dialogue_stats(subs: Any) -> tuple[int, int, int, int]:
    dialogue_count = 0
    text_count = 0
    replacement_count = 0
    total_chars = 0
    for line in subs:
        if getattr(line, "type", "") != "Dialogue":
            continue
        dialogue_count += 1
        text = (getattr(line, "text", "") or getattr(line, "plaintext", "") or "").strip()
        if text:
            text_count += 1
            total_chars += len(text)
            replacement_count += text.count("\ufffd")
    return dialogue_count, text_count, replacement_count, total_chars


def load_ass_with_best_encoding(
    path: str,
    encodings: tuple[str, ...],
    pysubs2_module: Any,
) -> tuple[Any, str, list[dict[str, Any]], Exception | None]:
    candidates: list[tuple[tuple[int, int, int, int, int], Any, str, dict[str, Any]]] = []
    diagnostics: list[dict[str, Any]] = []
    last_err: Exception | None = None
    for order, enc in enumerate(encodings):
        try:
            subs = pysubs2_module.load(path, encoding=enc)
        except UnicodeDecodeError as exc:
            last_err = exc
            diagnostics.append({"encoding": enc, "ok": False, "error": str(exc)})
            continue
        except Exception as exc:
            last_err = exc
            diagnostics.append({"encoding": enc, "ok": False, "error": str(exc)})
            continue
        dialogue_count, text_count, replacement_count, total_chars = _ass_dialogue_stats(subs)
        diagnostic = {
            "encoding": enc,
            "ok": True,
            "dialogue_count": dialogue_count,
            "text_count": text_count,
            "replacement_count": replacement_count,
            "total_chars": total_chars,
        }
        diagnostics.append(diagnostic)
        score = (
            1 if text_count > 0 else 0,
            text_count,
            dialogue_count,
            total_chars,
            -replacement_count,
            -order,
        )
        candidates.append((score, subs, enc, diagnostic))

    if not candidates:
        return None, "", diagnostics, last_err
    _, subs, enc, _ = max(candidates, key=lambda item: item[0])
    return subs, enc, diagnostics, last_err


def collect_dialogue_cues(
    subs: Any,
    *,
    style_is_noise: Callable[[str], bool],
    style_is_dialog: Callable[[str], bool],
    remove_karaoke: bool,
    strip_formatting: bool,
) -> dict[str, Any]:
    style_kept = {}
    style_dropped = {}
    style_whitelist = {}
    sample_drops = {'style': [], 'drawing': [], 'karaoke': [], 'empty': []}

    def remember(bucket, line, snippet):
        if len(sample_drops[bucket]) < 3:
            sample_drops[bucket].append(
                f"{ms_to_srt(line.start)} style={line.style!r} "
                f"text={snippet[:60]!r}"
            )

    cues = []
    skipped_style = 0
    skipped_drawing = 0
    skipped_karaoke = 0
    skipped_empty = 0
    skipped_nodialog = 0

    for line in subs:
        if line.type != "Dialogue":
            skipped_nodialog += 1
            continue

        # FIX#14: whitelist check FIRST. A style on the whitelist
        # bypasses all other filters (except pure-drawing, which
        # is unconditionally unreadable).
        whitelisted = style_is_dialog(line.style)

        # Primary filter: style-based exclusion (skipped when whitelisted).
        if not whitelisted and style_is_noise(line.style):
            skipped_style += 1
            style_dropped[line.style] = style_dropped.get(line.style, 0) + 1
            remember('style', line, (line.plaintext or ''))
            continue

        # Secondary filter: pure vector drawing (no readable text).
        # Applied EVEN to whitelisted events because a pure drawing
        # really is unreadable regardless of style label.
        if is_pure_drawing_event(line):
            skipped_drawing += 1
            remember('drawing', line, (line.plaintext or ''))
            continue

        # Secondary filter: karaoke syllables (skipped when whitelisted
        # because user explicitly asked to keep anything with this style).
        if remove_karaoke and not whitelisted and looks_like_karaoke_syllable(line):
            skipped_karaoke += 1
            remember('karaoke', line, (line.plaintext or ''))
            continue

        rendered_text = render_ass_text_for_srt(line, strip_formatting=strip_formatting)
        text = clean_text(rendered_text, preserve_srt_markup=not strip_formatting)
        if not text:
            skipped_empty += 1
            remember('empty', line, (line.text or ''))
            continue

        cues.append((int(line.start), int(line.end), text))
        style_kept[line.style] = style_kept.get(line.style, 0) + 1
        if whitelisted:
            style_whitelist[line.style] = style_whitelist.get(line.style, 0) + 1

    return {
        "cues": cues,
        "skipped_style": skipped_style,
        "skipped_drawing": skipped_drawing,
        "skipped_karaoke": skipped_karaoke,
        "skipped_empty": skipped_empty,
        "skipped_nodialog": skipped_nodialog,
        "style_kept": style_kept,
        "style_dropped": style_dropped,
        "style_whitelist": style_whitelist,
        "sample_drops": sample_drops,
    }
