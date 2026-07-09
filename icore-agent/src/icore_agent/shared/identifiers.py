"""Shared domain identifier generation."""

from __future__ import annotations

import secrets
import threading
import time
import uuid

_LOCK = threading.Lock()
_LAST_MS = 0
_COUNTER = 0


def uuid7() -> uuid.UUID:
    """Generate a monotonic UUIDv7 value without relying on PostgreSQL support."""
    global _LAST_MS, _COUNTER
    with _LOCK:
        now_ms = int(time.time() * 1000)
        if now_ms <= _LAST_MS:
            now_ms = _LAST_MS
            _COUNTER = (_COUNTER + 1) & 0xFFF
            if _COUNTER == 0:
                now_ms += 1
        else:
            _COUNTER = 0
        _LAST_MS = now_ms
        rand_a = _COUNTER

    rand_b = secrets.randbits(62)
    value = (now_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return uuid.UUID(int=value)
