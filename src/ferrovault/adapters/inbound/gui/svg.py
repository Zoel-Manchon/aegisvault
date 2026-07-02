"""Hand-built SVG graphics: brand logo, empty state, and the blockchain view.

Rendered to QSvgWidget so they stay crisp at any size. Colours come from the
theme so the art matches the rest of the window.
"""
from __future__ import annotations

from html import escape

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvgWidgets import QSvgWidget

from .theme import ACCENT, BG, BORDER, DANGER, MUTED, PANEL, TEXT

# A hexagon (the architecture) with a 3-block chain inside (the ledger).
LOGO_SVG = f"""
<svg viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg">
  <path d="M48 8 L82 28 L82 68 L48 88 L14 68 L14 28 Z" fill="none"
        stroke="{ACCENT}" stroke-width="3" stroke-linejoin="round"/>
  <g stroke="{ACCENT}" stroke-width="2.4" fill="none">
    <line x1="48" y1="38" x2="48" y2="42"/>
    <line x1="48" y1="56" x2="48" y2="60"/>
    <rect x="40" y="24" width="16" height="14" rx="3"/>
    <rect x="40" y="42" width="16" height="14" rx="3"/>
    <rect x="40" y="60" width="16" height="14" rx="3"/>
  </g>
</svg>
"""


def _widget(svg: str, w: int, h: int) -> QSvgWidget:
    widget = QSvgWidget()
    widget.load(QByteArray(svg.encode("utf-8")))
    widget.setFixedSize(w, h)
    widget.setAttribute(Qt.WA_TranslucentBackground, True)
    widget.setStyleSheet("background: transparent; border: none;")
    return widget


def logo_widget(size: int = 72) -> QSvgWidget:
    return _widget(LOGO_SVG, size, size)


def empty_state_widget(size: int = 120) -> QSvgWidget:
    svg = f"""
    <svg viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg" opacity="0.35">
      <path d="M48 8 L82 28 L82 68 L48 88 L14 68 L14 28 Z" fill="none"
            stroke="{MUTED}" stroke-width="2.5" stroke-linejoin="round"/>
      <g stroke="{MUTED}" stroke-width="2" fill="none">
        <rect x="40" y="34" width="16" height="14" rx="3"/>
        <rect x="40" y="52" width="16" height="14" rx="3"/>
        <line x1="48" y1="48" x2="48" y2="52"/>
      </g>
    </svg>
    """
    return _widget(svg, size, size)


_COLORS = {"init": "#58a6ff", "add": ACCENT, "remove": DANGER}


def chain_flow_widget(blocks) -> QSvgWidget:
    """Render the audit ledger as a vertical chain of linked blocks."""
    W, H, GAP, PAD = 440, 56, 26, 12
    n = max(len(blocks), 1)
    total_h = PAD * 2 + n * H + (n - 1) * GAP
    parts = [f'<svg viewBox="0 0 {W + 2 * PAD} {total_h}" '
             f'xmlns="http://www.w3.org/2000/svg">']

    for i, b in enumerate(blocks):
        y = PAD + i * (H + GAP)
        color = _COLORS.get(b.action, MUTED)
        cx, cy = PAD + 28, y + H / 2
        # connector to the next block
        if i < len(blocks) - 1:
            ly = y + H
            parts.append(
                f'<line x1="{cx}" y1="{ly}" x2="{cx}" y2="{ly + GAP}" '
                f'stroke="{BORDER}" stroke-width="2"/>'
                f'<circle cx="{cx}" cy="{ly + GAP/2}" r="3" fill="{BORDER}"/>')
        # block card
        parts.append(
            f'<rect x="{PAD}" y="{y}" width="{W}" height="{H}" rx="10" '
            f'fill="{PANEL}" stroke="{BORDER}" stroke-width="1.5"/>')
        # index disc
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="14" fill="none" '
            f'stroke="{color}" stroke-width="2"/>'
            f'<text x="{cx}" y="{cy+4}" fill="{color}" font-size="12" '
            f'font-family="monospace" text-anchor="middle">{b.index}</text>')
        # action + detail
        parts.append(
            f'<text x="{PAD+54}" y="{y+24}" fill="{color}" font-size="13" '
            f'font-family="monospace" font-weight="bold">{escape(b.action)}</text>'
            f'<text x="{PAD+54}" y="{y+42}" fill="{TEXT}" font-size="12" '
            f'font-family="monospace">{escape(b.detail[:34])}</text>')
        # short hash, right aligned
        parts.append(
            f'<text x="{PAD+W-14}" y="{cy+4}" fill="{MUTED}" font-size="11" '
            f'font-family="monospace" text-anchor="end">{b.hash[:16]}…</text>')

    parts.append("</svg>")
    return _widget("".join(parts), W + 2 * PAD, total_h)
