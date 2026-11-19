"""The application icon: the shield mark on the hero tile, drawn at any size.

The window icon at run time and the ``.ico`` of the Windows build both come
from here, so they cannot drift apart. The colours are fixed (dark tile, ivory
mark) instead of following the theme: an app icon is recognised by not changing.
Small sizes get a simpler mark with a thicker line, so it still reads at 16 px.
"""
from __future__ import annotations

import struct

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap

try:
    from PySide6.QtSvg import QSvgRenderer
except ImportError:  # pragma: no cover - QtSvg ships with PySide6 Essentials
    QSvgRenderer = None

TILE = "#1A1F2A"     # dark SURFACE_2, like the hero tile on the splash
BORDER = "#2C3342"   # dark BORDER_DEFAULT
MARK = "#EADFC8"     # ivory ACCENT
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)

_SHIELD = "M12 2.5l8 3.2v5.8c0 5-3.4 9-8 10.5-4.6-1.5-8-5.5-8-10.5V5.7z"


def icon_svg(size: int) -> str:
    """The icon as SVG (24-unit canvas), tuned for ``size`` pixels."""
    small = size < 32
    scale = 0.8 if small else 0.7
    unit = size / 24                                   # pixels per canvas unit
    stroke = max(1.25, size * 0.045) / (scale * unit)  # line width in mark units
    radius = 4.6 if small else 5.4
    if size >= 48:  # a hairline border, kept inside the canvas
        inset = 12 / size
        edge = f' stroke="{BORDER}" stroke-width="{24 / size:.4f}"'
    else:
        inset, edge = 0.0, ""
    if small:
        mark = f'<path d="{_SHIELD}"/><circle cx="12" cy="11" r="2.6" fill="{MARK}" stroke="none"/>'
    else:
        mark = f'<path d="{_SHIELD}"/><circle cx="12" cy="10.5" r="2.2"/><path d="M12 12.7V16"/>'
    side = 24 - 2 * inset
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<rect x="{inset:.4f}" y="{inset:.4f}" width="{side:.4f}" height="{side:.4f}" rx="{radius}" '
        f'fill="{TILE}"{edge}/>'
        f'<g transform="translate(12 12) scale({scale}) translate(-12 -12.25)" fill="none" stroke="{MARK}" '
        f'stroke-width="{stroke:.3f}" stroke-linecap="round" stroke-linejoin="round">{mark}</g>'
        '</svg>')


def render(size: int) -> QImage:
    """The icon as a ``size`` x ``size`` image with a transparent background."""
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    if QSvgRenderer is not None:
        renderer = QSvgRenderer(QByteArray(icon_svg(size).encode("utf-8")))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
    return image


def app_icon() -> QIcon:
    """Every size in one QIcon, so title bars and the taskbar pick a sharp one."""
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(QPixmap.fromImage(render(size)))
    return icon


def _png(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    data = bytes(buffer.data())
    buffer.close()
    return data


def ico_bytes(sizes: tuple[int, ...] = SIZES) -> bytes:
    """A Windows .ico holding one PNG per size (supported since Windows Vista)."""
    images = [(size, _png(render(size))) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = [], []
    for size, data in images:
        side = 0 if size >= 256 else size   # 0 means 256 in an icon directory
        entries.append(struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset))
        blobs.append(data)
        offset += len(data)
    return header + b"".join(entries) + b"".join(blobs)
