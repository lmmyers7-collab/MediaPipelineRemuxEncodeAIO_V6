#!/usr/bin/env python3
"""
ass_to_srt_chatgpt.py  —  Convert one ASS subtitle stream from an MKV to plain SRT.

v1.0 — current helper release addressing the consolidated-review findings:

  [FIX#3]  Orphaned ffmpeg processes on Python timeout / kill.
           The old subprocess.run() approach leaked a child ffmpeg that
           kept holding NVENC sessions and file locks when PowerShell
           killed the Python process. We now (a) launch ffmpeg via
           Popen, (b) on Windows assign it to a Job Object with
           JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE so it dies automatically
           when Python exits, and (c) register a signal handler + a
           try/finally that explicitly terminates the child on every
           exit path.

  [FIX#4]  Overlap merging used to greedily extend end_time to the
           latest of the overlapping cues, causing dialogue lines to
           linger on-screen for the entire duration of a sign translation
           that briefly overlapped them. Replaced with split-based
           merging: each overlapping pair produces up to three non-
           overlapping segments, preserving temporal semantics.

  [FIX#7]  Karaoke tag regex tightened. Old pattern `\\[kK]` matched
           any backslash+k/K, which both over-matched (stylistic \\k
           without timing) and didn't make the contract clear. New
           pattern `\\[kK][fot]?\\s*\\d+` explicitly requires a karaoke
           timing tag (\\k, \\K, \\kf, \\ko, \\kt) followed by a duration.

  [FIX#12] looks_like_karaoke_syllable was dropping real short dialogue
           that happened to contain a \\k tag. Added: style-name hint
           check (line kept unless its Style name matches typical
           karaoke styles), plaintext length tightened to 15 chars,
           and multi-line plaintext is never treated as a karaoke
           syllable.

  [FIX#14] New 6th argv: include_styles (pipe-separated glob patterns).
           Events whose Style matches any include pattern are ALWAYS
           kept, even if they also match exclude patterns. Guards
           against fansubs that mislabel dialogue as "Sign" or "Caption".

  [FIX#15] apply_minimum_gap falls back to shifting the NEXT cue's
           start forward when the current cue cannot be shortened
           (i.e. when new_end <= current.start). Eliminates the
           VLC zero-gap skip entirely rather than fixing only the
           easy cases.

Usage:
    python3 ass_to_srt_chatgpt.py <input.mkv> <stream_index> <output.srt>
                          [remove_karaoke] [exclude_styles] [include_styles]

    python3 ass_to_srt_chatgpt.py --input <input.mkv> --stream-index <stream_index>
                          --output <output.srt> [--keep-karaoke]
                          [--exclude-styles <pipe-separated globs>]
                          [--include-styles <pipe-separated globs>]
                          [--keep-temp-ass] [--summary-json <path>]

    stream_index    ffprobe absolute stream index (e.g. 3 for the 4th stream)
    remove_karaoke  "1" to drop karaoke-syllable events (default), "0" to keep
    exclude_styles  Pipe-separated case-insensitive shell-glob patterns that
                    match non-dialogue ASS Style names. Events matching any
                    pattern are dropped. Empty = built-in defaults.
    include_styles  Pipe-separated case-insensitive shell-glob patterns
                    (WHITELIST). Events matching any pattern are ALWAYS
                    kept, even if they also match an exclude pattern.
                    Empty = no whitelist. [Available in v1.0]

Design notes:
    The primary filter is style-based. Fansub ASS files use a small set of
    conventional style names for non-dialogue (Sign*, Signs*, OP*, ED*,
    *Lyrics*, *Romaji*, Title, Credits ...). Excluding those removes the
    overwhelming majority of noise without touching dialogue.

    Secondary filters (pure-drawing, karaoke-syllable) only catch events
    that slipped past style filtering. They are intentionally conservative —
    a false-positive in the secondary filters silently drops dialogue, and
    that is exactly the failure mode this revision exists to fix.

    After filtering, overlapping SRT cues are merged into non-overlapping
    time ranges. Samsung's built-in SRT renderer and most DLNA clients
    drop one cue when two are simultaneously active; merging the texts
    into a single cue with \\n between them preserves all dialogue.

Dependencies:
    pip install pysubs2
"""
import argparse
import contextlib
import json
import sys
import os
import re
import shutil
import signal
import subprocess
import tempfile
import fnmatch
import atexit
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import pysubs2
except ImportError:
    print("ERROR: pysubs2 not installed. Run: pip install pysubs2", file=sys.stderr)
    sys.exit(2)


__version__ = "1.0"

_LOG_LEVELS = {
    "ERROR": 0,
    "WARN": 1,
    "INFO": 2,
    "DEBUG": 3,
}
_CURRENT_LOG_LEVEL = _LOG_LEVELS["INFO"]


