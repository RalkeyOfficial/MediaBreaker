"""
A simple stylistic logger function

usage example:
```
import logging
from log import setup_logging, get_logger, logging_group

setup_logging(logging.INFO)
log = get_logger(__name__)

log.info("App started")

with logging_group("Checking dependencies", log):
    log.info("python-docx: OK")
    log.warning("zstd: missing, continuing without it")

with logging_group("Downloading playlist", log):
    log.info("Fetching master.m3u8")
    with logging_group("Parsing", log):
        log.info("Found 4 variants")
    log.error("Segment 12 failed")
    raise SystemExit(1)
```
```
import logging
from log import setup_logging, get_logger, logging_group

setup_logging(logging.INFO)
log = get_logger(__name__)

log.info("App started")

@logging_grouped("Checking dependencies", log)
def check_dependencies():
    log.info("python-docx: OK")
    log.warning("zstd: missing, continuing without it")

@logging_grouped("Downloading playlist", log)
def download_playlist():
    log.info("Fetching master.m3u8")
    with logging_group("Parsing", log):
        log.info("Found 4 variants")
    log.error("Segment 12 failed")
    raise SystemExit(1)
```

output example:
```
[    INFO    ] |  App started
[    INFO    ] |  Checking dependencies
[    INFO    ] |    python-docx: OK
[  WARNING   ] |    zstd: missing, continuing without it
[    INFO    ] |  Downloading playlist
[    INFO    ] |    Fetching master.m3u8
[    INFO    ] |    Parsing
[    INFO    ] |      Found 4 variants
[   ERROR    ] |    Segment 12 failed
```
"""

from __future__ import annotations

import logging
import os
import sys
import contextvars
import functools
from contextlib import contextmanager
from typing import Optional

_indent = contextvars.ContextVar("log_indent", default=0)

SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")


def success(self: logging.Logger, msg: str, *args, **kwargs) -> None:
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, msg, args, **kwargs)


logging.Logger.success = success  # type: ignore[attr-defined]


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\x1b[90m",
        logging.INFO: "\x1b[37m",
        SUCCESS: "\x1b[32m",
        logging.WARNING: "\x1b[33m",
        logging.ERROR: "\x1b[31m",
        logging.CRITICAL: "\x1b[31;1m",
    }
    RESET = "\x1b[0m"

    def __init__(self, use_color: bool, indent_spaces: int = 2):
        super().__init__(fmt="%(message)s")
        self.use_color = use_color
        self.indent_spaces = indent_spaces

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname.center(10)
        msg = record.getMessage()

        # Indent: applies to the whole line after the tag
        indent_level = _indent.get()
        indent = " " * (indent_level * self.indent_spaces)

        if self.use_color:
            color = self.COLORS.get(record.levelno, "")
            level = f"{color}{level}{self.RESET}"

        # If messages contain newlines, indent subsequent lines too
        msg_lines = msg.splitlines() or [""]
        msg_lines = [msg_lines[0]] + [indent + line for line in msg_lines[1:]]
        msg = "\n".join(msg_lines)

        return f"[{level}] |  {indent}{msg}"


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    no_color = os.getenv("NO_COLOR") is not None
    use_color = (sys.stderr.isatty() or sys.stdout.isatty()) and not no_color

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(ColorFormatter(use_color=use_color))
    root.addHandler(handler)


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or "app")


@contextmanager
def logging_group(title: str, logger: logging.Logger | None = None, level: int = logging.INFO):
    """
    Usage:
        with group("Downloading", log):
            log.info("Step 1")
            ...
    """
    log = logger or logging.getLogger("app")

    if title:
        log.log(level, title)

    token = _indent.set(_indent.get() + 1)
    try:
        yield
    finally:
        _indent.reset(token)


def logging_grouped(title: str | None = None,
                    logger: logging.Logger | None = None,
                    level: int = logging.INFO):
    """
    Decorate a function so its entire execution runs under a log group.
    """

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            log = logger or kwargs.get("logger") or logging.getLogger(fn.__module__)
            group_title = title or fn.__name__
            with logging_group(group_title, log, level=level):
                return fn(*args, **kwargs)

        return wrapper

    return deco


def logging_start_group(
        title: str,
        logger: Optional[logging.Logger] = None,
        level: int = logging.INFO,
):
    """
    Like console.group(): prints title, then increases indent.
    Returns a token you must pass to end_group().
    """
    log = logger or logging.getLogger("app")
    if title:
        log.log(level, title)
    token = _indent.set(_indent.get() + 1)
    return token


def logging_end_group(token) -> None:
    """
    Like console.groupEnd(): restores indent using the token from start_group().
    """
    _indent.reset(token)
