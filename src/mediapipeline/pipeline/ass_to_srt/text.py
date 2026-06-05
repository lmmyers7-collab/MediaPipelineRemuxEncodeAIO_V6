import re
from typing import Any


# HTML / XML tag. Requires a letter or slash+letter after '<' so we don't
# eat '<3' (emoji) or 'x < y' (math) in dialogue.
HTML_TAG_RE = re.compile(r'</?[A-Za-z][^>]*>')
ASS_OVERRIDE_BLOCK_RE = re.compile(r'\{([^{}]*)\}')
ASS_BASIC_FORMAT_TAG_RE = re.compile(r'\\([ibu])\s*([01])', re.IGNORECASE)
SRT_BASIC_FORMAT_TAG_RE = re.compile(r'</?(?:i|b|u)>', re.IGNORECASE)

# Non-breaking space, zero-width space, ideographic space, BOM.
WEIRD_SPACE_RE = re.compile(r'[\u00a0\u2000-\u200b\u3000\ufeff]')

# Valid ASS drawing command letters: m (move), n (move without close),
# l (line), b (cubic bezier), s/p (b-spline), q (bezier extension),
# c (close). 'e' is retained for compatibility with the previous script.
_DRAWING_CMD_CHARS = frozenset('mnlbspqce')
_NUMBER_RE         = re.compile(r'^-?\d+(\.\d+)?$')


def looks_like_drawing_line(ln: str) -> bool:
    """
    True only if `ln` is unambiguously an ASS drawing coordinate line
    left over after pysubs2 stripping.
    """
    tokens = ln.strip().split()
    if len(tokens) < 3:
        return False
    if tokens[0].lower() not in _DRAWING_CMD_CHARS:
        return False
    numeric_count = 0
    for tok in tokens[1:]:
        if _NUMBER_RE.match(tok):
            numeric_count += 1
        elif len(tok) == 1 and tok.lower() in _DRAWING_CMD_CHARS:
            continue
        else:
            return False
    return numeric_count >= 2


def sanitize_srt_markup(text: str) -> str:
    """Keep only the small SRT-safe markup subset supported by common players."""
    return HTML_TAG_RE.sub(
        lambda match: match.group(0) if SRT_BASIC_FORMAT_TAG_RE.fullmatch(match.group(0)) else '',
        text,
    )


def ass_override_block_to_srt_markup(match: re.Match[str]) -> str:
    pieces: list[str] = []
    for tag, enabled in ASS_BASIC_FORMAT_TAG_RE.findall(match.group(1)):
        tag_name = tag.lower()
        pieces.append(f"<{tag_name}>" if enabled == "1" else f"</{tag_name}>")
    return ''.join(pieces)


def render_ass_text_for_srt(line: Any, *, strip_formatting: bool) -> str:
    if strip_formatting:
        return getattr(line, 'plaintext', '') or ''

    raw = getattr(line, 'text', '') or ''
    text = raw.replace(r'\N', '\n').replace(r'\n', '\n').replace(r'\h', ' ')
    return ASS_OVERRIDE_BLOCK_RE.sub(ass_override_block_to_srt_markup, text)


def clean_text(raw: str, *, preserve_srt_markup: bool = False) -> str:
    """Normalise whitespace, drop drawing coords, and optionally keep basic SRT tags."""
    if not raw:
        return ''

    text = raw.replace('\u2028', '\n').replace('\u2029', '\n')
    text = sanitize_srt_markup(text) if preserve_srt_markup else HTML_TAG_RE.sub('', text)

    cleaned = []
    for ln in text.splitlines():
        ln = WEIRD_SPACE_RE.sub(' ', ln).strip()
        ln = re.sub(r'\s{2,}', ' ', ln)
        if not ln:
            continue
        if looks_like_drawing_line(ln):
            continue
        cleaned.append(ln)

    # Collapse only IMMEDIATELY ADJACENT exact duplicates.
    deduped = []
    for ln in cleaned:
        if deduped and deduped[-1].strip().lower() == ln.strip().lower():
            continue
        deduped.append(ln)

    return '\n'.join(deduped).strip()
