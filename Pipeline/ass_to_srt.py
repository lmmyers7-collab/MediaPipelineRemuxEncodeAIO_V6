#!/usr/bin/env python3
"""
ass_to_srt.py  —  Convert one ASS subtitle stream from an MKV to plain SRT.

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
    python3 ass_to_srt.py <input.mkv> <stream_index> <output.srt>
                          [remove_karaoke] [exclude_styles] [include_styles]

    python3 ass_to_srt.py --input <input.mkv> --stream-index <stream_index>
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
import shutil
import signal
import subprocess
import tempfile
import atexit
from pathlib import Path
from typing import Any, Dict, List, Optional

_HELPER_DIR = Path(__file__).with_suffix("")
if _HELPER_DIR.is_dir():
    __path__ = [str(_HELPER_DIR)]
    sys.modules.setdefault("ass_to_srt", sys.modules[__name__])

from ass_to_srt.ass_events import (  # noqa: E402
    _ass_dialogue_stats,
    collect_dialogue_cues,
    load_ass_with_best_encoding as _load_ass_with_best_encoding,
)
from ass_to_srt.log import emit_prefixed, set_log_verbosity  # noqa: E402
from ass_to_srt.srt import (  # noqa: E402
    _join_texts,
    apply_minimum_gap,
    merge_overlapping_cues,
    render_srt,
)
from ass_to_srt.styles import (  # noqa: E402
    DEFAULT_EXCLUDE_STYLES,
    KARAOKE_TAG_RE,
    SENTENCE_PUNCT_RE,
    _KARAOKE_STYLE_HINTS,
    _split_style_patterns,
    compile_style_matcher,
    is_pure_drawing_event,
    looks_like_karaoke_syllable,
)
from ass_to_srt.text import (  # noqa: E402
    ASS_BASIC_FORMAT_TAG_RE,
    ASS_OVERRIDE_BLOCK_RE,
    HTML_TAG_RE,
    SRT_BASIC_FORMAT_TAG_RE,
    WEIRD_SPACE_RE,
    _DRAWING_CMD_CHARS,
    _NUMBER_RE,
    ass_override_block_to_srt_markup,
    clean_text,
    looks_like_drawing_line,
    render_ass_text_for_srt,
    sanitize_srt_markup,
)
from ass_to_srt.timing import ms_to_srt  # noqa: E402

try:
    import pysubs2
except ImportError:
    print("ERROR: pysubs2 not installed. Run: pip install pysubs2", file=sys.stderr)
    sys.exit(2)


__version__ = "1.0"


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


def load_ass_with_best_encoding(path: str, encodings: tuple[str, ...]) -> tuple[Any, str, list[dict[str, Any]], Exception | None]:
    return _load_ass_with_best_encoding(path, encodings, pysubs2)


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
        dialogue_result = collect_dialogue_cues(
            subs,
            style_is_noise=style_is_noise,
            style_is_dialog=style_is_dialog,
            remove_karaoke=remove_karaoke,
            strip_formatting=strip_formatting,
        )
        cues = dialogue_result["cues"]
        skipped_style = dialogue_result["skipped_style"]
        skipped_drawing = dialogue_result["skipped_drawing"]
        skipped_karaoke = dialogue_result["skipped_karaoke"]
        skipped_empty = dialogue_result["skipped_empty"]
        skipped_nodialog = dialogue_result["skipped_nodialog"]
        style_kept = dialogue_result["style_kept"]
        style_dropped = dialogue_result["style_dropped"]
        style_whitelist = dialogue_result["style_whitelist"]
        sample_drops = dialogue_result["sample_drops"]

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
        Path(output_srt).parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(output_srt, render_srt(cues), encoding="utf-8")

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
