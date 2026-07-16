"""Lightweight per-image trace logger.

Stages call ``trace.log(section, message, data)`` at each decision point; when a trace is active
(started by the pipeline for one image) the entries are buffered and dumped to
``<image-name>-log.txt``. When inactive, every call is a cheap no-op, so the instrumentation has
no effect on normal runs.
"""
import json
import time
from dataclasses import asdict, is_dataclass

_active = None  # list[str] while a trace is running, else None


def start(header: str = ""):
    global _active
    _active = []
    if header:
        log("START", header)


def is_active() -> bool:
    return _active is not None


def _fmt(data) -> str:
    if data is None:
        return ""
    try:
        if is_dataclass(data):
            data = asdict(data)
        if isinstance(data, (dict, list)):
            return json.dumps(data, indent=2, default=str, ensure_ascii=False)
    except Exception:
        pass
    return str(data)


def log(section: str, message: str = "", data=None):
    """Record one trace entry (no-op unless a trace is active)."""
    if _active is None:
        return
    ts = time.strftime("%H:%M:%S")
    _active.append(f"[{ts}] {section}: {message}".rstrip())
    if data is not None:
        body = _fmt(data)
        if body:
            _active.append("\n".join("    " + ln for ln in body.splitlines()))


def dump(path: str):
    """Write the buffered trace to a file (best-effort)."""
    if _active is None:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(_active) + "\n")
    except Exception:
        pass


def stop():
    global _active
    _active = None
