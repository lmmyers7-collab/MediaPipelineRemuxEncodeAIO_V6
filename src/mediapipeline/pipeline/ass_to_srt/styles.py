import fnmatch
import re
from collections.abc import Callable


# ---------------------------------------------------------------------------
# Default exclude-style patterns (case-insensitive shell-glob)
# ---------------------------------------------------------------------------
DEFAULT_EXCLUDE_STYLES = [
    # Sign translations: cover space, hyphen, and underscore separators.
    "Sign",  "Sign *",  "Sign-*",  "Sign_*",
    "Signs", "Signs *", "Signs-*", "Signs_*",

    # Opening sequence styles (Romaji, English, Kanji variants).
    "OP", "OP *", "OP-*", "OP_*",
    "Opening", "Opening *", "Opening-*", "Opening_*",

    # Ending sequence styles.
    "ED", "ED *", "ED-*", "ED_*",
    "Ending", "Ending *", "Ending-*", "Ending_*",

    # Song lyrics, romanizations, translations, karaoke containers.
    "*Lyrics*", "*Romaji*", "*Kanji*", "*Karaoke*",
    "Song", "Song *", "Song-*", "Song_*",

    # Episode / show cards, credits, notes.
    "Title", "Show Title", "Episode Title",
    "Next Episode", "Next *",
    "Credits", "Credit*",
    "Note", "Note*",
    "Caption", "Caption*",
    "Staff", "Staff*",

    # One-off style used by some Kakumei Subs releases.
    "fs",
]

# Style names that hint the event really IS a karaoke syllable. Used by
# looks_like_karaoke_syllable to avoid dropping stylistic \k on dialogue.
_KARAOKE_STYLE_HINTS = (
    'karaoke', 'lyric', 'romaji', 'kanji', 'song',
    'op ', 'op-', 'op_',
    'ed ', 'ed-', 'ed_',
    'opening', 'ending',
)

# FIX#7: Karaoke syllable-timing tag. Old pattern r'\\[kK]' matched any
# backslash+k/K, which was ambiguous. The tag always has the form
# \k<duration>, \K<duration>, \kf<duration>, \ko<duration>, \kt<duration>.
# Matching that full shape cleanly identifies true karaoke without
# catching stylistic \k ornaments.
KARAOKE_TAG_RE = re.compile(r'\\[kK][fot]?\s*\d+')

# Sentence-terminal punctuation: a strong hint the event is real dialogue
# even when it contains karaoke timing tags.
SENTENCE_PUNCT_RE = re.compile(r'[.!?…]')


def compile_style_matcher(patterns) -> Callable[[str], bool]:
    """Case-insensitive shell-glob style name matcher."""
    lowered = [p.lower() for p in patterns if p and p.strip()]

    def matches(style_name: str) -> bool:
        if not style_name:
            return False
        s = style_name.strip().lower()
        for pat in lowered:
            if fnmatch.fnmatchcase(s, pat):
                return True
        return False

    return matches


def is_pure_drawing_event(line) -> bool:
    """
    True only for events that are unambiguously a vector drawing with
    no readable text.

    This is intentionally conservative. Mixed events (dialogue with a
    decorative \\p1..\\p0 glyph embedded) are NOT flagged: pysubs2's
    `plaintext` strips matched drawing blocks for us while preserving
    the surrounding text.

    The one reliable signal for a pure drawing is an ASS `effect` value
    that explicitly says "paint"; anything else risks a false positive
    that silently deletes dialogue.
    """
    effect = getattr(line, 'effect', None)
    if effect and 'paint' in effect.lower():
        return True
    return False


def looks_like_karaoke_syllable(line) -> bool:
    """
    FIX#12: distinguish a real karaoke syllable (drop) from dialogue that
    happens to use \\k for a stylistic effect (keep).

    An event is treated as a karaoke syllable ONLY when ALL of the
    following hold:

        1. raw text matches KARAOKE_TAG_RE (an explicit \\k/\\K/\\kf/\\ko/
           \\kt duration: stylistic \\k without a number is no longer
           considered karaoke).
        2. plaintext, stripped, is <= 15 characters (was 20).
        3. plaintext contains no sentence-terminal punctuation.
        4. plaintext contains no newline (real dialogue spanning two
           lines is always kept).
        5. the event's Style name matches one of the typical karaoke
           style hints (OP/ED/Song/Lyrics/Karaoke/Romaji/Kanji...).
           This is the new "context gate" that prevents short stylistic
           battle-cry dialogue with \\k ornaments from being dropped.

    The thresholds lean toward keeping events. Missing a karaoke
    syllable just means the PowerShell MergeAdjacent step has a couple
    more identical cues to collapse. Dropping real dialogue is
    unrecoverable.
    """
    raw = getattr(line, 'text', '') or ''
    if not KARAOKE_TAG_RE.search(raw):
        return False

    plain = (getattr(line, 'plaintext', '') or '').strip()
    if len(plain) > 15:
        return False
    if '\n' in plain:
        return False
    if SENTENCE_PUNCT_RE.search(plain):
        return False

    style_name = (getattr(line, 'style', '') or '').lower()
    if any(hint in style_name for hint in _KARAOKE_STYLE_HINTS):
        return True
    # Conservative fallback: no style hint -> don't drop. A spurious
    # extra cue is far preferable to missing real dialogue.
    return False


def _split_style_patterns(raw: str | None, default: list[str]) -> list[str]:
    if raw and raw.strip():
        return [p.strip() for p in raw.split("|") if p.strip()]
    return list(default)