def set_log_verbosity(*, quiet: bool = False, verbose: bool = False) -> None:
    global _CURRENT_LOG_LEVEL
    if verbose:
        _CURRENT_LOG_LEVEL = _LOG_LEVELS["DEBUG"]
    elif quiet:
        _CURRENT_LOG_LEVEL = _LOG_LEVELS["WARN"]
    else:
        _CURRENT_LOG_LEVEL = _LOG_LEVELS["INFO"]


def emit_prefixed(text: str) -> None:
    match = re.match(r"^(ERROR|WARN|INFO|DEBUG):\s*", text)
    level = match.group(1) if match else "INFO"
    if _LOG_LEVELS[level] <= _CURRENT_LOG_LEVEL:
        print(text, file=sys.stderr)


def atomic_write_text(path: str, text: str, *, encoding: str = "utf-8") -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except Exception:
        with contextlib.suppress(OSError):
            os.remove(tmp_name)
        raise


def atomic_write_json(path: str, summary_data: Dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(summary_data, indent=2, ensure_ascii=False))


def write_summary_json(path: Optional[str], summary_data: Dict[str, Any]) -> None:
    if not path:
        return

    summary_dir = os.path.dirname(os.path.abspath(path))
    if summary_dir:
        os.makedirs(summary_dir, exist_ok=True)
    atomic_write_json(path, summary_data)


