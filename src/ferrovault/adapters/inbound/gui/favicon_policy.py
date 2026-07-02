"""Qt-free favicon policy helpers."""
from __future__ import annotations

import os


def network_favicons_enabled() -> bool:
    """Return whether GUI favicon downloads are explicitly allowed."""

    return os.environ.get("AEGISVAULT_FETCH_FAVICONS", "").strip().lower() in {"1", "true", "yes", "on"}


def background_favicon_prefetch_enabled() -> bool:
    """Return whether cached/online favicons may be warmed in a background worker."""

    return os.environ.get("AEGISVAULT_PREFETCH_FAVICONS", "").strip().lower() in {"1", "true", "yes", "on"}


def favicon_prefetch_limit(default: int = 80) -> int:
    """Small safety cap for background favicon warmup."""

    raw = os.environ.get("AEGISVAULT_FAVICON_PREFETCH_LIMIT", "").strip()
    try:
        return max(0, min(500, int(raw))) if raw else default
    except ValueError:
        return default
