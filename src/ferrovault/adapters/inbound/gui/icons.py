"""Line icons from the "Tinta y marfil" design, rendered crisp at any DPI.

Every glyph is the 24x24 path data of the design boards (1.75 px stroke,
round caps). ``icon()`` returns a QIcon and ``pixmap()`` a QPixmap, both drawn
at the screen's device-pixel ratio (at least 2x) so they stay sharp on HiDPI
displays. Unknown names return an empty icon instead of raising, so a typo
never takes a dialog down.
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap

from .theme import PALETTE

try:
    from PySide6.QtSvg import QSvgRenderer
    _HAVE_SVG = True
except ImportError:  # pragma: no cover - QtSvg ships with PySide6 Essentials
    _HAVE_SVG = False

_HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
         'stroke="currentColor" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">')

_SHIELD = '<path d="M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6z"/>'
_LINK = ('<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3'
         'a4 4 0 0 0 5.7 5.7l1-1"/>')
_STAR = ('<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>')

_PATHS = {
    # brand and navigation
    "logo": ('<path d="M12 2.5l8 3.2v5.8c0 5-3.4 9-8 10.5-4.6-1.5-8-5.5-8-10.5V5.7z"/>'
             '<circle cx="12" cy="10.5" r="2.2"/><path d="M12 12.7V16"/>'),
    "vault": ('<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="12" cy="12" r="3.5"/>'
              '<path d="M12 8.5V7M12 17v-1.5M8.5 12H7M17 12h-1.5"/>'),
    "vault-file": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="12" cy="12" r="3.5"/>',
    "folder": ('<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2h8.5A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 '
               '1.5h-15A1.5 1.5 0 0 1 3 17.5z"/>'),
    "star": _STAR,
    "shield": _SHIELD,
    "shield-check": _SHIELD + '<path d="M9 12l2 2 4-4"/>',
    "shield-lock": _SHIELD + '<circle cx="12" cy="11" r="2"/><path d="M12 13v3"/>',
    "users": ('<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/>'
              '<path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c1.9.7 3.1 2.4 3.5 5.2"/>'),
    "user-share": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/><path d="M10 11v5M14 11v5"/>',
    "settings": ('<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/>'
                 '<circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>'),
    "gauge": '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l4-6"/>',
    "theme": '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/>',
    # top bar actions
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "search-minus": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5M8.5 11h5"/>',
    "share": '<path d="M12 3v12M7 8l5-5 5 5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "sync": ('<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8M4 4v4h4M4 13a8 8 0 0 0 14.3 4.9L20 16M20 20v-4h-4"/>'),
    "more": ('<circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none"/>'
             '<circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/>'
             '<circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none"/>'),
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "unlock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 7.5-2"/>',
    # list
    "add": '<path d="M12 5v14M5 12h14"/>',
    "filter": '<path d="M4 5h16l-6 8v6l-4-2v-4z"/>',
    "sort": '<path d="M7 4v16M3 16l4 4 4-4M17 20V4M13 8l4-4 4 4"/>',
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    "chevron-up": '<path d="M6 15l6-6 6 6"/>',
    "chevron-left": '<path d="M15 6l-6 6 6 6"/>',
    "chevron-right": '<path d="M9 6l6 6-6 6"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    # detail
    "copy": ('<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 '
             '2v8a2 2 0 0 0 2 2h2"/>'),
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": ('<path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.6'
                'C3.8 8.4 2 12 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2"/>'),
    "external": ('<path d="M14 4h6v6M20 4l-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/>'),
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3M15 8l2 2"/>',
    "code": '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4"/>',
    "note": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
    "doc": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
    "card": '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M7 15h4"/>',
    "qr": '<path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4M9 9h2v2H9zM13 13h2v2h-2z"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2"/>',
    "clipboard": '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4V3h6v1M9 10h6M9 14h4"/>',
    "download": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "printer": ('<path d="M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 '
                '2h-2"/><rect x="7" y="14" width="10" height="7"/>'),
    # states
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.5v.01"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5M12 16v.01"/>',
    "warning": '<path d="M12 4L2.5 20h19z"/><path d="M12 10v4.5M12 17.5v.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "ban": '<path d="M5 5l14 14M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z"/>',
    "circle": '<circle cx="12" cy="12" r="7"/>',
    "spinner": '<path d="M12 3a9 9 0 1 0 9 9"/>',
    "link": _LINK,
    "link-broken": _LINK + '<path d="M3 3l18 18"/>',
    "wifi-off": ('<path d="M3 3l18 18M8.5 16.4a5 5 0 0 1 7 0M5 12.9a10 10 0 0 1 4.2-2.5M14.8 10.4A10 10 0 0 1 '
                 '19 12.9M2 9.4a15 15 0 0 1 3.6-2.5M12 20h.01"/>'),
    # tools and dialogs
    "chip": ('<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 1.5V4M15 1.5V4M9 20v2.5M15 20v2.5'
             'M1.5 9H4M1.5 15H4M20 9h2.5M20 15h2.5"/><rect x="9" y="9" width="6" height="6" rx="1"/>'),
    "shamir": ('<circle cx="12" cy="5" r="2.5"/><circle cx="5" cy="18" r="2.5"/><circle cx="19" cy="18" r="2.5"/>'
               '<path d="M11 7.2l-4.7 8.6M13 7.2l4.7 8.6M7.5 18h9"/>'),
    "timer": '<circle cx="12" cy="13" r="7"/><path d="M12 9.5V13l2.5 1.5M9.5 3h5"/>',
    "terminal": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 10l3 2-3 2M12.5 15H17"/>',
    "fingerprint": ('<path d="M8 11a4 4 0 1 1 8 0v2M6.5 15.5c1-1 1.5-2.5 1.5-4.5M12 11v4c0 2-.8 3.8-2 5'
                    'M16 13c0 3-.7 5.3-1.7 7M18.5 16.5c-.2 1.3-.5 2.5-1 3.5"/>'),
    "keyboard": ('<rect x="2.5" y="6" width="19" height="12" rx="2"/>'
                 '<path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>'),
    "heart": ('<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 '
              '1-1a5.5 5.5 0 0 0 0-7.8z"/>'),
    "inbox": ('<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 '
              '2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'),
}

# Filled variants (selected favourite).
_FILLED = {
    "star-filled": _STAR.replace("<path ", '<path fill="currentColor" '),
}

# Names used before the redesign keep working.
_ALIASES = {
    "rotate": "sync",
    "grid": "folder",
    "sliders": "settings",
    "plus": "add",
    "x": "close",
}


def has_icon(name: str) -> bool:
    name = _ALIASES.get(name, name)
    return name in _PATHS or name in _FILLED


def _svg(name: str, color: str, stroke: float) -> str | None:
    name = _ALIASES.get(name, name)
    body = _PATHS.get(name) or _FILLED.get(name)
    if body is None:
        return None
    return (_HEAD.format(w=stroke) + body + "</svg>").replace("currentColor", color)


def _ratio() -> float:
    app = QGuiApplication.instance()
    ratio = app.devicePixelRatio() if app is not None else 1.0
    return max(2.0, float(ratio))


@lru_cache(maxsize=1024)
def _render(name: str, color: str, size: int, stroke: float, ratio: float) -> QPixmap:
    svg = _svg(name, color, stroke)
    side = max(1, int(round(size * ratio)))
    pm = QPixmap(side, side)
    pm.fill(Qt.transparent)
    if svg is not None and _HAVE_SVG:
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, side, side))
        painter.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def pixmap(name: str, color: str | None = None, size: int = 20, stroke: float = 1.75) -> QPixmap:
    """The icon as a HiDPI pixmap of ``size`` logical pixels."""
    return _render(name, color or PALETTE.TEXT_PRIMARY, int(size), float(stroke), _ratio())


def icon(name: str, color: str | None = None, size: int = 20, stroke: float = 1.75) -> QIcon:
    """The icon as a QIcon; an unknown name gives an empty icon."""
    if not has_icon(name) or not _HAVE_SVG:
        return QIcon()
    return QIcon(pixmap(name, color, size, stroke))
