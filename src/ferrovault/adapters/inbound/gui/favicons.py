"""Small favicon loader for the desktop GUI.

It resolves an entry URL to a cached web favicon, then falls back to a local
lettermark if the host is offline or the app has no network access.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap

from .favicon_policy import network_favicons_enabled

_MEM: dict[tuple[str, int], QPixmap] = {}
_NEGATIVE_MEM: dict[str, float] = {}
_NEGATIVE_TTL_SECONDS = 24 * 60 * 60


_BRAND_COLORS = {
    "binance": "#F0B90B",
    "github": "#24292F",
    "gitlab": "#FC6D26",
    "google": "#4285F4",
    "gmail": "#EA4335",
    "amazon": "#FF9900",
    "aws": "#FF9900",
    "microsoft": "#00A4EF",
    "azure": "#0078D4",
    "docker": "#2496ED",
    "cloudflare": "#F38020",
    "stripe": "#635BFF",
    "paypal": "#003087",
    "discord": "#5865F2",
    "slack": "#4A154B",
    "openai": "#10A37F",
    "vercel": "#111111",
    "netflix": "#E50914",
    "spotify": "#1DB954",
    "facebook": "#1877F2",
    "instagram": "#E4405F",
    "x": "#111111",
    "twitter": "#1DA1F2",
    "linkedin": "#0A66C2",
    "proton": "#6D4AFF",
}


def domain_from_url(url: str | None) -> str:
    """Return a normalized host from a URL-like string."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        host = urllib.parse.urlparse(raw).netloc.lower()
    except Exception:
        return ""
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    host = host.split(":", 1)[0].strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def favicon_icon(url: str | None, fallback: str, size: int = 34) -> QIcon:
    return QIcon(favicon_pixmap(url, fallback, size))


def favicon_pixmap(url: str | None, fallback: str, size: int = 40) -> QPixmap:
    domain = domain_from_url(url)
    key = (domain or fallback or "vault", size)
    if key in _MEM:
        return _MEM[key]

    pixmap = QPixmap()
    if domain:
        cached = _load_cached(domain, size)
        if cached is not None:
            pixmap = cached
        elif network_favicons_enabled() and not _recently_failed(domain):
            data = _download_favicon(domain)
            if data:
                _write_cache(domain, data)
                pixmap = _pixmap_from_data(data, size)
            else:
                _remember_failure(domain)

    if pixmap.isNull():
        pixmap = _fallback_pixmap(domain or fallback, fallback, size)

    _MEM[key] = pixmap
    return pixmap


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    path = root / "aegisvault" / "favicons"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(domain: str) -> Path:
    return _cache_dir() / (hashlib.sha1(domain.encode("utf-8")).hexdigest() + ".ico")


def _load_cached(domain: str, size: int) -> QPixmap | None:
    path = _cache_path(domain)
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        pix = QPixmap(str(path))
        if not pix.isNull():
            return _rounded(pix, size)
    except Exception:
        return None
    return None


def _write_cache(domain: str, data: bytes) -> None:
    try:
        _cache_path(domain).write_bytes(data)
    except Exception:
        pass


def _remember_failure(domain: str) -> None:
    if domain:
        _NEGATIVE_MEM[domain] = time.time()


def _recently_failed(domain: str) -> bool:
    failed_at = _NEGATIVE_MEM.get(domain)
    return bool(failed_at and time.time() - failed_at < _NEGATIVE_TTL_SECONDS)


def _download_favicon(domain: str) -> bytes | None:
    encoded = urllib.parse.quote(domain, safe="")
    sources = [
        f"https://www.google.com/s2/favicons?domain={encoded}&sz=64",
        f"https://icons.duckduckgo.com/ip3/{encoded}.ico",
    ]
    headers = {"User-Agent": "AegisVaultVault/0.1 favicon loader"}
    for source in sources:
        try:
            req = urllib.request.Request(source, headers=headers)
            with urllib.request.urlopen(req, timeout=0.35) as resp:
                data = resp.read(64_000)
                if len(data) > 80:
                    return data
        except Exception:
            continue
    return None


def _pixmap_from_data(data: bytes, size: int) -> QPixmap:
    pix = QPixmap()
    pix.loadFromData(data)
    return _rounded(pix, size) if not pix.isNull() else pix


def _brand_key(domain: str) -> str:
    parts = [p for p in domain.split(".") if p and p not in {"com", "net", "org", "io", "app", "dev", "es"}]
    return parts[-1] if parts else domain[:2]


def _fallback_pixmap(domain: str, fallback: str, size: int) -> QPixmap:
    key = _brand_key(domain.lower()) if domain else (fallback or "SV").lower()
    initials = _initials(key or fallback or "SV")
    color = _BRAND_COLORS.get(key, _color_from_text(key or fallback or "vault"))

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = pm.rect().adjusted(1, 1, -1, -1)
    path = QPainterPath()
    path.addRoundedRect(rect, size * 0.24, size * 0.24)
    painter.fillPath(path, QColor(color))
    painter.setPen(QColor("#FFFFFF" if color.lower() not in {"#f0b90b", "#ff9900"} else "#111827"))
    font = QFont("Inter")
    font.setBold(True)
    font.setPixelSize(max(11, int(size * 0.39)))
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignCenter, initials)
    painter.end()
    return pm


def _rounded(source: QPixmap, size: int) -> QPixmap:
    scaled = source.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(pm.rect().adjusted(1, 1, -1, -1), size * 0.24, size * 0.24)
    painter.setClipPath(path)
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()
    return pm


def _initials(text: str) -> str:
    tokens = [t for t in re.split(r"[^a-zA-Z0-9]+", text) if t]
    if not tokens:
        return "SV"
    if len(tokens) == 1:
        token = tokens[0]
        return token[:2].upper() if len(token) < 8 else token[0].upper()
    return (tokens[0][0] + tokens[1][0]).upper()


def _color_from_text(text: str) -> str:
    palette = ["#8B5CF6", "#06B6D4", "#10B981", "#F59E0B", "#EF4444", "#6366F1", "#EC4899"]
    digest = hashlib.sha1(text.encode("utf-8", "ignore")).digest()[0]
    return palette[digest % len(palette)]


def prefetch_favicon_files(urls, *, limit: int = 80, fetch: bool | None = None) -> dict[str, int]:
    """Warm favicon files without touching Qt pixmaps.

    This is safe to run in a background thread because it only normalizes URLs,
    checks/writes cache files, and optionally downloads the small favicon bytes.
    The GUI thread still creates QPixmap/QIcon objects later.
    """

    if fetch is None:
        fetch = network_favicons_enabled()
    seen: set[str] = set()
    checked = cached = downloaded = failed = 0
    for url in urls:
        if checked >= max(0, int(limit)):
            break
        domain = domain_from_url(url)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        checked += 1
        try:
            path = _cache_path(domain)
            if path.exists() and path.stat().st_size > 0:
                cached += 1
                continue
            if fetch and not _recently_failed(domain):
                data = _download_favicon(domain)
                if data:
                    _write_cache(domain, data)
                    downloaded += 1
                else:
                    _remember_failure(domain)
                    failed += 1
        except Exception:
            failed += 1
            _remember_failure(domain)
    return {"checked": checked, "cached": cached, "downloaded": downloaded, "failed": failed}