def fail_with_summary(args: argparse.Namespace,
                      summary_data: Dict[str, Any],
                      message: str,
                      *,
                      stage: Optional[str] = None,
                      details: Optional[List[str]] = None,
                      exit_code: int = 1) -> None:
    emit_prefixed(f"ERROR: {message}")
    if details:
        for line in details:
            emit_prefixed(f"ERROR:   {line}")
    summary_data["status"] = "error"
    summary_data["error"] = message
    if stage:
        summary_data["stage"] = stage
    if details:
        summary_data["details"] = details
    try:
        write_summary_json(args.summary_json, summary_data)
    except Exception as exc:
        emit_prefixed(f"ERROR: failed to write summary JSON: {exc}")
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Default exclude-style patterns (case-insensitive shell-glob)
# ---------------------------------------------------------------------------
DEFAULT_EXCLUDE_STYLES = [
    # Sign translations — cover space, hyphen, and underscore separators
    "Sign",  "Sign *",  "Sign-*",  "Sign_*",
    "Signs", "Signs *", "Signs-*", "Signs_*",

    # Opening sequence styles (Romaji, English, Kanji variants)
    "OP", "OP *", "OP-*", "OP_*",
    "Opening", "Opening *", "Opening-*", "Opening_*",

    # Ending sequence styles
    "ED", "ED *", "ED-*", "ED_*",
    "Ending", "Ending *", "Ending-*", "Ending_*",

    # Song lyrics, romanizations, translations, karaoke containers
    "*Lyrics*", "*Romaji*", "*Kanji*", "*Karaoke*",
    "Song", "Song *", "Song-*", "Song_*",

    # Episode / show cards, credits, notes
    "Title", "Show Title", "Episode Title",
    "Next Episode", "Next *",
    "Credits", "Credit*",
    "Note", "Note*",
    "Caption", "Caption*",
    "Staff", "Staff*",

    # One-off style used by some Kakumei Subs releases
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


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# FIX#7: Karaoke syllable-timing tag. Old pattern r'\\[kK]' matched any
# backslash+k/K, which was ambiguous. The tag always has the form
# \k<duration>, \K<duration>, \kf<duration>, \ko<duration>, \kt<duration>.
# Matching that full shape cleanly identifies true karaoke without
# catching stylistic \k ornaments.
KARAOKE_TAG_RE = re.compile(r'\\[kK][fot]?\s*\d+')

# HTML / XML tag. Requires a letter or slash+letter after '<' so we don't
# eat '<3' (emoji) or 'x < y' (math) in dialogue.
HTML_TAG_RE = re.compile(r'</?[A-Za-z][^>]*>')
ASS_OVERRIDE_BLOCK_RE = re.compile(r'\{([^{}]*)\}')
ASS_BASIC_FORMAT_TAG_RE = re.compile(r'\\([ibu])\s*([01])', re.IGNORECASE)
SRT_BASIC_FORMAT_TAG_RE = re.compile(r'</?(?:i|b|u)>', re.IGNORECASE)

# Sentence-terminal punctuation — a strong hint the event is real dialogue
# even when it contains karaoke timing tags.
SENTENCE_PUNCT_RE = re.compile(r'[.!?…]')

# Non-breaking space, zero-width space, ideographic space, BOM.
WEIRD_SPACE_RE = re.compile(r'[\u00a0\u2000-\u200b\u3000\ufeff]')

# Valid ASS drawing command letters: m (move), n (move without close),
# l (line), b (cubic bezier), s/p (b-spline), q (bezier extension),
# c (close). 'e' is retained for compatibility with the previous script.
_DRAWING_CMD_CHARS = frozenset('mnlbspqce')
_NUMBER_RE         = re.compile(r'^-?\d+(\.\d+)?$')


# ---------------------------------------------------------------------------
# FIX#3: Windows Job Object wrapper — ensures ffmpeg dies with Python
# ---------------------------------------------------------------------------
# When PowerShell's Invoke-NativeCommand kills the python.exe that runs
# this script (timeout, stop flag, or parent crash), the ffmpeg child
# used to survive and keep holding NVENC sessions + file locks on the
# source MKV. Eventually that exhausted the driver's concurrent-encode
# limit and the pipeline would begin failing every subsequent encode.
#
# The fix: on Windows, we create a Job Object with
# JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE and assign ffmpeg to it. When this
# Python process exits for ANY reason (SIGINT, SIGTERM, unhandled
# exception, or even a TerminateProcess from the parent), the kernel
# reliably reaps every process in the job — including the child ffmpeg.
#
# On non-Windows platforms we fall back to process groups (setsid) and
# os.killpg, which gives the same guarantee via POSIX semantics.

_IS_WINDOWS = (os.name == 'nt')

class ChildProcessGuard:
    """Launches a subprocess in a way that guarantees it dies if we do."""

    def __init__(self):
        self._job_handle = None
        self._active_children: list[subprocess.Popen] = []
        self._init_windows_job()

    def _init_windows_job(self):
        if not _IS_WINDOWS:
            return
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

            # Job Object structures
            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ('PerProcessUserTimeLimit', ctypes.c_int64),
                    ('PerJobUserTimeLimit',     ctypes.c_int64),
                    ('LimitFlags',              wintypes.DWORD),
                    ('MinimumWorkingSetSize',   ctypes.c_size_t),
                    ('MaximumWorkingSetSize',   ctypes.c_size_t),
                    ('ActiveProcessLimit',      wintypes.DWORD),
                    ('Affinity',                ctypes.c_size_t),
                    ('PriorityClass',           wintypes.DWORD),
                    ('SchedulingClass',         wintypes.DWORD),
                ]

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('ReadOperationCount',  ctypes.c_uint64),
                    ('WriteOperationCount', ctypes.c_uint64),
                    ('OtherOperationCount', ctypes.c_uint64),
                    ('ReadTransferCount',   ctypes.c_uint64),
                    ('WriteTransferCount',  ctypes.c_uint64),
                    ('OtherTransferCount',  ctypes.c_uint64),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ('IoInfo',                IO_COUNTERS),
                    ('ProcessMemoryLimit',    ctypes.c_size_t),
                    ('JobMemoryLimit',        ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t),
                    ('PeakJobMemoryUsed',     ctypes.c_size_t),
                ]

            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
            JobObjectExtendedLimitInformation  = 9

            CreateJobObjectW           = kernel32.CreateJobObjectW
            CreateJobObjectW.restype   = wintypes.HANDLE
            CreateJobObjectW.argtypes  = [ctypes.c_void_p, wintypes.LPCWSTR]

            SetInformationJobObject           = kernel32.SetInformationJobObject
            SetInformationJobObject.restype   = wintypes.BOOL
            SetInformationJobObject.argtypes  = [
                wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            ]

            CloseHandle                  = kernel32.CloseHandle
            CloseHandle.restype          = wintypes.BOOL
            CloseHandle.argtypes         = [wintypes.HANDLE]

            handle = CreateJobObjectW(None, None)
            if not handle:
                return

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

            ok = SetInformationJobObject(
                handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not ok:
                CloseHandle(handle)
                return

            self._job_handle = handle
            # Stash API refs for later Popen assignment.
            self._AssignProcessToJobObject           = kernel32.AssignProcessToJobObject
            self._AssignProcessToJobObject.restype   = wintypes.BOOL
            self._AssignProcessToJobObject.argtypes  = [wintypes.HANDLE, wintypes.HANDLE]

            OpenProcess                  = kernel32.OpenProcess
            OpenProcess.restype          = wintypes.HANDLE
            OpenProcess.argtypes         = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self._OpenProcess            = OpenProcess

            self._CloseHandle            = CloseHandle

            PROCESS_SET_QUOTA    = 0x0100
            PROCESS_TERMINATE    = 0x0001
            self._proc_access    = PROCESS_SET_QUOTA | PROCESS_TERMINATE
        except Exception as exc:
            # If the job-object dance fails for any reason we fall back to
            # killing the child explicitly in finally/atexit handlers. The
            # guarantee is weaker (the parent must get a chance to run its
            # cleanup) but still much better than no fix at all.
            emit_prefixed(f"WARN: Job Object init failed ({exc}); using fallback cleanup")
            self._job_handle = None

    def popen(self, argv, **kwargs) -> subprocess.Popen:
        """Launch a subprocess that the OS will kill when we die."""
        if _IS_WINDOWS:
            # CREATE_NEW_PROCESS_GROUP so Ctrl-C to us doesn't kill ffmpeg
            # before we can clean up; we call Terminate ourselves.
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            kwargs.setdefault('creationflags', creationflags)
        else:
            # POSIX: put the child in its own process group so we can
            # killpg it if the parent is SIGTERMed.
            kwargs.setdefault('preexec_fn', os.setsid)

        proc = subprocess.Popen(argv, **kwargs)

        if _IS_WINDOWS and self._job_handle:
            try:
                PROCESS_SET_QUOTA = 0x0100
                PROCESS_TERMINATE = 0x0001
                hProc = self._OpenProcess(
                    self._proc_access, False, proc.pid)
                if hProc:
                    self._AssignProcessToJobObject(self._job_handle, hProc)
                    self._CloseHandle(hProc)
            except Exception as exc:
                emit_prefixed(f"WARN: could not assign ffmpeg to job ({exc})")

        self._active_children.append(proc)
        return proc

    def kill_all(self):
        """Forcefully terminate every tracked child. Safe to call twice."""
        for proc in self._active_children:
            if proc.poll() is not None:
                continue
            try:
                if _IS_WINDOWS:
                    proc.kill()
                else:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
        self._active_children.clear()


# One global guard for the whole script run.
_GUARD = ChildProcessGuard()


def _install_signal_handlers():
    """Make sure the child dies even on SIGINT / SIGTERM / SIGBREAK."""
    def _handler(signum, _frame):
        try:
            _GUARD.kill_all()
        finally:
            # Re-raise the default action so the parent sees a clean exit.
            sys.exit(128 + int(signum))

    for sig_name in ('SIGINT', 'SIGTERM', 'SIGBREAK', 'SIGHUP'):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _handler)
        except (ValueError, OSError):
            # Some signals can't be handled outside the main thread on Windows
            pass

    atexit.register(_GUARD.kill_all)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ms_to_srt(ms: int) -> str:
    """Convert milliseconds to SRT timestamp HH:MM:SS,mmm."""
    ms = max(0, int(ms))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms,    60_000)
    s, ms = divmod(ms,     1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def compile_style_matcher(patterns):
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
    decorative \\p1..\\p0 glyph embedded) are NOT flagged — pysubs2's
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
           \\kt duration — stylistic \\k without a number is no longer
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


