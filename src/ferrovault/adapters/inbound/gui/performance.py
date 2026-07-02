"""Small performance helpers for the desktop GUI.

The helpers are intentionally dependency-free and disabled by default. Set
``AEGISVAULT_PROFILE_STARTUP=1`` when launching the GUI to print timings for
startup, unlock, and first render without adding visible UI noise for users.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


def profiling_enabled() -> bool:
    return os.environ.get("AEGISVAULT_PROFILE_STARTUP", "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class StartupProfiler:
    """Very small opt-in timer for diagnosing GUI startup slowness."""

    enabled: bool = field(default_factory=profiling_enabled)
    _origin: float = field(default_factory=time.perf_counter)
    _last: float = field(default_factory=time.perf_counter)

    def mark(self, label: str) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        delta = (now - self._last) * 1000
        total = (now - self._origin) * 1000
        print(f"[aegisvault-startup] {label}: +{delta:.1f} ms / {total:.1f} ms", flush=True)
        self._last = now

    @contextmanager
    def span(self, label: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        start = time.perf_counter()
        try:
            yield
        finally:
            now = time.perf_counter()
            total = (now - self._origin) * 1000
            print(f"[aegisvault-startup] {label}: {(now - start) * 1000:.1f} ms / {total:.1f} ms", flush=True)
            self._last = now


def background_health_warmup_enabled() -> bool:
    """Return whether the full vault health report may warm after first paint."""

    return os.environ.get("AEGISVAULT_DISABLE_HEALTH_WARMUP", "").strip().lower() not in {"1", "true", "yes", "on"}
