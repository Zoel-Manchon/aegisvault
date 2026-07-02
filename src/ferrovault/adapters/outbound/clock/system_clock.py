"""Clock adapter."""
from __future__ import annotations

from datetime import datetime, timezone


class SystemClock:
    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def now_unix(self) -> int:
        return int(datetime.now(timezone.utc).timestamp())