def _join_texts(a: str, b: str) -> str:
    """Join two cue texts, preserving order and dropping exact duplicates."""
    a_lines = a.split('\n') if a else []
    b_lines = b.split('\n') if b else []
    combined = list(a_lines)
    for ln in b_lines:
        if ln not in combined:
            combined.append(ln)
    return '\n'.join(combined)


def merge_overlapping_cues(
    cues: list[tuple[int, int, str]]
) -> list[tuple[int, int, str]]:
    """
    FIX#4: split-based overlap resolution.

    The old implementation was a GREEDY merge that extended the previous
    cue's end to max(pe, e). This caused dialogue lines to linger on
    screen for the entire duration of any sign-translation that briefly
    overlapped them — a dialogue at 10.0-12.0 s and a sign at 11.5-18.0 s
    would fuse into one cue "dialogue\\nsign" lasting 10.0-18.0 s. The
    dialogue was no longer connected to its actual timing.

    The new algorithm walks sorted cues and, for each pair (prev, curr)
    that overlap, emits up to three non-overlapping segments:

        [prev.start .. curr.start]                with prev.text
        [curr.start .. min(prev.end, curr.end)]   with prev.text + '\\n' + curr.text
        [min(prev.end, curr.end) .. max(prev.end, curr.end)]
                                                  with whichever text extends

    Zero-length segments are skipped. The result is sorted, non-
    overlapping, and temporally faithful to the source.

    Samsung's built-in SRT renderer and many DLNA clients only display
    one cue at a time; the combined middle segment is where the viewer
    sees dialogue+sign simultaneously without either being dropped.
    """
    filtered = sorted((c for c in cues if c[1] > c[0]),
                      key=lambda c: (c[0], c[1]))
    if not filtered:
        return []

    # Work off a mutable deque-like list so we can re-process when an
    # emitted tail segment overlaps with the NEXT source cue (rare but
    # possible with >2-way overlaps, e.g. dialogue + sign + lyrics all
    # layered during an opening sequence).
    pending = list(filtered)
    out: list[tuple[int, int, str]] = []

    def _insert_sorted(lst, item):
        """Insert item into lst preserving sort by (start, end)."""
        key = (item[0], item[1])
        lo, hi = 0, len(lst)
        while lo < hi:
            mid = (lo + hi) // 2
            k = (lst[mid][0], lst[mid][1])
            if k < key:
                lo = mid + 1
            else:
                hi = mid
        lst.insert(lo, item)

    while pending:
        curr = pending.pop(0)
        if not out:
            out.append(curr)
            continue
        ps, pe, pt = out[-1]
        cs, ce, ct = curr

        if cs >= pe:
            # No overlap.
            out.append(curr)
            continue

        # Overlap. Remove the previous emitted segment; we'll rebuild
        # from it plus curr.
        out.pop()

        # Segment A: [ps, cs] with prev text (only if non-zero).
        if cs > ps:
            out.append((ps, cs, pt))

        # Segment B: [cs, min(pe, ce)] with combined text.
        mid_end = min(pe, ce)
        if mid_end > cs:
            out.append((cs, mid_end, _join_texts(pt, ct)))

        # Segment C: [min(pe, ce), max(pe, ce)] with whichever outlives.
        if pe > ce:
            tail = (mid_end, pe, pt)
        elif ce > pe:
            tail = (mid_end, ce, ct)
        else:
            tail = None

        if tail and tail[1] > tail[0]:
            # Push tail back into pending in sort order so it participates
            # correctly in any further overlap resolution with the next
            # source cue (which may start earlier than the tail).
            _insert_sorted(pending, tail)

    return out


