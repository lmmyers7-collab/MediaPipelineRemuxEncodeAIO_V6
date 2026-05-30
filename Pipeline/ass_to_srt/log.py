import re
import sys


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