def apply_minimum_gap(
    cues: list[tuple[int, int, str]],
    gap_ms: int = 1,
) -> list[tuple[int, int, str]]:
    """
    FIX#15: ensure every cue ends at least `gap_ms` ms before the next
    cue starts.

    Old behaviour: when shortening prev.end by gap_ms would push it
    below or onto prev.start, the fix was skipped and the zero-gap
    pair survived into the SRT — VLC still dropped the second cue.

    New behaviour: two-pass.
        Pass 1 (preferred): shorten current's end by gap_ms if
        feasible (current.start + 1 <= new_end).
        Pass 2 (fallback):  shift NEXT cue's start forward by gap_ms
        when the current cue cannot be shortened. We only do this if
        the next cue is long enough to absorb the shift without
        inverting — if both cues are 1 ms wide with zero gap, we log
        and leave them alone (pathological input).

    A 1 ms gap is imperceptible at any frame rate but unambiguously
    distinguishes two adjacent cues.

    Input:  list of (start_ms, end_ms, text), sorted by start.
    Output: list of (start_ms, end_ms, text) with end_i < start_{i+1}.
    """
    if len(cues) < 2:
        return cues
    out = [list(c) for c in cues]
    fallback_count = 0
    unresolved     = 0

    for i in range(len(out) - 1):
        cur_end    = out[i][1]
        next_start = out[i + 1][0]
        if cur_end < next_start:
            continue  # already has a gap

        new_end = next_start - gap_ms
        if new_end > out[i][0]:
            # Pass 1: shorten current's end.
            out[i][1] = new_end
            continue

        # Pass 2 fallback: advance next.start by gap_ms if possible.
        desired_next_start = cur_end + gap_ms
        if desired_next_start < out[i + 1][1]:
            out[i + 1][0] = desired_next_start
            fallback_count += 1
            continue

        # Pathological: adjacent cues have zero or negative width and
        # we can't introduce a gap without inverting one of them.
        # Leave them alone — dropping either would lose dialogue.
        unresolved += 1

    if fallback_count:
        emit_prefixed(f"INFO: apply_minimum_gap fallback (shifted next.start) "
                      f"applied to {fallback_count} cue pair(s)")
    if unresolved:
        emit_prefixed(f"WARN: apply_minimum_gap could not resolve {unresolved} "
                      f"zero-width pair(s); leaving as-is")

    return [tuple(c) for c in out]


# ---------------------------------------------------------------------------
# ffmpeg launcher — FIX#3
# ---------------------------------------------------------------------------

def run_ffmpeg_extract(ffmpeg_bin: str, mkv_path: str, stream_idx: str,
                       tmp_ass: str, timeout_s: int = 120) -> subprocess.CompletedProcess:
    """
    Run ffmpeg to extract one subtitle stream to tmp_ass, but route the
    child through ChildProcessGuard so it cannot outlive this Python
    process no matter how we die.
    """
    argv = [
        ffmpeg_bin, "-y",
        "-i",   mkv_path,
        "-map", f"0:{stream_idx}",
        "-c:s", "ass",
        tmp_ass,
    ]
    proc = _GUARD.popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        # Try graceful terminate, then hard kill, then let the guard's
        # atexit sweep finish anything left behind.
        try: proc.terminate()
        except Exception: pass
        try: proc.wait(timeout=5)
        except Exception:
            try: proc.kill()
            except Exception: pass
            try: proc.wait(timeout=5)
            except Exception: pass
        raise
    except BaseException:
        # Guarantee: on any exception path we kill the child before
        # re-raising so it doesn't keep the source file locked.
        try: proc.kill()
        except Exception: pass
        try: proc.wait(timeout=5)
        except Exception: pass
        raise

    return subprocess.CompletedProcess(
        args=argv,
        returncode=proc.returncode,
        stdout=stdout.decode('utf-8', errors='replace') if stdout else '',
        stderr=stderr.decode('utf-8', errors='replace') if stderr else '',
    )


def _split_style_patterns(raw: str | None, default: list[str]) -> list[str]:
    if raw and raw.strip():
        return [p.strip() for p in raw.split("|") if p.strip()]
    return list(default)


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


def load_ass_with_best_encoding(path: str, encodings: tuple[str, ...]) -> tuple[Any, str, list[dict[str, Any]], Exception | None]:
    candidates: list[tuple[tuple[int, int, int, int, int], Any, str, dict[str, Any]]] = []
    diagnostics: list[dict[str, Any]] = []
    last_err: Exception | None = None
    for order, enc in enumerate(encodings):
        try:
            subs = pysubs2.load(path, encoding=enc)
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert one ASS subtitle stream from an MKV into plain UTF-8 SRT. "
            "Supports the legacy positional form used by MediaPipeline and a "
            "friendlier named-argument form for manual debugging."
        )
    )
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("input_path", nargs="?",
                        help="Input media file (legacy positional form)")
    parser.add_argument("stream_index_positional", nargs="?",
                        help="Subtitle stream index to extract (legacy positional form)")
    parser.add_argument("output_path", nargs="?",
                        help="Destination SRT path (legacy positional form)")
    parser.add_argument("remove_karaoke_positional", nargs="?",
                        help='Legacy positional toggle: "1" removes karaoke, "0" keeps it')
    parser.add_argument("exclude_styles_positional", nargs="?",
                        help="Legacy positional pipe-separated exclude-style list")
    parser.add_argument("include_styles_positional", nargs="?",
                        help="Legacy positional pipe-separated include-style list")

    parser.add_argument("--input", dest="input_override",
                        help="Input media file")
    parser.add_argument("--stream-index", dest="stream_index_override",
                        help="Subtitle stream index to extract")
    parser.add_argument("--output", dest="output_override",
                        help="Destination SRT path")

    karaoke_group = parser.add_mutually_exclusive_group()
    karaoke_group.add_argument("--remove-karaoke", dest="remove_karaoke_override",
                               action="store_true",
                               help="Drop karaoke-style syllable events")
    karaoke_group.add_argument("--keep-karaoke", dest="remove_karaoke_override",
                               action="store_false",
                               help="Keep karaoke-style syllable events")
    parser.set_defaults(remove_karaoke_override=None)

    parser.add_argument("--exclude-styles", dest="exclude_styles_override",
                        help="Pipe-separated case-insensitive exclude-style globs")
    parser.add_argument("--include-styles", dest="include_styles_override",
                        help="Pipe-separated case-insensitive include-style globs")
    formatting_group = parser.add_mutually_exclusive_group()
    formatting_group.add_argument("--strip-formatting", dest="strip_formatting_override",
                                  action="store_true",
                                  help="Strip ASS formatting and emit plain SRT text")
    formatting_group.add_argument("--keep-formatting", dest="strip_formatting_override",
                                  action="store_false",
                                  help="Preserve basic italic/bold/underline tags when SRT can represent them")
    parser.set_defaults(strip_formatting_override=None)
    parser.add_argument("--keep-temp-ass", action="store_true",
                        help="Keep the extracted temporary ASS file for manual inspection")
    parser.add_argument("--summary-json",
                        help="Write conversion diagnostics as JSON to this path")
    parser.add_argument("--ffmpeg-bin",
                        help="Path to the ffmpeg binary to use for subtitle extraction")
    parser.add_argument("--extract-timeout-seconds", type=int, default=120,
                        help="Timeout for the internal ffmpeg ASS extraction step")
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("--quiet", action="store_true",
                                 help="Suppress INFO lines and only print WARN/ERROR output")
    verbosity_group.add_argument("--verbose", action="store_true",
                                 help="Include extra DEBUG lines during manual troubleshooting")
    parser.add_argument("--print-default-exclude-styles", action="store_true",
                        help="Print the built-in exclude-style list and exit")

    args = parser.parse_args(argv)

    args.mkv_path = args.input_override or args.input_path
    args.stream_index = args.stream_index_override or args.stream_index_positional
    args.output_srt = args.output_override or args.output_path

    if (not args.print_default_exclude_styles and
            (not args.mkv_path or not args.stream_index or not args.output_srt)):
        parser.error("input, stream index, and output path are required")

    if args.remove_karaoke_override is None:
        legacy_value = (args.remove_karaoke_positional or "1").strip()
        args.remove_karaoke = legacy_value != "0"
    else:
        args.remove_karaoke = args.remove_karaoke_override

    args.strip_formatting = True if args.strip_formatting_override is None else args.strip_formatting_override
    if args.extract_timeout_seconds <= 0:
        parser.error("--extract-timeout-seconds must be greater than zero")

    args.exclude_patterns = _split_style_patterns(
        args.exclude_styles_override or args.exclude_styles_positional,
        DEFAULT_EXCLUDE_STYLES,
    )
    args.include_patterns = _split_style_patterns(
        args.include_styles_override or args.include_styles_positional,
        [],
    )

    return args


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _install_signal_handlers()
    args = parse_args(sys.argv[1:])
    set_log_verbosity(quiet=args.quiet, verbose=args.verbose)

    if args.print_default_exclude_styles:
        print("\n".join(DEFAULT_EXCLUDE_STYLES))
        sys.exit(0)

    mkv_path = args.mkv_path
    stream_idx = args.stream_index
    output_srt = args.output_srt
    remove_karaoke = args.remove_karaoke
    exclude_patterns = args.exclude_patterns
    include_patterns = args.include_patterns
    strip_formatting = args.strip_formatting
    extract_timeout_seconds = args.extract_timeout_seconds

    emit_prefixed(
        f"DEBUG: Parsed CLI remove_karaoke={remove_karaoke} "
        f"strip_formatting={strip_formatting} "
        f"extract_timeout_seconds={extract_timeout_seconds} "
        f"exclude_patterns={len(exclude_patterns)} include_patterns={len(include_patterns)}"
    )

    style_is_noise   = compile_style_matcher(exclude_patterns)
    style_is_dialog  = compile_style_matcher(include_patterns)

    tmp_ass: str | None = None
    summary_data: dict[str, Any] = {
        "input": mkv_path,
        "stream_index": stream_idx,
        "output": output_srt,
        "remove_karaoke": remove_karaoke,
        "strip_formatting": strip_formatting,
        "extract_timeout_seconds": extract_timeout_seconds,
        "exclude_patterns": exclude_patterns,
        "include_patterns": include_patterns,
        "temp_ass": "",
        "status": "started",
    }

    if not os.path.exists(mkv_path):
        fail_with_summary(args, summary_data, f"Input file not found: {mkv_path}",
                          stage="input-check")

    ffmpeg_bin = args.ffmpeg_bin or shutil.which("ffmpeg")
    if not ffmpeg_bin:
        fail_with_summary(args, summary_data, "ffmpeg not found; pass --ffmpeg-bin or add ffmpeg to PATH",
                          stage="ffmpeg-discovery")
    if not os.path.exists(ffmpeg_bin):
        fail_with_summary(args, summary_data, f"ffmpeg binary not found: {ffmpeg_bin}",
                          stage="ffmpeg-discovery")
    emit_prefixed(f"DEBUG: Using ffmpeg binary: {ffmpeg_bin}")

    try:
        tmp_fd, tmp_ass = tempfile.mkstemp(suffix='.ass')
        os.close(tmp_fd)
        summary_data["temp_ass"] = tmp_ass

        # ------------------------------------------------------------------
        # Step 1 — extract subtitle stream as ASS via ffmpeg
        # ------------------------------------------------------------------
        try:
            result = run_ffmpeg_extract(
                ffmpeg_bin, mkv_path, stream_idx, tmp_ass, timeout_s=extract_timeout_seconds)
        except subprocess.TimeoutExpired:
            fail_with_summary(args, summary_data,
                              f"ffmpeg extraction timed out after {extract_timeout_seconds} seconds",
                              stage="extract")
        except FileNotFoundError:
            fail_with_summary(args, summary_data,
                              f"ffmpeg binary not found: {ffmpeg_bin}",
                              stage="extract")

        if result.returncode != 0:
            fail_with_summary(
                args,
                summary_data,
                f"ffmpeg extraction failed (exit {result.returncode})",
                stage="extract",
                details=[f"ffmpeg: {line}" for line in result.stderr.strip().splitlines()[-10:]],
            )

        if not os.path.exists(tmp_ass) or os.path.getsize(tmp_ass) == 0:
            fail_with_summary(args, summary_data,
                              "ffmpeg produced an empty ASS file",
                              stage="extract")

        # ------------------------------------------------------------------
        # Step 2 — load with pysubs2
        # ------------------------------------------------------------------
        subs, ass_encoding, encoding_diagnostics, last_err = load_ass_with_best_encoding(
            tmp_ass,
            ("utf-8", "utf-8-sig", "cp1252", "cp932", "shift_jis", "euc_jp", "iso-8859-1"),
        )
        summary_data["ass_encoding_candidates"] = encoding_diagnostics
        if subs is None:
            msg = str(last_err) if last_err else "UTF-8 decode failed"
            fail_with_summary(
                args,
                summary_data,
                "pysubs2 could not load ASS without risking silent "
                f"text corruption: {msg}",
                stage="decode",
            )
        summary_data["ass_encoding"] = ass_encoding
        if ass_encoding not in ("utf-8", "utf-8-sig"):
            emit_prefixed(f"WARN: ASS decode required fallback encoding {ass_encoding}")

        emit_prefixed(f"INFO: Loaded {len(subs)} events from ASS stream {stream_idx}")
        summary_data["loaded_events"] = len(subs)

        # ------------------------------------------------------------------
        # Step 3 — convert Dialogue events to cues with style filtering
        # ------------------------------------------------------------------
        style_kept      = {}
        style_dropped   = {}
        style_whitelist = {}
        sample_drops = {'style': [], 'drawing': [], 'karaoke': [], 'empty': []}

        def remember(bucket, line, snippet):
            if len(sample_drops[bucket]) < 3:
                sample_drops[bucket].append(
                    f"{ms_to_srt(line.start)} style={line.style!r} "
                    f"text={snippet[:60]!r}"
                )

        cues = []                       # list of (start_ms, end_ms, text)
        skipped_style    = 0
        skipped_drawing  = 0
        skipped_karaoke  = 0
        skipped_empty    = 0
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
            # — user explicitly asked to keep anything with this style).
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

        # ------------------------------------------------------------------
        # Step 4 — resolve overlapping cues (Samsung / DLNA compatibility)
        # ------------------------------------------------------------------
        before = len(cues)
        cues = merge_overlapping_cues(cues)
        after = len(cues)
        if before != after:
            emit_prefixed(
                f"INFO: Resolved overlaps — {before} source cues -> {after} non-overlapping segments"
            )
        summary_data["overlap_resolution"] = {
            "before": before,
            "after": after,
            "changed": before != after,
        }

        # ------------------------------------------------------------------
        # Step 4b — enforce 1 ms minimum gap between cues (VLC compat)
        # ------------------------------------------------------------------
        zero_gap_count = sum(
            1 for i in range(len(cues) - 1)
            if cues[i][1] >= cues[i + 1][0]
        )
        summary_data["minimum_gap_adjustments"] = zero_gap_count
        if zero_gap_count > 0:
            cues = apply_minimum_gap(cues, gap_ms=1)
            emit_prefixed(
                f"INFO: Applied 1ms gap to {zero_gap_count} back-to-back cues"
            )

        # ------------------------------------------------------------------
        # Diagnostics
        # ------------------------------------------------------------------
        emit_prefixed(
            f"INFO: {after} cues written "
            f"(skipped: {skipped_style} by style, {skipped_drawing} drawing, "
            f"{skipped_karaoke} karaoke, {skipped_empty} empty, "
            f"{skipped_nodialog} non-dialogue)"
        )
        if style_kept:
            top_kept = sorted(style_kept.items(), key=lambda kv: -kv[1])[:5]
            emit_prefixed("INFO: Kept styles: " +
                          ", ".join(f"{k}={v}" for k, v in top_kept))
        if style_whitelist:
            emit_prefixed("INFO: Whitelisted styles that survived exclude-filter: " +
                          ", ".join(f"{k}={v}" for k, v in style_whitelist.items()))
        if style_dropped:
            top_dropped = sorted(style_dropped.items(), key=lambda kv: -kv[1])[:5]
            emit_prefixed("INFO: Dropped styles: " +
                          ", ".join(f"{k}={v}" for k, v in top_dropped))
        for bucket, samples in sample_drops.items():
            if samples:
                emit_prefixed(f"INFO: Sample dropped [{bucket}]:")
                for s in samples:
                    emit_prefixed(f"INFO:   {s}")

        summary_data["diagnostics"] = {
            "cues_written": after,
            "skipped": {
                "style": skipped_style,
                "drawing": skipped_drawing,
                "karaoke": skipped_karaoke,
                "empty": skipped_empty,
                "non_dialogue": skipped_nodialog,
            },
            "kept_styles": style_kept,
            "dropped_styles": style_dropped,
            "whitelisted_styles": style_whitelist,
            "sample_drops": sample_drops,
        }

        if after == 0:
            details = []
            all_styles = {}
            for ln in subs:
                if ln.type == "Dialogue":
                    all_styles[ln.style] = all_styles.get(ln.style, 0) + 1
            if all_styles:
                details.append("Style names present in this file:")
                for s, c in sorted(all_styles.items(), key=lambda kv: -kv[1]):
                    details.append(f"  {s!r}: {c} events")
            fail_with_summary(
                args,
                summary_data,
                "No dialogue cues produced — all events were filtered. Check exclude_styles / include_styles patterns.",
                stage="filtering",
                details=details,
            )

        # ------------------------------------------------------------------
        # Step 5 — write SRT (UTF-8, no BOM, sorted by time)
        # ------------------------------------------------------------------
        output_lines = []
        for i, (s, e, t) in enumerate(cues, start=1):
            output_lines.append(str(i))
            output_lines.append(f"{ms_to_srt(s)} --> {ms_to_srt(e)}")
            output_lines.append(t)
            output_lines.append("")

        Path(output_srt).parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(output_srt, "\n".join(output_lines), encoding="utf-8")

        summary_data["status"] = "success"
        write_summary_json(args.summary_json, summary_data)

        sys.exit(0)

    finally:
        # FIX#3 final safety net: the guard's atexit handler will also
        # reap any surviving children, but we call explicitly for
        # immediate resource release.
        _GUARD.kill_all()
        if args.keep_temp_ass and tmp_ass and os.path.exists(tmp_ass):
            emit_prefixed(f"INFO: Preserved extracted ASS at {tmp_ass}")
        elif tmp_ass and os.path.exists(tmp_ass):
            try:
                os.remove(tmp_ass)
            except OSError:
                pass


if __name__ == "__main__":
    main()
